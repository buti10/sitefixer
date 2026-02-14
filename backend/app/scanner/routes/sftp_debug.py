# app/scanner/routes/sftp_debug.py
from flask import Blueprint, request, jsonify, current_app

bp = Blueprint("sftp_debug", __name__, url_prefix="/api/_debug/sftp")


@bp.get("/inspect")
def inspect_sid():
    sid = (request.args.get("sid") or "").strip()
    if not sid:
        return jsonify({"error": "sid required"}), 400

    # Import hier drin, damit es sicher im Gunicorn-Prozess passiert
    from app.scanner.sftp_adapter import get_client_by_sid

    obj = get_client_by_sid(sid)
    if obj is None:
        return jsonify({"error": "sid not found in current process", "sid": sid}), 404

    def pick_attrs(o):
        out = []
        for a in dir(o):
            al = a.lower()
            if any(k in al for k in ("sftp", "client", "conn", "wrap", "inner", "proxy", "delegate", "impl", "transport")):
                out.append(a)
        return out[:120]

    payload = {
        "sid": sid,
        "raw_type": type(obj).__name__,
        "raw_attrs_hint": pick_attrs(obj),
        "raw_has_listdir_attr": hasattr(obj, "listdir_attr"),
        "raw_has_rename": hasattr(obj, "rename"),
        "raw_has_posix_rename": hasattr(obj, "posix_rename"),
    }

    # häufige Felder prüfen
    for attr in ("sftp", "client", "sftp_client", "_client", "_sftp", "_inner", "_wrapped", "delegate", "_delegate"):
        inner = getattr(obj, attr, None)
        if inner is None:
            continue
        payload[f"{attr}_type"] = type(inner).__name__
        payload[f"{attr}_has_listdir_attr"] = hasattr(inner, "listdir_attr")
        payload[f"{attr}_has_rename"] = hasattr(inner, "rename")
        payload[f"{attr}_has_posix_rename"] = hasattr(inner, "posix_rename")
        payload[f"{attr}_has__sftp"] = hasattr(inner, "_sftp")

    return jsonify(payload), 200
