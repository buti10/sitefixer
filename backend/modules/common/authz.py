# modules/common/authz.py
from functools import wraps
from flask import request, jsonify
from modules.common.db import get_session
from modules.users.models import User
from modules.common.security import decode_token


def _get_user_from_request():
    """Liest den Access-Token aus dem Cookie und liefert den User oder None."""
    token = request.cookies.get("access_token")
    if not token:
        return None
    try:
        data = decode_token(token)
        if data.get("type") != "access":
            return None

        s = get_session()
        u = s.get(User, int(data["sub"]))
        if not u or not u.is_active or u.token_version != data.get("tv"):
            return None
        return u
    except Exception:
        return None


def login_required(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        u = _get_user_from_request()
        if not u:
            return jsonify({"error": "unauthorized"}), 401
        # optional: an die Request-Context hängen
        request.user = u  # type: ignore[attr-defined]
        return fn(*args, **kwargs)

    return wrapper


def require_permissions(*perm_codes: str):
    """Erzwingt, dass der eingeloggte User die angegebenen Permission-Codes hat."""
    def decorator(fn):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            u = _get_user_from_request()
            if not u:
                return jsonify({"error": "unauthorized"}), 401
            if not u.role:
                return jsonify({"error": "forbidden"}), 403

            have = {p.code for p in u.role.permissions}
            need = set(perm_codes)
            if not need.issubset(have):
                return jsonify({"error": "forbidden", "missing": list(need - have)}), 403

            request.user = u  # type: ignore[attr-defined]
            return fn(*args, **kwargs)

        return wrapper
    return decorator
