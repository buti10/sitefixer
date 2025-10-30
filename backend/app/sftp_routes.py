# app/sftp_routes.py
from flask import Blueprint, request, jsonify, abort
import time, posixpath, io, socket, traceback
import paramiko
import stat as pystat

bp = Blueprint("sftp", __name__, url_prefix="/api/sftp")

_SESS = {}
_TTL  = 60 * 30  # 30min

def _gc():
    now = time.time()
    for sid, s in list(_SESS.items()):
        if now - s["ts"] > _TTL:
            try:
                s["sftp"].close(); s["client"].close()
            except Exception:
                pass
            _SESS.pop(sid, None)

def _new_sid():
    return hex(int(time.time() * 1000))[2:]

# --- Debug ---
@bp.route("/debug/ping", methods=["GET"])
def debug_ping():
    host = request.args.get("host"); port = int(request.args.get("port") or 22)
    if not host: abort(400, "host fehlt")
    try:
        ip = socket.gethostbyname(host)
        with socket.create_connection((ip, port), timeout=10):
            pass
        return jsonify({"ok": True, "host": host, "ip": ip, "port": port})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 502

@bp.route("/debug/ssh_banner", methods=["GET"])
def debug_ssh_banner():
    host = request.args.get("host"); port = int(request.args.get("port") or 22)
    try:
        s = socket.create_connection((host, port), timeout=20)
        s.settimeout(20)
        banner = s.recv(1024).decode("utf-8", "ignore")
        s.close()
        return jsonify({"ok": True, "banner": banner})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 502

# --- Preflight ---
@bp.route("/session", methods=["OPTIONS"])
def _session_options():
    return ("", 200)

# --- Session öffnen ---
@bp.route("/session", methods=["POST"])
def open_session():
    _gc()
    data = request.get_json(force=True) or {}
    host = (data.get("host") or "").strip()
    port = int(data.get("port") or 22)
    user = (data.get("user") or "").strip()
    auth = (data.get("auth") or "password").lower()
    password = data.get("password") or None
    key_pem = data.get("key") or None

    if not host or not user:
        abort(400, "host und user sind erforderlich")

    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        common_kwargs = dict(
            hostname=host, port=port, username=user,
            timeout=30, banner_timeout=30, auth_timeout=30,
            allow_agent=False, look_for_keys=False,
            disabled_algorithms={},
        )

        if auth == "key":
            if not key_pem: abort(400, "key (PEM) fehlt")
            pkey = paramiko.RSAKey.from_private_key(io.StringIO(key_pem))
            client.connect(pkey=pkey, **common_kwargs)
        else:
            if not password: abort(400, "password fehlt")
            client.connect(password=password, **common_kwargs)

        sftp = client.open_sftp()
        sid = _new_sid()
        _SESS[sid] = {"client": client, "sftp": sftp, "ts": time.time()}
        return jsonify({"session_id": sid})
    except Exception as e:
        return jsonify({"error": "connect_failed", "message": str(e),
                        "trace": traceback.format_exc(limit=3)}), 502

# --- Verzeichnis auflisten ---
@bp.route("/<sid>/list", methods=["GET"])
def list_dir(sid):
    _gc()
    sess = _SESS.get(sid)
    if not sess: abort(404, "Sitzung nicht gefunden/abgelaufen")
    sftp = sess["sftp"]
    base = request.args.get("path") or "/"
    try:
        entries = []
        for a in sftp.listdir_attr(base):
            kind = "dir" if pystat.S_ISDIR(a.st_mode) else "file"
            entries.append({
                "name": a.filename,
                "path": posixpath.join(base, a.filename) if base != "/" else f"/{a.filename}",
                "type": kind,
                "size": int(a.st_size),
            })
        sess["ts"] = time.time()
        entries.sort(key=lambda x: (x["type"] != "dir", x["name"].lower()))
        return jsonify(entries)
    except FileNotFoundError:
        abort(404, "Pfad nicht gefunden")
    except Exception as e:
        return jsonify({"error": "list_failed", "message": str(e)}), 502

# --- Session schließen ---
@bp.route("/<sid>", methods=["DELETE"])
def close_session(sid):
    s = _SESS.pop(sid, None)
    if s:
        try:
            s["sftp"].close(); s["client"].close()
        except Exception:
            pass
    return jsonify({"ok": True})
