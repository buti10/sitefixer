from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from .extensions import db
from .models import Setting

bp = Blueprint("settings", __name__)

@bp.get("/")
@jwt_required()
def get_settings():
    rows = Setting.query.order_by(Setting.key).all()
    return jsonify({s.key: s.value for s in rows})

@bp.post("/")
@jwt_required()
def save_settings():
    data = request.get_json(force=True) or {}
    for k, v in data.items():
        s = Setting.query.filter_by(key=k).first()
        if not s:
            s = Setting(key=k, value=v)
            db.session.add(s)
        else:
            s.value = v
    db.session.commit()
    return jsonify({"ok": True})
