# modules/repair/bp.py
import os, json
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
import mysql.connector

bp = Blueprint("repair", __name__, url_prefix="/api/repair")

def _db():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST","127.0.0.1"),
        user=os.getenv("DB_USER","root"),
        password=os.getenv("DB_PASS",""),
        database=os.getenv("DB_NAME","sitefixer"),
        autocommit=True
    )

def _now_utc():
    return datetime.now(timezone.utc).replace(tzinfo=None)

# 1) Session anlegen
@bp.post("/session")
def create_session():
    data = request.get_json(force=True) or {}
    ticket_id = int(data.get("ticket_id") or 0)
    sid       = (data.get("sid") or "").strip()
    root      = (data.get("root") or "/").strip()
    cms       = (data.get("cms") or None)
    cms_ver   = (data.get("cms_version") or None)
    if not (ticket_id and sid and root):
        return jsonify({"error":"ticket_id, sid, root required"}), 400
    cn = _db(); cur = cn.cursor()
    cur.execute("""INSERT INTO repair_sessions(ticket_id,sid,root,cms,cms_version,created_at)
                   VALUES(%s,%s,%s,%s,%s,NOW())""",
                (ticket_id,sid,root,cms,cms_ver))
    session_id = cur.lastrowid
    cur.close(); cn.close()
    return jsonify({"session_id": session_id})

# 2) Session lesen
@bp.get("/session/<int:session_id>")
def get_session(session_id):
    cn=_db(); cur=cn.cursor(dictionary=True)
    cur.execute("SELECT * FROM repair_sessions WHERE id=%s", (session_id,))
    row = cur.fetchone()
    cur.close(); cn.close()
    if not row:
        return jsonify({"error":"not found"}),404
    return jsonify(row)

# 3) Checkpoint anlegen
@bp.post("/checkpoint")
def create_checkpoint():
    data = request.get_json(force=True) or {}
    session_id = int(data.get("session_id") or 0)
    label = (data.get("label") or "checkpoint").strip()
    # Standard-Snapshot-Verzeichnis
    base = os.getenv("REPAIR_QUARANTINE_BASE","/var/www/sitefixer/quarantine")
    snapshot_dir = os.path.join(base, str(session_id), datetime.utcnow().strftime("%Y%m%dT%H%M%SZ"))
    if not session_id:
        return jsonify({"error":"session_id required"}),400
    cn=_db(); cur=cn.cursor()
    cur.execute("""INSERT INTO repair_checkpoints(session_id,label,snapshot_dir,created_at)
                   VALUES(%s,%s,%s,NOW())""", (session_id,label,snapshot_dir))
    checkpoint_id = cur.lastrowid
    cur.close(); cn.close()
    return jsonify({"checkpoint_id": checkpoint_id, "snapshot_dir": snapshot_dir})

# 4) Aktion loggen (move/replace/delete/…)
@bp.post("/action")
def log_action():
    d = request.get_json(force=True) or {}
    session_id = int(d.get("session_id") or 0)
    kind = (d.get("kind") or "").strip()
    src  = d.get("src")
    dst  = d.get("dst")
    meta = d.get("meta") or {}
    success = 1 if d.get("success") else 0
    error_msg = d.get("error_msg")
    if not (session_id and kind):
        return jsonify({"error":"session_id and kind required"}),400
    cn=_db(); cur=cn.cursor()
    cur.execute("""INSERT INTO repair_actions(session_id,kind,src,dst,meta,success,error_msg,executed_at)
                   VALUES(%s,%s,%s,%s,%s,%s,%s,NOW())""",
                (session_id,kind,src,dst,json.dumps(meta),success,error_msg))
    action_id = cur.lastrowid
    cur.close(); cn.close()
    return jsonify({"action_id": action_id})

# 5) Actions auflisten
@bp.get("/actions")
def list_actions():
    session_id = int(request.args.get("session_id") or 0)
    if not session_id:
        return jsonify({"error":"session_id required"}),400
    cn=_db(); cur=cn.cursor(dictionary=True)
    cur.execute("""SELECT id,kind,src,dst,meta,success,error_msg,executed_at
                   FROM repair_actions WHERE session_id=%s ORDER BY id DESC""", (session_id,))
    rows = cur.fetchall()
    cur.close(); cn.close()
    # meta zurück in dict
    for r in rows:
        try: r["meta"] = json.loads(r["meta"]) if r["meta"] else {}
        except: r["meta"] = {}
    return jsonify(rows)

# 6) Freitext-Log
@bp.post("/log")
def write_log():
    d = request.get_json(force=True) or {}
    session_id = int(d.get("session_id") or 0)
    level = (d.get("level") or "INFO").upper()
    message = d.get("message") or ""
    context = d.get("context") or {}
    if not (session_id and message):
        return jsonify({"error":"session_id and message required"}),400
    cn=_db(); cur=cn.cursor()
    cur.execute("""INSERT INTO repair_logs(session_id,level,message,context,created_at)
                   VALUES(%s,%s,%s,%s,NOW())""",
                (session_id,level[:10],message,json.dumps(context)))
    cur.close(); cn.close()
    return jsonify({"ok": True})
