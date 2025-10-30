# backend/blueprints/repairs.py
from flask import Blueprint, request, jsonify, abort
from app.extensions import db
from app.models_repair import ActionsLog

bp = Blueprint("repairs", __name__, url_prefix="/api/repair")

BASIC_PLAN = [
    {"id": "htaccess_minimal",   "label": ".htaccess Minimal",                "risk": "low",    "selected": True},
    {"id": "userini_neutralize", "label": ".user.ini/php.ini neutralisieren", "risk": "low",    "selected": True},
    {"id": "safe_mode",          "label": "Safe-Mode (Plugins/Themes off)",   "risk": "medium", "selected": True},
    {"id": "core_restore",       "label": "Core ersetzen (missing/altered)",  "risk": "medium", "selected": True},
    {"id": "uploads_php_block",  "label": "PHP in Uploads blockieren",        "risk": "low",    "selected": True},
]

@bp.get("/<scan_id>/plan")
def plan(scan_id):
    ticket_id = int(request.args.get("ticket_id", 0) or 0)
    sid = request.args.get("sid") or "unknown"
    return jsonify({"scan_id": scan_id, "ticket_id": ticket_id, "sid": sid, "plan": BASIC_PLAN})

@bp.post("/<scan_id>/execute")
def execute(scan_id):
    data = request.get_json(force=True) or {}
    ticket_id = int(data.get("ticket_id") or 0)
    sid = data.get("sid") or request.args.get("sid")
    actions = data.get("actions") or []
    if not sid:
        abort(400, "sid required")
    if not actions:
        abort(400, "no actions")
    ids = []
    for a in actions:
        row = ActionsLog(ticket_id=ticket_id, sid=sid, scan_id=scan_id,
                         action=a, status="planned", details='{"source":"ui"}')
        db.session.add(row); db.session.flush(); ids.append(row.id)
    db.session.commit()
    return jsonify({"ok": True, "created": ids, "count": len(ids)})

@bp.post("/<scan_id>/run")
def run_now(scan_id):
    from app.repair.runner import run_for_scan
    data = request.get_json(force=True) or {}
    sid  = data.get("sid"); root = data.get("root")
    if not sid or not root:
        return ("sid and root required", 400)
    try:
        run_for_scan(scan_id, sid, root)
    except Exception as e:
        return (f"run failed: {e}", 409)
    return jsonify({"ok": True})


@bp.get("/<scan_id>/actions")
def list_actions(scan_id):
    rows = (ActionsLog.query
            .filter_by(scan_id=scan_id)
            .order_by(ActionsLog.id.desc())
            .all())
    return jsonify({"items": [{
        "id": r.id, "action": r.action, "status": r.status,
        "started_at": r.started_at.isoformat() if r.started_at else None,
        "finished_at": r.finished_at.isoformat() if r.finished_at else None
    } for r in rows]})
