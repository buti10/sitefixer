# scan_worker.py
import os, json, hashlib, math, re, tempfile, traceback
from datetime import datetime
from paramiko import Transport, SFTPClient
import mysql.connector
from stat import S_ISDIR

DB_KW = dict(
    host=os.getenv("DB_HOST","localhost"),
    user=os.getenv("DB_USER","root"),
    password=os.getenv("DB_PASS",""),
    database=os.getenv("DB_NAME","sitefixer")
)

def get_db():
    return mysql.connector.connect(**DB_KW)

def update_scan(scan_id, **fields):
    db = get_db(); cur = db.cursor()
    sets = ", ".join([f"{k}=%s" for k in fields.keys()])
    vals = list(fields.values()) + [scan_id]
    cur.execute(f"UPDATE scans SET {sets} WHERE id=%s", vals)
    db.commit(); cur.close(); db.close()

def insert_finding(scan_id, path, severity, ftype, detail):
    db = get_db(); cur = db.cursor()
    cur.execute("INSERT INTO findings (scan_id, path, severity, type, detail) VALUES (%s,%s,%s,%s,%s)",
                (scan_id, path, severity, ftype, json.dumps(detail)))
    db.commit(); cur.close(); db.close()

def sha256_bytes(b: bytes):
    return hashlib.sha256(b).hexdigest()

def entropy(data: bytes):
    if not data: return 0.0
    from collections import Counter
    cnt = Counter(data)
    e = 0.0
    length = len(data)
    for v in cnt.values():
        p = v/length
        e -= p * math.log2(p)
    return e

# ----- SFTP session lookup: implement according to your SID storage -----
def connect_sftp_from_sid(sid):
    """
    Erwartet eine DB-Tabelle `sftp_sessions` mit columns:
    id, sid, host, port, username, password, private_key (NULL/optional)
    Passe an dein Schema an.
    """
    db = get_db(); cur = db.cursor(dictionary=True)
    cur.execute("SELECT host, port, username, password, private_key FROM sftp_sessions WHERE sid=%s LIMIT 1", (sid,))
    r = cur.fetchone()
    cur.close(); db.close()
    if not r:
        raise RuntimeError(f"SFTP SID {sid} not found")
    host = r.get("host")
    port = int(r.get("port") or 22)
    username = r.get("username")
    password = r.get("password")
    key = r.get("private_key")
    # create transport
    t = Transport((host, port))
    if key:
        # if private key present use it (paramiko expects PKey object; simplified: use password method if key is raw)
        t.connect(username=username, password=password)
    else:
        t.connect(username=username, password=password)
    sftp = SFTPClient.from_transport(t)
    return t, sftp

# ----- Heuristics + YARA integration optional -----
try:
    import yara
    YARA_AVAILABLE = True
    # load rules from /opt/sitefixer/yara/*.yara if present
    YARA_RULES = None
    rules_dir = os.getenv("YARA_RULES_DIR","/opt/sitefixer/yara")
    if os.path.isdir(rules_dir):
        rules_files = [os.path.join(rules_dir,f) for f in os.listdir(rules_dir) if f.endswith(".yara")]
        if rules_files:
            YARA_RULES = yara.compile(filepaths={f.split("/")[-1]: f for f in rules_files})
except Exception:
    YARA_AVAILABLE = False
    YARA_RULES = None

def detect_suspicious(content: bytes, path: str):
    findings = []
    # try decode text
    try:
        text = content.decode("utf-8", errors="ignore")
    except:
        text = ""
    # dangerous PHP functions
    if re.search(r'\b(passwd|exec|shell_exec|system|popen|proc_open|eval|assert|create_function)\b', text, re.IGNORECASE):
        findings.append(("dangerous_functions","high","contains dangerous functions"))
    # base64 + eval patterns
    if re.search(r'(base64_decode\(|eval\(|gzinflate\(|str_rot13\()', text, re.IGNORECASE):
        findings.append(("obfuscation","high","eval/base64/gzinflate pattern"))
    # long obfuscated strings (entropy)
    ent = entropy(content)
    if ent >= 7.5 and len(content) > 200:
        findings.append(("high_entropy","medium",f"{ent:.2f}"))
    # suspicious file extensions or locations
    if path.endswith((".php",".phtml",".php5",".php7")):
        # php specific checks above
        pass
    # yara
    if YARA_AVAILABLE and YARA_RULES:
        try:
            matches = YARA_RULES.match(data=content)
            if matches:
                findings.append(("yara_match","high", [m.rule for m in matches]))
        except Exception:
            pass
    return findings

# ----- Main worker entrypoint -----
def perform_scan(scan_id):
    started = datetime.utcnow()
    try:
        update_scan(scan_id, status="RUNNING", started_at=started, progress=1)
        # load meta
        db = get_db(); cur = db.cursor(dictionary=True)
        cur.execute("SELECT meta FROM scans WHERE id=%s", (scan_id,))
        row = cur.fetchone()
        cur.close(); db.close()
        meta = {}
        if row and row.get("meta"):
            try: meta = json.loads(row["meta"])
            except: meta = {}
        sid = meta.get("sid")
        root = meta.get("root", "/")
        if not sid:
            raise RuntimeError("No sid in scan meta")
        t, sftp = connect_sftp_from_sid(sid)

        # gather file list
        paths = []
        def walk(p):
            try:
                for attr in sftp.listdir_attr(p):
                    name = attr.filename
                    full = (p.rstrip("/") + "/" + name) if p!="/" else ("/" + name)
                    if S_ISDIR(attr.st_mode):
                        # skip common huge directories if needed (node_modules, vendor)
                        if name in ('.git','node_modules','vendor','uploads/cache'): 
                            continue
                        walk(full)
                    else:
                        paths.append(full)
            except Exception:
                pass
        walk(root)

        total = len(paths) or 1
        scanned = 0
        for path in paths:
            scanned += 1
            progress = int(scanned/total*100)
            try:
                f = sftp.file(path, "rb")
                content = f.read(1024*1024*5)  # read up to 5MB; small files fully
                rest = b""
                # if file larger than read chunk, attempt to read rest in streaming only if necessary
                # but avoid huge memory: skip reading very large files fully
                try:
                    # if file size < 5MB read fully
                    size = f.stat().st_size
                    if size <= 5*1024*1024:
                        f.seek(0); content = f.read()
                    else:
                        # keep first chunk only for heuristics
                        pass
                except Exception:
                    pass
                f.close()
                sha = sha256_bytes(content)
                finds = detect_suspicious(content, path)
                if finds:
                    for ftype, severity, detail in finds:
                        insert_finding(scan_id, path, severity, ftype, {"detail": detail, "sha256": sha})
                # additional low-level checks
                # e.g. check for suspicious file permissions can be checked via sftp.stat
            except Exception as e:
                insert_finding(scan_id, path, "low", "read_error", {"error": str(e)})
            # update progress periodically
            if scanned % 5 == 0 or progress >= 100:
                update_scan(scan_id, progress=progress)
        update_scan(scan_id, progress=100, status="DONE", finished_at=datetime.utcnow())
        sftp.close(); t.close()
    except Exception as e:
        tb = traceback.format_exc()
        update_scan(scan_id, status="FAILED", notes=str(e) + "\n" + tb, finished_at=datetime.utcnow())
