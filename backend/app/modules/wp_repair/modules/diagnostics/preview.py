from __future__ import annotations

import posixpath
from typing import Any, Dict

from .helpers import choose_wp_config_path, read_text_remote, parse_table_prefix, sftp_exists


def diagnostics_preview(host: str, port: int, username: str, password: str, wp_root: str) -> Dict[str, Any]:
    wp_root = posixpath.normpath(wp_root)
    wp_config_path = choose_wp_config_path(host, port, username, password, wp_root)

    config = {}
    if wp_config_path:
        txt = read_text_remote(host, port, username, password, wp_config_path)
        config["wp_config_path"] = wp_config_path
        config["table_prefix"] = parse_table_prefix(txt)
        config["has_wp_debug"] = ("WP_DEBUG" in txt)
        config["has_wp_debug_log"] = ("WP_DEBUG_LOG" in txt)
        config["has_wp_debug_display"] = ("WP_DEBUG_DISPLAY" in txt)
    else:
        config["wp_config_path"] = None

    paths = {
        "wp_debug_log": posixpath.join(wp_root, "wp-content", "debug.log"),
        "php_errors_log": posixpath.join(wp_root, "wp-content", "php-errors.log"),
        "error_log_wp_root": posixpath.join(wp_root, "error_log"),
        "error_log_wp_content": posixpath.join(wp_root, "wp-content", "error_log"),
    }

    exists = {k: sftp_exists(host, port, username, password, p) for k, p in paths.items()}

    return {
        "ok": True,
        "wp_root": wp_root,
        "config": config,
        "paths": paths,
        "exists": exists,
        "notes": [
            "Enable will patch wp-config.php (WP_DEBUG/LOG/DISPLAY) and optionally create/update user.ini/php ini logging.",
            "Scan will read tails from logs and extract fatal/memory/parse indicators for UI.",
        ],
    }
