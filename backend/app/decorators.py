# /var/www/sitefixer/backend/app/decorators.py
from functools import wraps
from flask import jsonify
from flask_jwt_extended import jwt_required as _jwt_required, get_jwt

def jwt_required(fn):
    return _jwt_required()(fn)

def roles_required(*roles):
    def deco(fn):
        @_jwt_required()
        @wraps(fn)
        def wrap(*a, **k):
            claims = get_jwt() or {}
            role = claims.get("role")
            if roles and role not in roles:
                return jsonify({"msg":"forbidden"}), 403
            return fn(*a, **k)
        return wrap
    return deco
