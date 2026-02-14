from __future__ import annotations

from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required

from app.models_wp_repair_audit import RepairAction, RepairActionFile

bp_audit = Blueprint("wp_repair_audit", __name__)

def _int(v, default):
    try:
        return int(v)
    except Exception:
        return default

@bp_audit.get("/audit/actions")
@jwt_required()
def api_audit_actions_list():
    """
    Query:
      ticket_id=70 (optional)
      status=applied|created|rolled_back|failed|partial|skipped (optional)
      fix_id=maintenance|core_replace|... (optional)
      limit=50 (optional, max 200)
      offset=0 (optional)

    Returns:
      { ok: true, items: [...], total: N, limit, offset }
    """
    ticket_id = request.args.get("ticket_id")
    status = (request.args.get("status") or "").strip()
    fix_id = (request.args.get("fix_id") or "").strip()
    limit = min(max(_int(request.args.get("limit"), 50), 1), 200)
    offset = max(_int(request.args.get("offset"), 0), 0)

    q = RepairAction.query

    if ticket_id:
        q = q.filter(RepairAction.ticket_id == _int(ticket_id, 0))
    if status:
        q = q.filter(RepairAction.status == status)
    if fix_id:
        q = q.filter(RepairAction.fix_id == fix_id)

    total = q.count()

    rows = (
        q.order_by(RepairAction.created_at_utc.desc())
         .offset(offset)
         .limit(limit)
         .all()
    )

    items = []
    for r in rows:
        items.append({
            "action_id": r.action_id,
            "ticket_id": r.ticket_id,
            "fix_id": r.fix_id,
            "status": r.status,
            "created_at_utc": r.created_at_utc.isoformat() if r.created_at_utc else None,
            "updated_at_utc": r.updated_at_utc.isoformat() if r.updated_at_utc else None,
            "created_by_user_id": r.created_by_user_id,
            "created_by_name": r.created_by_name,
            "wp_root": r.wp_root,
            "project_root": r.project_root,
            "remote_action_dir": r.remote_action_dir,
            "remote_meta_path": r.remote_meta_path,
            "remote_moved_dir": r.remote_moved_dir,
        })

    return jsonify({
        "ok": True,
        "total": total,
        "limit": limit,
        "offset": offset,
        "items": items,
    })


@bp_audit.get("/audit/actions/<action_id>")
@jwt_required()
def api_audit_action_detail(action_id: str):
    """
    Returns action row + file ops.
    """
    r = RepairAction.query.filter_by(action_id=action_id).first()
    if not r:
        return jsonify({"ok": False, "error": "not_found"}), 404

    files = (
        RepairActionFile.query
        .filter(RepairActionFile.action_id == action_id)
        .order_by(RepairActionFile.ts_utc.asc())
        .all()
    )

    action = {
        "action_id": r.action_id,
        "ticket_id": r.ticket_id,
        "fix_id": r.fix_id,
        "status": r.status,
        "created_at_utc": r.created_at_utc.isoformat() if r.created_at_utc else None,
        "updated_at_utc": r.updated_at_utc.isoformat() if r.updated_at_utc else None,
        "created_by_user_id": r.created_by_user_id,
        "created_by_name": r.created_by_name,
        "wp_root": r.wp_root,
        "project_root": r.project_root,
        "remote_action_dir": r.remote_action_dir,
        "remote_meta_path": r.remote_meta_path,
        "remote_moved_dir": r.remote_moved_dir,
        "context_json": r.context_json or {},
        "result_json": getattr(r, "result_json", None),
        "error_json": getattr(r, "error_json", None),
        "meta_json": r.meta_json,
        "manifest_json": r.manifest_json,
    }

    ops = []
    for f in files:
        ops.append({
            "id": f.id,
            "op": f.op,
            "src_path": f.src_path,
            "dst_path": f.dst_path,
            "ts_utc": f.ts_utc.isoformat() if f.ts_utc else None,
            "payload_json": f.payload_json or {},
        })

    return jsonify({"ok": True, "action": action, "file_ops": ops})
