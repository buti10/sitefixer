from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt
from app.extensions import db
from .models_patterns import ScanPattern

bp = Blueprint("patterns", __name__)

def _is_admin():
    claims = get_jwt() or {}
    return claims.get("role") == "admin"

@bp.get("/api/patterns")
@jwt_required(optional=True)
def list_patterns():
    only_enabled = request.args.get("enabled") in (None, "1", "true", "True")
    q = ScanPattern.query
    if only_enabled:
        q = q.filter_by(enabled=True)
    rows = q.order_by(ScanPattern.id.desc()).all()
    return jsonify([{
        "id": r.id, "name": r.name, "engine": r.engine,
        "pattern": r.pattern, "enabled": r.enabled, "source": r.source, "meta": r.meta
    } for r in rows])

@bp.post("/api/patterns")
@jwt_required()
def upsert():
    if not _is_admin():
        return jsonify({"error": "forbidden"}), 403
    data = request.get_json(force=True)
    pid = data.get("id")
    if pid:
        r = ScanPattern.query.get(pid)
        if not r:
            return jsonify({"error": "not_found"}), 404
    else:
        r = ScanPattern()
        db.session.add(r)
    r.name = data["name"]
    r.engine = data.get("engine", "regex")
    r.pattern = data["pattern"]
    r.enabled = bool(data.get("enabled", True))
    r.meta = data.get("meta")
    r.source = data.get("source")
    db.session.commit()
    return jsonify({"ok": True, "id": r.id})

@bp.post("/api/patterns/toggle/<int:pid>")
@jwt_required()
def toggle(pid):
    if not _is_admin():
        return jsonify({"error": "forbidden"}), 403
    r = ScanPattern.query.get_or_404(pid)
    r.enabled = not r.enabled
    db.session.commit()
    return jsonify({"ok": True, "enabled": r.enabled})
