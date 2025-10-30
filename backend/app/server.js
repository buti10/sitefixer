// server.js
const express = require('express');
const bodyParser = require('body-parser');
const SftpClient = require('ssh2-sftp-client');
const crypto = require('crypto');
const pLimit = require('p-limit');

const app = express();
app.use(bodyParser.json({ limit: '2mb' }));

/* -------------------- In-Memory Stores -------------------- */
const scans = new Map();          // id -> scan record
const sftpSessions = new Map();   // session_id -> { host,port,user,auth,password,key }

/* -------------------- Helpers -------------------- */
const nowISO = () => new Date().toISOString();
const newId = () => crypto.randomBytes(8).toString('hex');
const logLine = (scan, msg) => {
  scan.logs.push(`[${nowISO()}] ${msg}`);
};

function blankScan({ ticket_id, kind }) {
  return {
    id: newId(),
    ticket_id,
    kind,                 // 'quick' | 'deep' | 'health'
    status: 'queued',     // 'queued' | 'running' | 'done' | 'issues' | 'error' | 'canceled'
    progress: 0,
    started_at: nowISO(),
    ended_at: null,
    counts: { malicious: 0, suspicious: 0, clean: 0 },
    cms: null,
    cms_version: null,
    php_version: null,
    score: null,
    findings: [],         // { id, path, rule, severity, preview }
    logs: [],
    config: { root_path: null, sftp: null },
    _totalFiles: 0,
    _doneFiles: 0,
  };
}

/* -------------------- SFTP session endpoints (Explorer) -------------------- */
app.post('/api/sftp/open', async (req, res) => {
  const { host, port = 22, user, auth, password, key } = req.body || {};
  if (!host || !user || !auth) return res.status(400).json({ error: 'missing fields' });
  const sid = newId();
  sftpSessions.set(sid, { host, port, user, auth, password, key });
  return res.json({ session_id: sid });
});

app.get('/api/sftp/:sid/list', async (req, res) => {
  const { sid } = req.params;
  const { path = '/' } = req.query;
  const cfg = sftpSessions.get(sid);
  if (!cfg) return res.status(404).json({ error: 'session not found' });
  const sftp = new SftpClient();
  try {
    await sftp.connect(
      cfg.auth === 'key'
        ? { host: cfg.host, port: cfg.port, username: cfg.user, privateKey: cfg.key }
        : { host: cfg.host, port: cfg.port, username: cfg.user, password: cfg.password }
    );
    const list = await sftp.list(path || '/');
    const items = list.map(it => ({
      name: it.name,
      path: (path === '/' ? `/${it.name}` : `${String(path).replace(/\/$/,'')}/${it.name}`),
      type: it.type === 'd' ? 'dir' : 'file',
      size: it.size
    }));
    res.json(items);
  } catch (e) {
    res.status(500).json({ error: String(e.message || e) });
  } finally {
    try { await sftp.end(); } catch {}
  }
});

/* -------------------- Scan lifecycle -------------------- */
app.post('/api/scans', async (req, res) => {
  const { ticket_id, kind } = req.body || {};
  if (!ticket_id || !kind) return res.status(400).json({ error: 'missing fields' });
  const scan = blankScan({ ticket_id, kind });
  scans.set(scan.id, scan);
  logLine(scan, `scan created kind=${kind}`);

  // start deep/quick/health
  if (kind === 'deep') setTimeout(() => runDeepScan(scan.id).catch(() => {}), 10);

  return res.json({ id: scan.id });
});

app.patch('/api/scans/:id/config', async (req, res) => {
  const scan = scans.get(req.params.id);
  if (!scan) return res.status(404).json({ error: 'not found' });
  const { root_path, sftp } = req.body || {};
  if (root_path) scan.config.root_path = root_path;
  if (sftp) scan.config.sftp = sftp;
  logLine(scan, `config saved root=${scan.config.root_path || '—'}`);
  res.json({ ok: true });
});

app.get('/api/scans/:id', (req, res) => {
  const scan = scans.get(req.params.id);
  if (!scan) return res.status(404).json({ error: 'not found' });
  res.json({
    id: scan.id,
    kind: scan.kind,
    status: scan.status,
    progress: scan.progress,
    started_at: scan.started_at,
    ended_at: scan.ended_at,
    counts: scan.counts,
    cms: scan.cms,
    cms_version: scan.cms_version,
    php_version: scan.php_version,
    score: scan.score
  });
});

app.get('/api/scans/:id/findings', (req, res) => {
  const scan = scans.get(req.params.id);
  if (!scan) return res.status(404).json({ error: 'not found' });
  const severity = String(req.query.severity || '').trim();
  const list = severity ? scan.findings.filter(f => f.severity === severity) : scan.findings;
  res.json(list);
});

app.get('/api/scans/:id/logs', (req, res) => {
  const scan = scans.get(req.params.id);
  if (!scan) return res.status(404).json({ error: 'not found' });
  const cursor = Number(req.query.cursor || 0);
  const lines = scan.logs.slice(cursor);
  res.json({ lines, cursor: cursor + lines.length });
});

app.post('/api/scans/:id/actions', async (req, res) => {
  const scan = scans.get(req.params.id);
  if (!scan) return res.status(404).json({ error: 'not found' });
  const { action, dry_run = true } = req.body || {};
  if (action === 'quarantine') {
    const targets = scan.findings.filter(f => f.severity === 'malicious').map(f => f.path);
    const done = await quarantineFiles(scan, targets, dry_run);
    return res.json({ ok: true, processed: done });
  }
  if (action === 'core_restore') {
    logLine(scan, 'core_restore requested (stub)');
    return res.json({ ok: true });
  }
  res.status(400).json({ error: 'unknown action' });
});

/* -------------------- Deep Scan Engine -------------------- */

const MAX_FILE_SIZE = 2 * 1024 * 1024; // 2MB cap
const CONCURRENCY = 6;
const EXCLUDE_DIRS = new Set(['node_modules','vendor','.git','.svn','.cache','cache','.well-known']);

// simple heuristics
function analyzeBuffer(buf) {
  const txt = buf.toString('utf8');
  const m1 = /(eval|assert|system|exec|shell_exec|passthru|proc_open)\s*\(/i.test(txt);
  const m2 = /\$_(GET|POST|REQUEST|COOKIE)\s*\[['"][^'"]+['"]\]/i.test(txt);
  const m3 = /(base64_decode|gzinflate|str_rot13|create_function|fromCharCode)\s*\(/i.test(txt);
  const m4 = /(preg_replace\s*\(\s*['"]\/.*\/e['"])/i.test(txt);
  const backdoor = /(r57|c99|webshell|wso_?shell|FilesMan)/i.test(txt);

  if ((m1 && m2) || backdoor) {
    return { severity: 'malicious', rule: 'yara_webshell' };
  }
  if (m3 || m4) {
    return { severity: 'suspicious', rule: 'heur_obfuscation' };
  }
  return { severity: 'clean', rule: 'none' };
}

async function runDeepScan(id) {
  const scan = scans.get(id);
  if (!scan) return;
  if (!scan.config?.root_path || !scan.config?.sftp) {
    scan.status = 'error';
    logLine(scan, 'missing root_path or sftp credentials');
    return;
  }

  scan.status = 'running';
  logLine(scan, `deep-scan started at root=${scan.config.root_path}`);

  // build file list
  const files = [];
  const sftp = new SftpClient();
  const cred = scan.config.sftp;
  try {
    await sftp.connect(
      cred.auth === 'key'
        ? { host: cred.host, port: cred.port || 22, username: cred.user, privateKey: cred.key }
        : { host: cred.host, port: cred.port || 22, username: cred.user, password: cred.password }
    );

    async function walk(dir) {
      let list = [];
      try {
        list = await sftp.list(dir);
      } catch (e) {
        logLine(scan, `list error ${dir}: ${e.message || e}`);
        return;
      }
      for (const it of list) {
        const p = dir === '/' ? `/${it.name}` : `${dir.replace(/\/$/,'')}/${it.name}`;
        if (it.type === 'd') {
          if (EXCLUDE_DIRS.has(it.name)) continue;
          await walk(p);
        } else {
          files.push({ path: p, size: it.size || 0 });
        }
      }
    }

    await walk(scan.config.root_path);
    scan._totalFiles = files.length;
    logLine(scan, `files queued: ${files.length}`);

    // scan files
    const limit = pLimit(CONCURRENCY);
    await Promise.all(files.map(f => limit(async () => {
      try {
        // small files: full; big files: head+tail
        let buf;
        if (f.size === 0) {
          buf = Buffer.alloc(0);
        } else if (f.size <= MAX_FILE_SIZE) {
          buf = await sftp.get(f.path);
        } else {
          const head = await sftp.get(f.path, { start: 0, end: 64 * 1024 });
          const tail = await sftp.get(f.path, { start: Math.max(0, f.size - 64 * 1024), end: f.size });
          buf = Buffer.concat([head, Buffer.from('\n...\n'), tail]);
        }

        const { severity, rule } = analyzeBuffer(buf);
        const preview = buf.toString('utf8').slice(0, 300);

        if (severity !== 'clean') {
          scan.findings.push({
            id: newId(),
            path: f.path,
            rule,
            severity,
            preview
          });
          if (severity === 'malicious') scan.counts.malicious++;
          if (severity === 'suspicious') scan.counts.suspicious++;
        } else {
          scan.counts.clean++;
        }
      } catch (e) {
        logLine(scan, `read error ${f.path}: ${e.message || e}`);
      } finally {
        scan._doneFiles++;
        scan.progress = Math.round((scan._doneFiles / Math.max(1, scan._totalFiles)) * 100);
      }
    })));

    // score simple: 100 - penalty
    const penalty = scan.counts.malicious * 50 + scan.counts.suspicious * 5;
    scan.score = Math.max(0, 100 - penalty);
    scan.status = (scan.counts.malicious || scan.counts.suspicious) ? 'issues' : 'done';
    scan.ended_at = nowISO();
    logLine(scan, `deep-scan finished status=${scan.status} score=${scan.score}`);
  } catch (e) {
    scan.status = 'error';
    scan.ended_at = nowISO();
    logLine(scan, `fatal: ${e.message || e}`);
  } finally {
    try { await sftp.end(); } catch {}
  }
}

async function quarantineFiles(scan, paths, dryRun) {
  if (!scan.config?.sftp) return 0;
  if (!paths.length) return 0;
  const sftp = new SftpClient();
  let n = 0;
  try {
    const cred = scan.config.sftp;
    await sftp.connect(
      cred.auth === 'key'
        ? { host: cred.host, port: cred.port || 22, username: cred.user, privateKey: cred.key }
        : { host: cred.host, port: cred.port || 22, username: cred.user, password: cred.password }
    );
    const Q = scan.config.root_path.replace(/\/$/,'') + '/.quarantine';
    try { await sftp.mkdir(Q, true); } catch {}

    for (const p of paths) {
      const base = p.split('/').pop();
      const target = `${Q}/${Date.now()}-${base}`;
      logLine(scan, `${dryRun ? '[dry]' : ''} quarantine ${p} -> ${target}`);
      if (!dryRun) {
        try { await sftp.rename(p, target); } catch (e) { logLine(scan, `rename failed: ${e.message || e}`); continue; }
        try { await sftp.chmod(target, 0o400); } catch {}
      }
      n++;
    }
  } catch (e) {
    logLine(scan, `quarantine error: ${e.message || e}`);
  } finally {
    try { await sftp.end(); } catch {}
  }
  return n;
}

/* -------------------- Server -------------------- */
const PORT = process.env.PORT || 8787;
app.listen(PORT, () => console.log(`scanner api listening on :${PORT}`));
