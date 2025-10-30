from flask import Blueprint, jsonify, request
from flask_jwt_extended import (
    create_access_token, create_refresh_token,
    set_access_cookies, set_refresh_cookies,
    unset_jwt_cookies, jwt_required
)
from .models import User
from argon2 import PasswordHasher

bp = Blueprint("auth", __name__)
ph = PasswordHasher()

@bp.post("/login")
def login():
    d = request.get_json(force=True)
    u = User.query.filter_by(email=d["email"].strip().lower()).first()
    if not u: return jsonify({"msg":"bad creds"}), 401
    try: ph.verify(u.password_hash, d["password"])
    except: return jsonify({"msg":"bad creds"}), 401

    access  = create_access_token(identity=str(u.id), additional_claims={"role": u.role})
    refresh = create_refresh_token(identity=str(u.id))
    resp = jsonify(ok=True)
    set_access_cookies(resp, access)
    set_refresh_cookies(resp, refresh)

    return resp, 200

@bp.post("/refresh")
@jwt_required(refresh=True)
def refresh():
    from flask_jwt_extended import get_jwt_identity
    access = create_access_token(identity=str(get_jwt_identity()))
    resp = jsonify(ok=True)
    set_access_cookies(resp, access)
    return resp, 200

@bp.post("/logout")
def logout():
    resp = jsonify(ok=True)
    unset_jwt_cookies(resp)
    return resp, 200
