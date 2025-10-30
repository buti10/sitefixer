import json, threading, uuid
from app.extensions import db, redis_conn
from app.models_scan import Scan, Finding
from ..common.errors import NotFound
from ..workers.scan_worker import run_scan as worker_run_scan

def enqueue(sid, root, patterns):
    jid = str(uuid.uuid4())

    s = Scan(
    id=jid, sid=sid, root=root,
    patterns=json.dumps(patterns or []),  # <— HIER JSON-String
    status="queued", progress=0
    )

    db.session.add(s)
    db.session.commit()

    redis_conn.set(f"scan:{jid}", json.dumps({
        "status": "queued", "progress": 0, "findings": []
    }), ex=3600)

    t = threading.Thread(target=_run, args=(jid, sid, root, patterns or []), daemon=True)
    t.start()
    return jid

def _run(jid, sid, root, patterns):
    worker_run_scan(jid, sid, root, patterns)

def status(jid):
    key = f"scan:{jid}"
    raw = redis_conn.get(key)
    if raw:
        return json.loads(raw)
    s = db.session.get(Scan, jid)
    if not s:
        raise NotFound("scan_not_found")
    return {"status": s.status, "progress": s.progress, "findings": []}
