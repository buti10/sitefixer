from __future__ import annotations

import posixpath
from typing import Any, Dict, Optional

from app.modules.wp_repair.modules.audit.actions import create_action, quarantine_move
from app.modules.wp_repair.modules.sftp.connect import sftp_connect
from .helpers import choose_wp_config_path, patch_wp_config_debug, _read_text_sftp, _write_text_sftp


def _upsert_user_ini(sftp, wp_root: str, enable: bool) -> Dict[str, Any]:
    """
    Create/patch wp_root/user.ini (or wp_root/.user.ini depending on hosting; here: user.ini).
    Whitelist keys only.
    """
    wp_root = posixpath.normpath(wp_root)
    user_ini_path = posixpath.join(wp_root, "user.ini")
    target_log = posixpath.join(wp_root, "wp-content", "php-errors.log")

    desired = {
        "log_errors": "1" if enable else "0",
        "display_errors": "0",
        "error_log": target_log,
    }

    existing = ""
    try:
        existing = _read_text_sftp(sftp, user_ini_path, max_bytes=200_000)
    except Exception:
        existing = ""

    lines = existing.splitlines() if existing else []
    kv = {}
    for ln in lines:
        if "=" in ln and not ln.strip().startswith(";"):
            k, v = ln.split("=", 1)
            kv[k.strip()] = v.strip()

    for k, v in desired.items():
        kv[k] = v

    out_lines = ["; Sitefixer diagnostics"]
    for k in ["log_errors", "display_errors", "error_log"]:
        out_lines.append(f"{k}={kv[k]}")
    out_lines.append("; /Sitefixer diagnostics")
    out = "\n".join(out_lines) + "\n"

    _write_text_sftp(sftp, user_ini_path, out)
    return {"ok": True, "user_ini_path": user_ini_path, "php_error_log": target_log}


def diagnostics_enable(
    host: str,
    port: int,
    username: str,
    password: str,
    wp_root: str,
    *,
    ticket_id: int,
    actor_user_id: int,
    actor_name: Optional[str] = None,
    project_root: Optional[str] = None,
    enable: bool = True,
) -> Dict[str, Any]:
    wp_root = posixpath.normpath(wp_root)

    action = create_action(
        host, port, username, password, wp_root,
        fix_id="diagnostics_enable" if enable else "diagnostics_disable",
        context={"enable": bool(enable)},
        ticket_id=int(ticket_id or 0),
        actor_user_id=int(actor_user_id or 0),
        actor_name=actor_name,
        project_root=project_root,
    )

    wp_config_path = choose_wp_config_path(host, port, username, password, wp_root)
    if not wp_config_path:
        return {"ok": False, "error": "wp-config.php not found", "action_id": action["action_id"]}

    client = sftp_connect(host, port, username, password)
    sftp = client.open_sftp()
    try:
        # quarantine wp-config.php
        qm = quarantine_move(
            host, port, username, password,
            wp_root=wp_root,
            src_path=wp_config_path,
            action_id=action_id,
            kind="FILE",
        )
        wp_config_backup = qm.get("dst_path") if qm.get("ok") else None


        # write patched wp-config.php
        original = _read_text_sftp(sftp, wp_config_backup)  # read from moved backup
        patched, report = patch_wp_config_debug(original, enable=enable)
        _write_text_sftp(sftp, wp_config_path, patched)

        # upsert user.ini (quarantine if exists)
        user_ini_path = posixpath.join(wp_root, "user.ini")
        user_ini_existed = False
        try:
            sftp.stat(user_ini_path)
            user_ini_existed = True
        except Exception:
            user_ini_existed = False

        user_ini_backup = None
        if user_ini_existed:
            qm = quarantine_move(
                host, port, username, password,
                wp_root=wp_root,
                src_path=wp_config_path,
                action_id=action_id,
                kind="FILE",
            )
            user_ini_backup = qm.get("dst_path") if qm.get("ok") else None


        user_ini_result = _upsert_user_ini(sftp, wp_root, enable=enable)

        return {
            "ok": True,
            "action_id": action["action_id"],
            "wp_root": wp_root,
            "wp_config_path": wp_config_path,
            "wp_config_backup_path": wp_config_backup,
            "wp_config_patch_report": report,
            "user_ini_backup_path": user_ini_backup,
            "user_ini": user_ini_result,
            "notes": [
                "WP_DEBUG_LOG writes to wp-content/debug.log (WordPress-controlled).",
                "PHP errors are configured to log into wp-content/php-errors.log (hosting permitting).",
            ],
        }
    finally:
        try:
            sftp.close()
        except Exception:
            pass
        try:
            client.close()
        except Exception:
            pass
