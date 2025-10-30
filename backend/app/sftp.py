# app/sftp.py
from flask import Blueprint, request, jsonify, abort
import paramiko, time, os, threading, base64
from uuid import uuid4
from app.repair.session_bridge import register_client, deregister_client

bp = Blueprint("sftp", __name__, url_prefix="/api/sftp")

# sehr einfacher In-Memory-Store (für Prod: Redis o.ä.)
_SESS = {}
_TTL = 15 * 60  # 15min

def _cleanup():
    now = time.time()
    for sid, s in list(_SESS.items()):
        if now - s["ts"] > _TTL:
            try:
                s["client"].close()
            except Exception:
                pass
            _SESS.pop(sid, None)

def _mk_sid():
    return base64.urlsafe_b64encode(uuid4().bytes).decode().rstrip("=")

def _connect(host, username, password, port=22):
    client = paramiko.Transport((host, int(port)))
    client.connect(username=username, password=password)
    return client

# app/sftp.py
@bp.post("/session")
def create_session():
    data = request.get_json(silent=True) or request.form.to_dict() or request.args.to_dict() or {}
    host = (data.get("host") or data.get("ftp_host") or "").strip()
    username = (data.get("username") or data.get("user") or data.get("ftp_user") or "").strip()
    password = (data.get("password") or data.get("pass") or data.get("ftp_pass") or "")
    port = int(data.get("port") or 22)
    if not host or not username:
        return ("host und user sind erforderlich", 400)

    try:
        transport = paramiko.Transport((host, port))
        transport.connect(username=username, password=password)
        sftp = paramiko.SFTPClient.from_transport(transport)
    except paramiko.AuthenticationException:
        return ("Auth fehlgeschlagen", 401)
    except Exception as e:
        current_app.logger.exception("SFTP connect failed: %r", e)
        return (f"Connect-Fehler: {e}", 400)

    sid = str(uuid4())
    _SESS[sid] = {"client": transport, "sftp": sftp, "ts": time.time()}
    register_client(sid, sftp)
    return jsonify({"sid": sid})


@bp.get("/<sid>/list")
def list_dir(sid):
    sess = _SESS.get(sid)
    if not sess: abort(404, "session not found")
    path = request.args.get("path") or "/"
    try:
        items = []
        for a in sess["sftp"].listdir_attr(path):
            items.append({
                "name": a.filename,
                "path": (path.rstrip("/") + "/" + a.filename) if path != "/" else ("/" + a.filename),
                "type": "dir" if paramiko.S_ISDIR(a.st_mode) else "file",
                "size": getattr(a, "st_size", 0),
                "mtime": getattr(a, "st_mtime", 0),
            })
        sess["ts"] = time.time()
        return jsonify({"items": items})
    except Exception as e:
        abort(400, f"list failed: {e}")

@bp.delete("/<sid>")
def close_session(sid):
    sess = _SESS.pop(sid, None)
    if not sess: abort(404, "session not found")
    deregister_client(sid)
    try:
        sess["sftp"].close()
        sess["client"].close()
    except Exception:
        pass
    return jsonify({"ok": True})
