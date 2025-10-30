# app/tasks_scan.py
from __future__ import annotations
import io, json, re, time, os
from datetime import datetime
from typing import Optional, Iterable, Dict, List, Tuple
from pathlib import PurePosixPath

# Lazy-Imports (verhindern Backend-Crash, wenn Pakete fehlen)
try:
    import paramiko
except Exception:
    paramiko = None  # type: ignore
try:
    import requests
except Exception:
    requests = None  # type: ignore
try:
    from rq import get_current_job
except Exception:
    def get_current_job(): return None  # type: ignore
try:
    from .extensions import rq_scans
except Exception:
    rq_scans = None  # type: ignore

from .models import Scan, Finding, ScanLog, Report
from . import db as _db

EXCLUDE_DIRS = {"node_modules","vendor",".git",".svn",".cache","cache",".well-known",".quarantine"}
MAX_FILE = 2 * 1024 * 1024
SAMPLE   = 64 * 1024
CORE_CACHE_DIR = PurePosixPath("/var/www/sitefixer/backend/core-cache/wordpress")
SCAN_EXT = {".php",".phtml",".php5",".phar",".inc",".txt",".js",".htaccess",".user.ini"}

def enqueue_scan(scan_id: int):
    if rq_scans is None:
        raise RuntimeError("RQ/Redis nicht verfügbar (extensions.rq_scans).")
    return rq_scans.enqueue("app.tasks_scan.run_scan", scan_id, job_timeout="45m")

def _commit(db, obj=None):
    if obj is not None: db.add(obj)
    db.commit()

def _log(db, scan_id: int, text: str):
    last = (db.query(ScanLog).filter(ScanLog.scan_id==scan_id)
            .order_by(ScanLog.line_no.desc()).first())
    line_no = (last.line_no if last else 0) + 1
    _commit(db, ScanLog(scan_id=scan_id, line_no=line_no, text=text))
    return line_no

def _open_sftp_from_config(cfg: dict):
    if paramiko is None:
        raise RuntimeError("paramiko nicht installiert")
    s = (cfg or {}).get("sftp")
    if not s: return None
    t = paramiko.Transport((s["host"], int(s.get("port", 22))))
    if s.get("auth") == "key":
        pkey = paramiko.RSAKey.from_private_key(io.StringIO(s.get("key") or ""))
        t.connect(username=s["user"], pkey=pkey)
    else:
        t.connect(username=s["user"], password=s.get("password") or "")
    return paramiko.SFTPClient.from_transport(t)

def _safe_join(parent: str, name: str) -> str:
    return f"/{name}" if parent == "/" else f"{parent.rstrip('/')}/{name}"

def _walk(sftp, root: str) -> Iterable[Dict]:
    stack = [root]
    while stack:
        d = stack.pop()
        try:
            for it in sftp.listdir_attr(d):
                name = it.filename
                path = _safe_join(d, name)
                is_dir = (str(it.longname or "").startswith("d")) or (it.st_mode and (it.st_mode & 0o40000))
                if is_dir:
                    if name in EXCLUDE_DIRS: continue
                    stack.append(path)
                else:
                    yield {"path": path, "size": int(it.st_size or 0)}
        except Exception:
            continue

def _read_chunked(sftp, path: str, size: int) -> bytes:
    if size <= 0: return b""
    if size <= MAX_FILE:
        with sftp.open(path, "rb") as f: return f.read()
    with sftp.open(path, "rb") as f: head = f.read(SAMPLE)
    with sftp.open(path, "rb") as f:
        try: f.seek(max(0, size - SAMPLE))
        except Exception: return head
        tail = f.read(SAMPLE)
    return head + b"\n...\n" + tail

_webshell_re = re.compile(r"(r57|c99|FilesMan|wso_?shell|webshell)", re.I)
_danger_call = re.compile(r"(eval|assert|system|exec|shell_exec|passthru|proc_open|popen)\s*\(", re.I)
_user_input  = re.compile(r"\$_(GET|POST|REQUEST|COOKIE|SERVER)\s*\[['\"][^'\" ]+['\"]\]", re.I)
_obfus       = re.compile(r"(base64_decode|gzinflate|str_rot13|fromCharCode|create_function|atob)\s*\(", re.I)
_preg_e      = re.compile(r"preg_replace\s*\(\s*['\"]\/.*\/e['\"]", re.I)
_js_inject   = re.compile(r"(document\.write\s*\(|atob\(|unescape\()", re.I)
_ht_bad      = re.compile(r"RewriteRule\s+.*\s+\[.*(E=|R=302|R=307).*\]|AddHandler\s+application/x-httpd-php", re.I)
_bad_name    = re.compile(r"\.(cache|bak|tmp|old)\.php$|^\.?s(h)?ell\.php$", re.I)

def _entropy(s: bytes) -> float:
    from math import log2
    if not s: return 0.0
    from collections import Counter
    cnt = Counter(s); l = float(len(s))
    return -sum((n/l) * log2(n/l) for n in cnt.values())

def _should_scan(path: str, size: int) -> bool:
    name = path.rsplit("/", 1)[-1].lower()
    if any(seg in EXCLUDE_DIRS for seg in path.strip("/").split("/")): return False
    if name.endswith((".jpg",".jpeg",".png",".gif",".webp",".svg",".ico",
                      ".zip",".tar",".gz",".7z",".rar",".pdf",".mp4",".mp3",
                      ".woff",".woff2",".ttf",".eot",".map")): return False
    if size > 32 * 1024 * 1024: return False
    ext = "." + name.split(".")[-1] if "." in name else ""
    return (ext in SCAN_EXT) or (name in {".htaccess","user.ini",".user.ini"})

def _analyze(buf: bytes, path: str) -> Tuple[str, str, str]:
    txt = buf.decode("utf-8", errors="ignore")
    name = path.rsplit("/",1)[-1].lower()
    if name == ".htaccess" and _ht_bad.search(txt):
        return "suspicious","htaccess_rule", txt[:300]
    if path.endswith(".js") and _js_inject.search(txt) and "http" in txt:
        return "suspicious","js_inject", txt[:300]
    if _webshell_re.search(txt) or (_danger_call.search(txt) and _user_input.search(txt)):
        return "malicious","yara_webshell", txt[:300]
    if _obfus.search(txt) or _preg_e.search(txt) or _bad_name.search(name) or _entropy(buf) > 7.5:
        return "suspicious","heur_obfuscation", txt[:300]
    return "clean","none", txt[:200]

def _read_text(sftp, path: str) -> Optional[str]:
    try:
        with sftp.open(path, "r", bufsize=32768) as f:
            return f.read().decode("utf-8","ignore")
    except Exception:
        return None

def _wp_root_from(root: str) -> str:
    r = (root or "/").rstrip("/") or "/"
    return r[: -len("/wp-content")] or "/" if r.endswith("/wp-content") else r

def _detect_cms_and_version(sftp, root: str):
    r = _wp_root_from(root)
    txt = _read_text(sftp, f"{r}/wp-includes/version.php")
    if txt:
        m = re.search(r"\$wp_version\s*=\s*'([^']+)'", txt)
        return ("WordPress", m.group(1) if m else None)
    xml = _read_text(sftp, f"{r}/administrator/manifests/files/joomla.xml")
    if xml:
        m = re.search(r"<version>\s*([^<]+)\s*</version>", xml)
        return ("Joomla", m.group(1).strip() if m else None)
    t3 = _read_text(sftp, f"{r}/typo3/sysext/core/composer.json")
    if t3:
        try: v = (json.loads(t3)).get("version")
        except Exception: v = None
        return ("TYPO3", v)
    dr = _read_text(sftp, f"{r}/core/lib/Drupal.php")
    if dr:
        m = re.search(r"const\s+VERSION\s*=\s*'([^']+)'", dr)
        return ("Drupal", m.group(1) if m else None)
    return (None, None)

def _detect_php_version(sftp, root: str):
    r = _wp_root_from(root)
    lock = _read_text(sftp, f"{r}/composer.lock")
    if lock:
        try:
            j = json.loads(lock)
            for p in (j.get("packages", []) + j.get("packages-dev", [])):
                if p.get("name") == "php": return p.get("version")
                if "php" in (p.get("require") or {}): return str(p["require"]["php"])
        except Exception: pass
    ui = _read_text(sftp, f"{r}/user.ini") or _read_text(sftp, f"{r}/.user.ini")
    if ui:
        m = re.search(r"php(\d\.\d)", ui);
        if m: return m.group(1)
    ht = _read_text(sftp, f"{r}/.htaccess")
    if ht:
        m = re.search(r"php(\d\d?)\.(\d)", ht)
        if m: return f"{m.group(1)}.{m.group(2)}"
    return None

def _detect_from_http(url: str):
    if requests is None: return (None, None, None)
    cms = cms_ver = php = None
    try:
        r = requests.get(url, timeout=10, headers={"User-Agent":"Sitefixer/1.0"})
        gen = re.search(r'<meta[^>]+name=["\']generator["\'][^>]+content=["\']([^"\']+)["\']', r.text, re.I)
        if gen:
            g = gen.group(1)
            if "WordPress" in g:
                cms="WordPress"; m=re.search(r'WordPress\s+([\d\.]+)', g, re.I); cms_ver=m.group(1) if m else None
            elif "Joomla" in g:
                cms="Joomla";    m=re.search(r'([\d\.]+)', g);                  cms_ver=m.group(1) if m else None
            elif "Drupal" in g:
                cms="Drupal";    m=re.search(r'([\d\.]+)', g);                  cms_ver=m.group(1) if m else None
        xp = r.headers.get("X-Powered-By") or r.headers.get("x-powered-by")
        if xp and "PHP" in xp.upper():
            m = re.search(r'PHP/?\s*([\d\.]+)', xp, re.I); php=m.group(1) if m else None
        if (not cms or cms=="WordPress") and not cms_ver:
            try:
                j = requests.get(url.rstrip("/") + "/wp-json", timeout=6).json()
                m = re.search(r'WordPress\s*([\d\.]+)', str(j.get("generator") or j.get("name") or ""), re.I)
                if m: cms, cms_ver = "WordPress", m.group(1)
            except Exception: pass
    except Exception:
        pass
    return cms, cms_ver, php

def quarantine(scan: Scan, paths: List[str], dry_run: bool = True) -> int:
    cfg = (scan.config or {})
    sftp = None; moved = 0
    try:
        sftp = _open_sftp_from_config(cfg)
        if not sftp: return 0
        root = (cfg.get("root_path") or "/").rstrip("/") or "/"
        qdir = _safe_join(root, ".quarantine")
        try: sftp.mkdir(qdir)
        except Exception: pass
        ts = int(time.time())
        for p in paths:
            name = p.split("/")[-1]
            target = _safe_join(qdir, f"{ts}-{name}")
            _log(_db.session, scan.id, f"{'[dry]' if dry_run else ''} quarantine {p} -> {target}")
            if not dry_run:
                try:
                    sftp.rename(p, target); sftp.chmod(target, 0o400); moved += 1
                except Exception as e:
                    _log(_db.session, scan.id, f"quarantine failed: {e}")
            else:
                moved += 1
    finally:
        try: sftp and sftp.close()
        except Exception: pass
    return moved

def core_restore_wp(scan: Scan, dry_run: bool = True) -> int:
    cfg = (scan.config or {})
    sftp = None; copied = 0
    try:
        sftp = _open_sftp_from_config(cfg)
        if not sftp: return 0
        root = (cfg.get("root_path") or "/").rstrip("/") or "/"
        for base in ("wp-admin","wp-includes"):
            src_root = (CORE_CACHE_DIR / base)
            if not os.path.isdir(src_root): continue
            for dirpath, _, filenames in os.walk(src_root):
                rel = PurePosixPath(dirpath).relative_to(CORE_CACHE_DIR)
                dest_dir = _safe_join(root, str(rel))
                parts = dest_dir.strip("/").split("/")
                cur = ""
                for seg in parts:
                    cur = f"{cur}/{seg}" if cur else f"/{seg}"
                    try: sftp.mkdir(cur)
                    except Exception: pass
                for fn in filenames:
                    src_file = f"{dirpath}/{fn}"
                    dest_file = _safe_join(dest_dir, fn)
                    _log(_db.session, scan.id, f"{'[dry]' if dry_run else ''} restore {dest_file}")
                    if not dry_run:
                        with open(src_file,"rb") as fsrc:
                            with sftp.open(dest_file,"wb") as fdst:
                                fdst.write(fsrc.read())
                    copied += 1
    finally:
        try: sftp and sftp.close()
        except Exception: pass
    return copied

def run_scan(scan_id: int):
    db = _db.session
    s: Scan = db.get(Scan, scan_id)
    if not s: return
    job = get_current_job()
    s.status="running"; s.started_at=datetime.utcnow(); s.progress=3
    s.job_id = job.id if job else None
    s.counts = {"malicious":0,"suspicious":0,"clean":0,"total":0,"scanned":0,"bytes":0,"errors":0}
    _commit(db)

    try:
        cfg = s.config or {}
        root = (cfg.get("root_path") or "/").rstrip("/") or "/"
        http = (cfg.get("target_url") or "").strip()

        cms_name=cms_ver=php_ver=None
        if http:
            c,v,p = _detect_from_http(http)
            cms_name, cms_ver, php_ver = c or cms_name, v or cms_ver, p or php_ver

        sftp = _open_sftp_from_config(cfg) if cfg.get("sftp") else None
        try:
            if sftp:
                c,v = _detect_cms_and_version(sftp, root)
                p    = _detect_php_version(sftp, root)
                cms_name, cms_ver, php_ver = c or cms_name, v or cms_ver, p or php_ver
        finally:
            try: sftp and sftp.close()
            except Exception: pass

        s.cms, s.cms_version, s.php_version = cms_name, cms_ver, php_ver
        _commit(db)

        if s.kind == "deep" and (cfg.get("sftp") is not None):
            sftp = _open_sftp_from_config(cfg)
            if not sftp:
                _log(db, s.id, "SFTP-Verbindung fehlgeschlagen"); raise RuntimeError("sftp failed")

            _log(db, s.id, f"deep scan start root={root}")
            files = [it for it in _walk(sftp, root)]
            s.counts["total"] = len(files); _log(db, s.id, f"files={s.counts['total']}")
            _commit(db)

            done = 0
            for it in files:
                path, size = it["path"], int(it["size"] or 0)
                if not _should_scan(path, size): continue
                try:
                    buf = _read_chunked(sftp, path, size)
                    sev, rule, preview = _analyze(buf, path)
                    if sev != "clean":
                        db.add(Finding(scan_id=s.id, path=path, rule=rule, severity=sev, preview=preview))
                        s.counts[sev] += 1
                    else:
                        s.counts["clean"] += 1
                    s.counts["bytes"] += len(buf)
                except Exception as e:
                    s.counts["errors"] += 1; _log(db, s.id, f"read error {path}: {e}")
                finally:
                    done += 1; s.counts["scanned"] = done
                    s.progress = min(95, 5 + int(90 * done / max(1, s.counts["total"])))
                    if done % 50 == 0: _commit(db)

            try: sftp.close()
            except Exception: pass

            penalty = s.counts["malicious"]*50 + s.counts["suspicious"]*5
            s.score = max(0, 100 - penalty)
            s.status = "issues" if (s.counts["malicious"] or s.counts["suspicious"]) else "done"
        else:
            s.score = 100; s.status = "done"

        s.progress=100; s.finished_at=datetime.utcnow(); _commit(db)
        _commit(db, Report(scan_id=s.id, type=s.kind.capitalize(), score=s.score,
                           url=f"/reports/{s.id}-{int(time.time())}.pdf"))
    except Exception:
        s.status="error"; s.progress=100; s.finished_at=datetime.utcnow(); _commit(db); raise
    finally:
        _db.session.remove()
