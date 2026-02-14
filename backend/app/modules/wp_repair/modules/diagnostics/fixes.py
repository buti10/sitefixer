from __future__ import annotations

import posixpath
import re
from typing import Any, Dict, Optional

from app.modules.wp_repair.modules.audit.actions import create_action, quarantine_move
from app.modules.wp_repair.modules.sftp.connect import sftp_connect
from .helpers import choose_wp_config_path, _read_text_sftp, _write_text_sftp


def _patch_wp_memory_limit(text: str, memory: str) -> str:
    # replace existing define or insert before That's all
    pat = re.compile(r"define\(\s*['\"]WP_MEMORY_LIMIT['\"]\s*,\s*([^)]+)\)\s*;", re.IGNORECASE)
    if pat.search(text):
        return pat.sub(f"define('WP_MEMORY_LIMIT', '{memory}');", text)

    block = f"\n/* Sitefixer diagnostics */\ndefine('WP_MEMORY_LIMIT', '{memory}');\n/* /Sitefixer diagnostics */\n"
    marker = "/* That's all, stop editing! */"
    idx = text.find(marker)
    if idx != -1:
        return text[:idx] + block + text[idx:]
    return text + block


def _disable_plugin_folder(sftp, wp_root: str, plugin_slug: str) -> Dict[str, Any]:
    wp_root = posixpath.normpath(wp_root)
    plugin_dir = posixpath.join(wp_root, "wp-content", "plugins", plugin_slug)
    disabled_dir = posixpath.join(wp_root, "wp-content", "plugins", f"_disabled_{plugin_slug}")

    # collision-safe
    try:
        sftp.stat(disabled_dir)
        disabled_dir = disabled_dir + "_1"
    except Exception:
        pass

    sftp.rename(plugin_dir, disabled_dir)
    return {"ok": True, "from": plugin_dir, "to": disabled_dir}


def diagnostics_apply_fix(
    host: str,
    port: int,
    username: str,
    password: str,
    wp_root: str,
    *,
    fix_id: str,
    params: Dict[str, Any],
    ticket_id: int,
    actor_user_id: int,
    actor_name: Optional[str] = None,
    project_root: Optional[str] = None,
) -> Dict[str, Any]:
    wp_root = posixpath.normpath(wp_root)

    action = create_action(
        host, port, username, password, wp_root,
        fix_id=f"diagnostics_{fix_id}",
        context={"fix_id": fix_id, "params": params or {}},
        ticket_id=int(ticket_id or 0),
        actor_user_id=int(actor_user_id or 0),
        actor_name=actor_name,
        project_root=project_root,
    )

    client = sftp_connect(host, port, username, password)
    sftp = client.open_sftp()
    try:
        if fix_id == "set_wp_memory_limit":
            mem = str((params or {}).get("memory") or "256M")
            wp_config_path = choose_wp_config_path(host, port, username, password, wp_root)
            if not wp_config_path:
                return {"ok": False, "error": "wp-config.php not found", "action_id": action["action_id"]}

            qm = quarantine_move(
                host, port, username, password,
                wp_root=wp_root,
                src_path=wp_config_path,
                action_id=action_id,
                kind="FILE",
            )
            wp_config_backup = qm.get("dst_path") if qm.get("ok") else None
            backup_path = qm["dst_path"]


            original = _read_text_sftp(sftp, wp_config_backup)
            patched = _patch_wp_memory_limit(original, mem)
            _write_text_sftp(sftp, wp_config_path, patched)

            return {
                "ok": True,
                "action_id": action["action_id"],
                "result": {"ok": True, "wp_config_path": wp_config_path, "wp_config_backup_path": wp_config_backup, "memory": mem},
            }

        if fix_id == "disable_plugin":
            plugin_slug = str((params or {}).get("plugin_slug") or "").strip()
            if not plugin_slug:
                return {"ok": False, "error": "plugin_slug missing", "action_id": action["action_id"]}

            # we do NOT quarantine_move here because it's a directory rename; just rename via sftp
            res = _disable_plugin_folder(sftp, wp_root, plugin_slug)
            return {"ok": True, "action_id": action["action_id"], "result": res}

        return {"ok": False, "error": f"Unknown fix_id: {fix_id}", "action_id": action["action_id"]}

    finally:
        try:
            sftp.close()
        except Exception:
            pass
        try:
            client.close()
        except Exception:
            pass
