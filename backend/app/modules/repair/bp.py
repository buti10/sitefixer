# app/modules/repair/bp.py
from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
from app.extensions import db
from app.models_repair import RepairSession, RepairAction, RepairCheckpoint, RepairLog
from .sftp_ops import list_dir as _list_dir, SFTPUnavailable

bp = Blueprint("repair", __name__, url_prefix="/api/repair")

@bp.post("/session")
def create_session():
    d = request.get_json(force=True) or {}
    ticket_id = int(d.get("ticket_id") or 0)
    sid = (d.get("sid") or "").strip()
    root = (d.get("root") or "/").strip()
    if not (ticket_id and sid and root):
        return jsonify({"error":"ticket_id, sid, root required"}), 400
    s = RepairSession(ticket_id=ticket_id, sid=sid, root=root,
                      cms=d.get("cms"), cms_version=d.get("cms_version"))
    db.session.add(s); db.session.commit()
    return jsonify({"session_id": s.id})

@bp.get("/sftp/list")
def sftp_list():
    session_id = int(request.args.get("session_id") or 0)
    path = request.args.get("path")
    if not session_id:
        return jsonify({"error":"session_id required"}), 400
    try:
        body, code = _list_dir(session_id, path)
        return jsonify(body), code
    except SFTPUnavailable as e:
        return jsonify({"error": str(e)}), 500

@bp.post("/action")
def log_action():
    d = request.get_json(force=True) or {}
    session_id = int(d.get("session_id") or 0)
    kind = (d.get("kind") or "").strip()
    if not (session_id and kind):
        return jsonify({"error":"session_id and kind required"}), 400
    a = RepairAction(session_id=session_id, kind=kind,
                     src=d.get("src"), dst=d.get("dst"),
                     meta=d.get("meta") or {}, success=bool(d.get("success")),
                     error_msg=d.get("error_msg"))
    db.session.add(a); db.session.commit()
    return jsonify({"action_id": a.id})

@bp.post("/log")
def write_log():
    d = request.get_json(force=True) or {}
    session_id = int(d.get("session_id") or 0)
    message = d.get("message") or ""
    if not (session_id and message):
        return jsonify({"error":"session_id and message required"}),400
    lg = RepairLog(session_id=session_id, level=(d.get("level") or "INFO").upper()[:10],
                   message=message, context=d.get("context") or {})
    db.session.add(lg); db.session.commit()
    return jsonify({"ok": True})
