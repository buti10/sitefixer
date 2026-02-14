from __future__ import annotations

from datetime import datetime, timedelta
from flask import Blueprint, jsonify, request
from flask_jwt_extended import (
    create_access_token,
    get_jwt,
    get_jwt_identity,
    jwt_required,
)
from argon2 import PasswordHasher

from .models import User
from .extensions import db  # falls du db dort hast; sonst anpassen

bp_api = Blueprint("auth_api", __name__)
ph = PasswordHasher()

# ---------------------------------------
# Optional: Audit Log Model (minimal)
# ---------------------------------------
# Wenn du noch kein Audit-Table hast, kannst du das erstmal weglassen.
# Oder du loggst erstmal nur via logger.
def audit(event: str, ok: bool, user_id: str | None = None, meta: dict | None = None):
    # Minimal-Variante: server log
    # Ersetze später durch DB-Tabelle audit_log
    try:
        from flask import current_app
        current_app.logger.info("AUDIT %s ok=%s user_id=%s meta=%s", event, ok, user_id, meta or {})
    except Exception:
        pass


@bp_api.post("/token")
def token_login():
    """
    Tool/API Login (Appsmith etc.)
    Returns: {access_token, token_type, expires_in, role}
    """
    d = request.get_json(silent=True) or {}
    email = (d.get("email") or "").strip().lower()
    password = d.get("password") or ""

    if not email or not password:
        audit("auth.token_login", False, None, {"reason": "missing_fields"})
        return jsonify({"msg": "missing email/password"}), 400

    u = User.query.filter_by(email=email).first()
    if not u or not getattr(u, "is_active", True):
        audit("auth.token_login", False, None, {"email": email, "reason": "bad_creds_or_inactive"})
        return jsonify({"msg": "bad creds"}), 401

    try:
        ph.verify(u.password_hash, password)
    except Exception:
        audit("auth.token_login", False, str(u.id) if u else None, {"email": email, "reason": "bad_password"})
        return jsonify({"msg": "bad creds"}), 401

    # Optional: Token TTL (z.B. 8h)
    expires = timedelta(hours=8)
    role = getattr(u, "role", "viewer")

    access = create_access_token(
        identity=str(u.id),
        additional_claims={"role": role},
        expires_delta=expires,
    )

    audit("auth.token_login", True, str(u.id), {"role": role})

    return jsonify(
        access_token=access,
        token_type="bearer",
        expires_in=int(expires.total_seconds()),
        role=role,
        user_id=str(u.id),
    ), 200


@bp_api.get("/me")
@jwt_required()
def me():
    """
    Useful for Appsmith to verify token and get role/user info.
    """
    uid = get_jwt_identity()
    claims = get_jwt() or {}
    role = claims.get("role")

    u = User.query.get(uid)
    if not u:
        return jsonify({"msg": "not found"}), 404

    return jsonify(
        id=str(u.id),
        email=u.email,
        name=getattr(u, "name", None),
        role=role or getattr(u, "role", None),
        is_active=getattr(u, "is_active", True),
    ), 200
