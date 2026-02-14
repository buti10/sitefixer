from __future__ import annotations

import time
from datetime import datetime
import re
from typing import Callable, Any, Dict, Tuple

import paramiko

# -----------------------------
# SFTP helpers
# -----------------------------
def _norm_root(p: str) -> str:
    p = (p or "/").strip()
    if not p.startswith("/"):
        p = "/" + p
    if not p.endswith("/"):
        p += "/"
    return p

def _join(root: str, rel: str) -> str:
    return _norm_root(root) + rel.lstrip("/")

def _now_stamp() -> str:
    return datetime.utcnow().strftime("%Y%m%d-%H%M%S")

def _sftp_connect(host: str, port: int, user: str, password: str):
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(hostname=host, port=port, username=user, password=password, timeout=25)
    sftp = client.open_sftp()
    return client, sftp

def _exists(sftp, path: str) -> bool:
    try:
        sftp.stat(path)
        return True
    except Exception:
        return False

def _size(sftp, path: str) -> int:
    return int(sftp.stat(path).st_size)

def _read_text(sftp, path: str) -> str:
    with sftp.open(path, "r") as f:
        data = f.read()
        if isinstance(data, (bytes, bytearray)):
            return data.decode("utf-8", "replace")
        return str(data)

def _write_text_atomic(sftp, path: str, content: str):
    tmp = f"{path}.tmp.{int(time.time())}"
    with sftp.open(tmp, "w") as f:
        f.write(content)
    try:
        sftp.remove(path)
    except Exception:
        pass
    sftp.rename(tmp, path)
def _now_stamp() -> str:
    return datetime.utcnow().strftime("%Y%m%d-%H%M%S")
def _backup_copy(sftp, path: str) -> str:
    # copy by read+write (rename wäre riskant)
    if not _exists(sftp, path):
        return ""
    bkp = f"{path}.bak.{_now_stamp()}"
    data = _read_text(sftp, path)
    _write_text_atomic(sftp, bkp, data)
    try:
        sftp.chmod(bkp, 0o644)
    except Exception:
        pass
    return bkp

# -----------------------------
# wp-config patching
# -----------------------------
def _set_define_bool(text: str, key: str, value: bool) -> Tuple[str, bool]:
    key_u = key.upper()
    desired = "true" if value else "false"
    pattern = re.compile(rf"(define\(\s*['\"]{re.escape(key_u)}['\"]\s*,\s*)(true|false)(\s*\)\s*;)", re.I)

    if pattern.search(text):
        new_text = pattern.sub(rf"\1{desired}\3", text, count=1)
        return new_text, (new_text != text)

    insert = f"define('{key_u}', {desired});\n"
    marker = "/* That's all, stop editing! Happy publishing. */"
    if marker in text:
        return text.replace(marker, insert + marker, 1), True

    return text.rstrip() + "\n" + insert, True

# -----------------------------
# Fix implementations
# -----------------------------
def fix_debug_disable(host: str, port: int, user: str, password: str, wp_root: str, params: dict) -> Dict[str, Any]:
    wp_root = _norm_root(wp_root)
    wp_config = _join(wp_root, "wp-config.php")

    client = None
    try:
        client, sftp = _sftp_connect(host, port, user, password)
        if not _exists(sftp, wp_config):
            return {"ok": False, "changed": False, "msg": f"wp-config.php nicht gefunden: {wp_config}"}

        original = _read_text(sftp, wp_config)
        backup = _backup_copy(sftp, wp_config)

        patched = original
        changed_any = False

        patched, ch = _set_define_bool(patched, "WP_DEBUG", False); changed_any |= ch
        patched, ch = _set_define_bool(patched, "WP_DEBUG_LOG", False); changed_any |= ch
        patched, ch = _set_define_bool(patched, "WP_DEBUG_DISPLAY", False); changed_any |= ch

        if changed_any:
            _write_text_atomic(sftp, wp_config, patched)

        return {
            "ok": True,
            "changed": bool(changed_any),
            "fix_id": "debug_disable",
            "backup": backup,
            "wp_config": wp_config,
            "applied": {"WP_DEBUG": False, "WP_DEBUG_LOG": False, "WP_DEBUG_DISPLAY": False},
        }
    finally:
        try:
            if client:
                client.close()
        except Exception:
            pass

def fix_debug_rotate(host: str, port: int, user: str, password: str, wp_root: str, params: dict) -> Dict[str, Any]:
    wp_root = _norm_root(wp_root)
    log_path = _join(wp_root, "wp-content/debug.log")

    client = None
    try:
        client, sftp = _sftp_connect(host, port, user, password)
        if not _exists(sftp, log_path):
            return {"ok": False, "changed": False, "msg": f"debug.log nicht gefunden: {log_path}"}

        size_before = _size(sftp, log_path)
        rotated = f"{log_path}.{_now_stamp()}"
        sftp.rename(log_path, rotated)

        _write_text_atomic(sftp, log_path, "")
        try:
            sftp.chmod(log_path, 0o644)
        except Exception:
            pass

        return {
            "ok": True,
            "changed": True,
            "fix_id": "debug_rotate",
            "log_path": log_path,
            "rotated_to": rotated,
            "size_before": size_before,
        }
    finally:
        try:
            if client:
                client.close()
        except Exception:
            pass

def fix_permissions(host: str, port: int, user: str, password: str, wp_root: str, params: dict) -> Dict[str, Any]:
    """
    Normalisiert minimal:
    - wp-config.php -> 0640 oder 0644 (hier 0644, weil Shared Hosting oft Probleme macht)
    - wp-content, wp-admin, wp-includes -> 0755
    - index.php, .htaccess (falls vorhanden) -> 0644
    """
    wp_root = _norm_root(wp_root)
    targets = [
        ("dir", _join(wp_root, "wp-content"), 0o755),
        ("dir", _join(wp_root, "wp-admin"), 0o755),
        ("dir", _join(wp_root, "wp-includes"), 0o755),
        ("file", _join(wp_root, "wp-config.php"), 0o644),
        ("file", _join(wp_root, "index.php"), 0o644),
        ("file", _join(wp_root, ".htaccess"), 0o644),
    ]

    changed = []
    missing = []

    client = None
    try:
        client, sftp = _sftp_connect(host, port, user, password)
        for kind, path, mode in targets:
            if not _exists(sftp, path):
                missing.append(path)
                continue
            try:
                sftp.chmod(path, mode)
                changed.append({"path": path, "mode": oct(mode)})
            except Exception:
                # shared hosting/permissions können chmod blocken -> weiter
                pass

        return {
            "ok": True,
            "changed": len(changed) > 0,
            "fix_id": "permissions_fix",
            "changed_items": changed,
            "missing": missing,
        }
    finally:
        try:
            if client:
                client.close()
        except Exception:
            pass

# -----------------------------
# Registry + dispatcher
# -----------------------------



def apply_fix(*, fix_id: str, host: str, port: int, user: str, password: str, wp_root: str, params: dict) -> Dict[str, Any]:
    fn = _FIXES[fix_id]  # KeyError -> 404 in route
    return fn(host, port, user, password, wp_root, params)


def fix_htaccess_reset(host: str, port: int, user: str, password: str, wp_root: str, params: dict) -> Dict[str, Any]:
    """
    Reset .htaccess to standard WP rewrite rules (safe baseline).
    Creates a backup copy if existing.
    """
    wp_root = _norm_root(wp_root)
    htaccess_path = _join(wp_root, ".htaccess")

    default_htaccess = (
        "# BEGIN WordPress\n"
        "<IfModule mod_rewrite.c>\n"
        "RewriteEngine On\n"
        "RewriteRule .* - [E=HTTP_AUTHORIZATION:%{HTTP:Authorization}]\n"
        "RewriteBase /\n"
        "RewriteRule ^index\\.php$ - [L]\n"
        "RewriteCond %{REQUEST_FILENAME} !-f\n"
        "RewriteCond %{REQUEST_FILENAME} !-d\n"
        "RewriteRule . /index.php [L]\n"
        "</IfModule>\n"
        "# END WordPress\n"
    )

    client = None
    try:
        client, sftp = _sftp_connect(host, port, user, password)

        backup = ""
        if _exists(sftp, htaccess_path):
            backup = _backup_copy(sftp, htaccess_path)

        _write_text_atomic(sftp, htaccess_path, default_htaccess)
        try:
            sftp.chmod(htaccess_path, 0o644)
        except Exception:
            pass

        return {
            "ok": True,
            "changed": True,
            "fix_id": "htaccess_reset",
            "htaccess": htaccess_path,
            "backup": backup,
        }
    finally:
        try:
            if client:
                client.close()
        except Exception:
            pass
_FIXES = {
    "debug_disable": fix_debug_disable,
    "debug_rotate": fix_debug_rotate,
    "permissions_fix": fix_permissions,
    "htaccess_reset": fix_htaccess_reset,
}