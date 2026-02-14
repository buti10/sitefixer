from __future__ import annotations

from flask import Blueprint, request, jsonify
from .sftp_service import sftp_connect
from .explorer import list_dir
from .wp_detect import find_wp_projects
from .wp_service import run_wp_diagnose
from .wp_fixes import apply_fix
from .http_diagnose import run_http_diagnose

import re
import time
from datetime import datetime


bp = Blueprint(
    "repair_beta",
    __name__,
    url_prefix="/api/repair-beta"
)

@bp.get("/ping")
def ping():
    return jsonify({
        "ok": True,
        "module": "repair_beta"
    })

@bp.post("/explorer/list")
def explorer_list():
    data = request.json

    with sftp_connect(
        data["host"],
        data["user"],
        data["password"],
        data.get("port", 22)
    ) as sftp:
        items = list_dir(sftp, data.get("path", "/"))

    return jsonify({
        "ok": True,
        "items": items
    })

@bp.post("/wp/projects")
def wp_projects():
    data = request.get_json(force=True) or {}
    host = (data.get("host") or "").strip()
    user = (data.get("user") or "").strip()
    password = data.get("password") or ""
    port = int(data.get("port") or 22)
    start_path = data.get("start_path") or "/"
    max_depth = int(data.get("max_depth") or 4)

    if not host or not user or not password:
        return jsonify(ok=False, msg="host/user/password fehlen"), 400

    with sftp_connect(host=host, user=user, password=password, port=port) as sftp:
        roots = find_wp_projects(sftp, start_path=start_path, max_depth=max_depth)
        return jsonify(
            ok=True,
            projects=[
                {
                    "path": r.path,
                    "version": r.version,
                    "label": f"{r.path} (WP {r.version})" if r.version else r.path,
                }
                for r in roots
            ],
        )
@bp.post("/wp/diagnose")
def wp_diagnose():
    data = request.get_json(force=True) or {}

    host = (data.get("host") or "").strip()
    user = (data.get("user") or "").strip()
    password = data.get("password") or ""
    port = int(data.get("port") or 22)
    wp_root = (data.get("wp_root") or "").strip() or "/"
    site_url = (data.get("site_url") or "").strip() or None

    if not host or not user or not password or not wp_root:
        return jsonify({"ok": False, "msg": "host/user/password/wp_root erforderlich"}), 400

    try:
        out = run_wp_diagnose(host=host, port=port, user=user, password=password, wp_root=wp_root, site_url=site_url)
        return jsonify(out)
    except Exception as e:
        return jsonify({"ok": False, "msg": f"Diagnose fehlgeschlagen: {type(e).__name__}"}), 500

    
@bp.post("/wp/fix/apply")
def wp_fix_apply():
    body = request.get_json(force=True) or {}

    host = (body.get("host") or "").strip()
    user = (body.get("user") or "").strip()
    password = body.get("password") or ""
    port = int(body.get("port") or 22)
    wp_root = (body.get("wp_root") or "").strip() or "/"
    fix_id = (body.get("fix_id") or "").strip()

    if not host or not user or not password or not wp_root or not fix_id:
        return jsonify(ok=False, msg="host/user/password/wp_root/fix_id fehlen"), 400

    try:
        result = apply_fix(
            fix_id=fix_id,
            host=host,
            port=port,
            user=user,
            password=password,
            wp_root=wp_root,
            params=body.get("params") or {},
        )
        return jsonify(result)
    except KeyError:
        return jsonify(ok=False, msg=f"Unbekannter Fix: {fix_id}"), 404
    except Exception as e:
        return jsonify(ok=False, msg=f"Fix fehlgeschlagen: {type(e).__name__}"), 500




# -----------------------------
# Helpers (SFTP read/write, path join, safe edits)
# -----------------------------
def _norm_root(p: str) -> str:
    if not p:
        return "/"
    if not p.startswith("/"):
        p = "/" + p
    if not p.endswith("/"):
        p += "/"
    return p


def _join(root: str, rel: str) -> str:
    root = _norm_root(root)
    rel = rel.lstrip("/")
    return root + rel


def _now_stamp() -> str:
    return datetime.utcnow().strftime("%Y%m%d-%H%M%S")


# --- Replace this with your existing connector if you already have one ---
def _sftp_connect(host: str, port: int, user: str, password: str):
    import paramiko  # make sure it's installed on backend
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=host, port=port, username=user, password=password, timeout=20)
    sftp = client.open_sftp()
    return client, sftp


def _sftp_read_text(sftp, path: str) -> str:
    with sftp.open(path, "r") as f:
        data = f.read()
        if isinstance(data, bytes):
            return data.decode("utf-8", "replace")
        return data


def _sftp_write_text_atomic(sftp, path: str, content: str):
    tmp = f"{path}.tmp.{int(time.time())}"
    with sftp.open(tmp, "w") as f:
        f.write(content)
    # atomic-ish replace
    try:
        sftp.remove(path)
    except Exception:
        pass
    sftp.rename(tmp, path)


def _sftp_exists(sftp, path: str) -> bool:
    try:
        sftp.stat(path)
        return True
    except Exception:
        return False


def _sftp_size(sftp, path: str) -> int:
    return int(sftp.stat(path).st_size)


def _backup_file(sftp, path: str) -> str:
    if not _sftp_exists(sftp, path):
        return ""
    bkp = f"{path}.bak.{_now_stamp()}"
    sftp.rename(path, bkp)
    # danach schreibt man die neue Datei wieder nach "path"
    return bkp


# -----------------------------
# wp-config parsing + patching
# -----------------------------
_CONST_RE = re.compile(r"define\(\s*['\"](?P<k>[A-Z0-9_]+)['\"]\s*,\s*(?P<v>[^)]+)\)\s*;", re.I)

def _parse_wp_config_constants(text: str) -> dict:
    out = {}
    for m in _CONST_RE.finditer(text):
        k = m.group("k").upper()
        v_raw = m.group("v").strip()
        v_norm = v_raw.lower()
        if v_norm in ("true", "false"):
            out[k] = (v_norm == "true")
        else:
            out[k] = v_raw
    return out


def _set_define_bool(text: str, key: str, value: bool) -> tuple[str, bool]:
    """
    Setzt define('KEY', true/false). Wenn KEY existiert → ersetzen. Sonst hinzufügen.
    Fügt vor "/* That's all, stop editing! */" ein, sonst am Ende.
    """
    key_u = key.upper()
    desired = "true" if value else "false"

    # replace existing define
    pattern = re.compile(rf"(define\(\s*['\"]{re.escape(key_u)}['\"]\s*,\s*)(true|false)(\s*\)\s*;)", re.I)
    if pattern.search(text):
        new_text = pattern.sub(rf"\1{desired}\3", text, count=1)
        return new_text, (new_text != text)

    # add new define
    insert_line = f"define('{key_u}', {desired});\n"
    marker = "/* That's all, stop editing! Happy publishing. */"
    if marker in text:
        new_text = text.replace(marker, insert_line + marker, 1)
        return new_text, True

    # fallback: append
    return text.rstrip() + "\n" + insert_line, True


# -----------------------------
# FIX: Disable debug logging (real fix)
# -----------------------------
@bp.post("/fix/debug-log/disable")
def fix_disable_debug_log():
    body = request.get_json(force=True) or {}
    host = body.get("host")
    port = int(body.get("port", 22))
    user = body.get("user")
    password = body.get("password")
    wp_root = _norm_root(body.get("wp_root") or "/")

    if not all([host, user, password, wp_root]):
        return jsonify(ok=False, msg="host/user/password/wp_root fehlen"), 400

    wp_config = _join(wp_root, "wp-config.php")

    client = None
    try:
        client, sftp = _sftp_connect(host, port, user, password)
        if not _sftp_exists(sftp, wp_config):
            return jsonify(ok=False, msg=f"wp-config.php nicht gefunden: {wp_config}"), 404

        original = _sftp_read_text(sftp, wp_config)
        bkp = _backup_file(sftp, wp_config)

        # Setze best practice:
        # - WP_DEBUG false
        # - WP_DEBUG_LOG false
        # - WP_DEBUG_DISPLAY false
        patched = original
        changed_any = False

        patched, ch = _set_define_bool(patched, "WP_DEBUG", False); changed_any |= ch
        patched, ch = _set_define_bool(patched, "WP_DEBUG_LOG", False); changed_any |= ch
        patched, ch = _set_define_bool(patched, "WP_DEBUG_DISPLAY", False); changed_any |= ch

        _sftp_write_text_atomic(sftp, wp_config, patched)

        return jsonify(
            ok=True,
            changed=bool(changed_any),
            backup=bkp,
            applied={"WP_DEBUG": False, "WP_DEBUG_LOG": False, "WP_DEBUG_DISPLAY": False},
            wp_config=wp_config,
        )
    except Exception as e:
        return jsonify(ok=False, msg=str(e)), 500
    finally:
        try:
            if client:
                client.close()
        except Exception:
            pass


# -----------------------------
# FIX: Rotate + truncate debug.log (ops fix)
# -----------------------------
@bp.post("/fix/debug-log/rotate")
def fix_rotate_debug_log():
    body = request.get_json(force=True) or {}
    host = body.get("host")
    port = int(body.get("port", 22))
    user = body.get("user")
    password = body.get("password")
    wp_root = _norm_root(body.get("wp_root") or "/")

    if not all([host, user, password, wp_root]):
        return jsonify(ok=False, msg="host/user/password/wp_root fehlen"), 400

    log_path = _join(wp_root, "wp-content/debug.log")
    client = None
    try:
        client, sftp = _sftp_connect(host, port, user, password)

        if not _sftp_exists(sftp, log_path):
            return jsonify(ok=False, msg=f"debug.log nicht gefunden: {log_path}"), 404

        size_before = _sftp_size(sftp, log_path)
        rotated = f"{log_path}.{_now_stamp()}"
        sftp.rename(log_path, rotated)

        # neues leeres debug.log anlegen
        _sftp_write_text_atomic(sftp, log_path, "")
        # optional: Permissions setzen (oft 0644)
        try:
            sftp.chmod(log_path, 0o644)
        except Exception:
            pass

        return jsonify(
            ok=True,
            changed=True,
            rotated_to=rotated,
            size_before=size_before,
            log_path=log_path,
        )
    except Exception as e:
        return jsonify(ok=False, msg=str(e)), 500
    finally:
        try:
            if client:
                client.close()
        except Exception:
            pass
@bp.post("/http/diagnose")
def http_diagnose():
    data = request.get_json(force=True) or {}
    domain = (data.get("domain") or "").strip()
    timeout = int(data.get("timeout") or 15)
    verify_tls = bool(data.get("verify_tls", True))

    out = run_http_diagnose(domain, timeout=timeout, verify_tls=verify_tls)
    code = 200 if out.get("ok") else 400
    return jsonify(out), code
