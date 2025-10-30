import re, time, json
from app.extensions import redis_conn, db
from app.models_scan import Scan, Finding
from app.models_patterns import ScanPattern
from ..infra.storage import Sessions
from ..infra.sftp_client import SFTPClient
from ..common.errors import NotFound
from app import create_app

TEXT_CHUNK_TRY = 1024
MAX_FILE_BYTES  = 5_000_000
PER_FILE_TIMEOUT = 0.5

_app_cached = None
def _app():
    global _app_cached
    if _app_cached is None:
        _app_cached = create_app()
    return _app_cached

def _is_text(b: bytes) -> bool:
    if not b: return True
    if b.find(b"\x00") != -1: return False
    nonprint = sum(1 for c in b if c < 9 or (c > 13 and c < 32))
    return (nonprint / max(1, len(b))) < 0.30

def _severity_for(engine: str) -> str:
    return "malicious" if engine == "regex" else "suspicious"

def run_scan(jid, sid, root, patterns_from_payload):
    key = f"scan:{jid}"
    with _app().app_context():
        try:
            compiled = []
            db_patterns = ScanPattern.query.filter_by(enabled=True).all()
            if db_patterns:
                for p in db_patterns:
                    try:
                        compiled.append((p.engine, re.compile(p.pattern, re.IGNORECASE)))
                    except re.error:
                        continue
            else:
                for p in (patterns_from_payload or []):
                    try:
                        compiled.append(("regex", re.compile(p, re.IGNORECASE)))
                    except re.error:
                        compiled.append(("regex", re.compile(re.escape(p), re.IGNORECASE)))

            state = {"status": "running", "progress": 1, "findings": []}
            redis_conn.set(key, json.dumps(state), ex=3600)

            s = db.session.get(Scan, jid)
            if s:
                s.status = "running"; s.progress = 1; db.session.commit()

            creds = Sessions.get(sid)
            client = SFTPClient.connect(creds["host"], creds["username"], creds["password"])
            try:
                paths = list(client.iter_paths(root, max_files=10000))
                total = max(1, len(paths))
                processed = 0

                for path in paths:
                    t0 = time.time()

                    # filename rules
                    fn_hits = []
                    for eng, rx in compiled:
                        if eng != "filename": continue
                        if rx.search(path):
                            fn_hits.append({
                                "path": path, "rule": f"[filename]{rx.pattern}",
                                "line": None, "snippet": path, "severity": _severity_for(eng),
                            })
                    if fn_hits:
                        state["findings"].extend(fn_hits)
                        db.session.bulk_save_objects([Finding(scan_id=jid, **f) for f in fn_hits])
                        db.session.commit()

                    # content rules
                    try:
                        sample = client.read_file(path, max_bytes=TEXT_CHUNK_TRY)
                        if _is_text(sample):
                            data = sample
                            if len(sample) >= TEXT_CHUNK_TRY:
                                rest = client.read_file(path, max_bytes=MAX_FILE_BYTES)
                                if len(rest) > len(sample): data = sample + rest[len(sample):]
                            try:
                                text = data.decode("utf-8", errors="replace")
                            except Exception:
                                text = data.decode("latin-1", errors="replace")

                            content_hits = []
                            for eng, rx in compiled:
                                if eng != "regex": continue
                                for m in rx.finditer(text):
                                    idx = m.start()
                                    snippet = text[max(0, idx-40):min(len(text), idx+40)].replace("\n"," ")
                                    line = text[:idx].count("\n") + 1
                                    content_hits.append({
                                        "path": path, "rule": rx.pattern,
                                        "line": line, "snippet": snippet,
                                        "severity": _severity_for(eng),
                                    })
                            if content_hits:
                                state["findings"].extend(content_hits)
                                db.session.bulk_save_objects([Finding(scan_id=jid, **f) for f in content_hits])
                                db.session.commit()
                    except Exception as e:
                        state.setdefault("errors", []).append({"path": path, "error": str(e)})

                    processed += 1
                    prog = int(processed * 100 / total)
                    state["progress"] = prog
                    redis_conn.set(key, json.dumps(state), ex=3600)
                    if s:
                        s.progress = prog; db.session.commit()

                    if time.time() - t0 > PER_FILE_TIMEOUT:
                        pass

                state["status"] = "done"; state["progress"] = 100
                redis_conn.set(key, json.dumps(state), ex=3600)
                if s:
                    s.status = "done"; s.progress = 100; db.session.commit()
            finally:
                try: client.close()
                except: pass

        except NotFound as e:
            redis_conn.set(key, json.dumps({"status":"error","progress":0,"findings":[],"error":str(e)}), ex=3600)
            _mark_error(jid)
        except Exception as e:
            redis_conn.set(key, json.dumps({"status":"error","progress":0,"findings":[],"error":str(e)}), ex=3600)
            _mark_error(jid)

def _mark_error(jid):
    with _app().app_context():
        s = db.session.get(Scan, jid)
        if s:
            s.status = "error"; s.progress = 0; db.session.commit()
