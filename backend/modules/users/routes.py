from flask import Blueprint, request, jsonify
from modules.common.db import get_session
from modules.users.models import User
from modules.roles.models import Role
from modules.common.security import hash_password

bp = Blueprint("users", __name__)

@bp.get("/")
def list_users():
    s = get_session()
    data = [
        {
            "id": u.id,
            "email": u.email,
            "full_name": u.full_name,
            "is_active": u.is_active,
            "role": u.role.name if u.role else None,
        }
        for u in s.query(User).order_by(User.id.desc()).all()
    ]
    return jsonify(data)

@bp.post("/")
def create_user():
    s = get_session()
    body = request.get_json(force=True)
    email = (body.get("email") or "").strip().lower()
    full_name = body.get("full_name") or ""
    password = body.get("password") or ""
    role_name = body.get("role") or None

    if not email or not password:
        return {"error": "email_and_password_required"}, 400

    if s.query(User).filter_by(email=email).first():
        return {"error": "email_taken"}, 400

    role = s.query(Role).filter_by(name=role_name).one_or_none() if role_name else None

    u = User(
        email=email,
        full_name=full_name,
        password_hash=hash_password(password),
        role=role,
        is_active=True,
    )
    s.add(u)
    s.commit()
    return {"ok": True, "id": u.id}
