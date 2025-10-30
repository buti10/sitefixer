from flask import Blueprint, request, jsonify, make_response, current_app
from sqlalchemy import text
from passlib.context import CryptContext
from modules.common.db import get_session
from modules.users.models import User
from modules.common.security import (
    create_access_token, create_refresh_token, decode_token,
    verify_password, hash_password,   # für change-password
)
from modules.common.utils import set_auth_cookies, clear_auth_cookies
import jwt

bp = Blueprint("auth", __name__)
_pwd = CryptContext(schemes=["bcrypt_sha256", "bcrypt"], deprecated="auto")

@bp.post("/login")
def login():
    return jsonify({"ok": True, "id": 1, "email": "admin@sitefixer.de"})

# Login-Endpoint
"""
@bp.post("/login")

def login():
    log = current_app.logger
    data = request.get_json(force=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""
    s = get_session()

    row = s.execute(text(
        "SELECT id, password_hash, is_active FROM users WHERE lower(email)=:e LIMIT 1"
    ), {"e": email}).first()
    if not row:
        log.warning("AUTH no_user email=%s", email)
        return jsonify({"error": "invalid_credentials"}), 401

    uid, h, active = row
    try:
        ok = bool(h) and verify_password(password, h)  # <- ACHTUNG: Nutze nur noch verify_password!
    except Exception:
        log.exception("AUTH verify error")
        ok = False
    log.info("AUTH uid=%s active=%s ok=%s", uid, active, ok)

    if not active or not ok:
        return jsonify({"error": "invalid_credentials"}), 401

    u = s.get(User, int(uid))
    at = create_access_token(u)
    rt = create_refresh_token(u)
    resp = make_response({"ok": True})
    return set_auth_cookies(resp, at, rt)"""



@bp.post("/logout")
def logout():
    resp = make_response({"ok": True})
    return clear_auth_cookies(resp)


@bp.get("/me")
def me():
    token = request.cookies.get("access_token")
    if not token:
        return jsonify({"error": "unauthorized"}), 401
    try:
        data = decode_token(token)
        if data.get("type") != "access":
            raise Exception("wrong token")

        s = get_session()
        u = s.get(User, int(data["sub"]))
        if not u or not u.is_active:
            return jsonify({"error": "unauthorized"}), 401

        # Hier KEINE Prüfung auf token_version oder Rollen!
        return {
            "id": u.id,
            "email": u.email,
            "full_name": u.full_name,
        }
    except jwt.ExpiredSignatureError:
        return jsonify({"error": "token_expired"}), 401
    except Exception:
        return jsonify({"error": "unauthorized"}), 401



@bp.post("/refresh")
def refresh():
    rtoken = request.cookies.get("refresh_token")
    if not rtoken:
        return jsonify({"error": "unauthorized"}), 401
    try:
        data = decode_token(rtoken)
        if data.get("type") != "refresh":
            raise Exception("wrong token")

        s = get_session()
        u = s.get(User, int(data["sub"]))
        if not u or not u.is_active:
            return jsonify({"error": "unauthorized"}), 401

        tv_db = getattr(u, "token_version", None)
        if tv_db is not None and tv_db != data.get("tv"):
            return jsonify({"error": "unauthorized"}), 401

        at = create_access_token(u)
        resp = make_response({"ok": True})
        resp.set_cookie("access_token", at, httponly=True, samesite="Lax")
        return resp
    except Exception:
        return jsonify({"error": "unauthorized"}), 401


@bp.post("/change-password")
def change_password():
    token = request.cookies.get("access_token")
    if not token:
        return jsonify({"error": "unauthorized"}), 401
    try:
        data = decode_token(token)
        if data.get("type") != "access":
            raise Exception()

        s = get_session()
        u = s.get(User, int(data["sub"]))
        if not u or not u.is_active:
            return jsonify({"error": "unauthorized"}), 401

        tv_db = getattr(u, "token_version", None)
        if tv_db is not None and tv_db != data.get("tv"):
            return jsonify({"error": "unauthorized"}), 401

        body = request.get_json(force=True) or {}
        old = body.get("old_password") or ""
        new = body.get("new_password") or ""
        if not verify_password(old, u.password_hash):
            return jsonify({"error": "wrong_password"}), 400

        u.password_hash = hash_password(new)
        if hasattr(u, "token_version"):
            u.token_version = (u.token_version or 1) + 1
        s.commit()

        resp = make_response({"ok": True})
        return clear_auth_cookies(resp)
    except Exception:
        return jsonify({"error": "unauthorized"}), 401
