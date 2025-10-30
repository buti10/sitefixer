# app/scanner/routes/sftp_routes.py
from __future__ import annotations
from flask import Blueprint, request, jsonify
import uuid, paramiko, stat

bp = Blueprint("sftp_proxy", __name__, url_prefix="/api/sftp")

SESSIONS: dict[str, dict] = {}

def _normalize(p: str) -> str:
    return ("/" + (p or "/")).replace("//", "/")

def _open_sftp(sess: dict):
    """SSH+SFTP öffnen; Caller schließt in finally."""
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=sess["host"].strip(),
        port=sess.get("port", 22),
        username=sess["username"],
        password=sess.get("password", ""),
        look_for_keys=False,
        allow_agent=False,
        timeout=15,
        banner_timeout=15,
        auth_timeout=15,
    )
    return client, client.open_sftp()

@bp.post("/session")
def create_session():
    data = request.get_json(force=True) or {}
    host = (data.get("host") or "").strip()
    username = data.get("username") or ""
    password = data.get("password") or ""
    port = int(data.get("port") or 22)
    if not host or not username:
        return jsonify({"message": "host und username erforderlich"}), 422
    sid = str(uuid.uuid4())
    SESSIONS[sid] = {"host": host, "username": username, "password": password, "port": port}
    return jsonify({"sid": sid})

@bp.get("/tree")
def list_tree():
    sid  = request.args.get("sid")
    path = _normalize(request.args.get("path", "/"))
    sess = SESSIONS.get(sid)
    if not sess:
        return jsonify({"message": "invalid sid"}), 400

    client = sftp = None
    try:
        client, sftp = _open_sftp(sess)

        # 1. Versuch: path wie geliefert
        try:
            entries = sftp.listdir_attr(path if path != "/" else ".")
        except FileNotFoundError:
            # 2. Versuch: ohne führenden Slash (IONOS chroot)
            alt = path.lstrip("/") or "."
            entries = sftp.listdir_attr(alt)

        children = []
        for e in entries:
            is_dir = stat.S_ISDIR(e.st_mode)
            children.append({
                "name": e.filename,
                "type": "dir" if is_dir else "file",
                "size": getattr(e, "st_size", 0) or 0,
                "mtime": int(getattr(e, "st_mtime", 0) or 0),
                "path": _normalize(path.rstrip("/") + "/" + e.filename),
            })

        children.sort(key=lambda x: (0 if x["type"] == "dir" else 1, x["name"].lower()))
        return jsonify({"path": path, "children": children})

    except Exception as ex:
        return jsonify({"message": str(ex)}), 500
    finally:
        try:
            if sftp: sftp.close()
        except: pass
        try:
            if client: client.close()
        except: pass

@bp.post("/close")
def close_session():
    data = request.get_json(force=True) or {}
    sid = data.get("sid")
    if sid in SESSIONS:
        del SESSIONS[sid]
    return jsonify({"ok": True})
