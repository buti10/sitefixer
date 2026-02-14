from __future__ import annotations

import posixpath
from typing import Any, Dict, Optional

from ..sftp.connect import sftp_connect
from .helpers import (
    find_wp_config_path,
    read_remote_text,
    parse_wp_config_info,
    ensure_site_base_url,
    build_repair_url,
)


def db_repair_preview(
    host: str,
    port: int,
    username: str,
    password: str,
    wp_root: str,
    *,
    domain: Optional[str] = None,
) -> Dict[str, Any]:
    """Preview database repair preconditions.

    - Locates wp-config.php
    - Reads WP_ALLOW_REPAIR state
    - Computes repair endpoint URL
    """
    wp_root = posixpath.normpath(wp_root)
    base_url = ensure_site_base_url(domain or "")
    repair_url = build_repair_url(base_url) if base_url else None

    client = sftp_connect(host, port, username, password)
    sftp = client.open_sftp()
    try:
        wp_config_path = find_wp_config_path(sftp, wp_root)
        if not wp_config_path:
            return {
                "ok": False,
                "error": "wp-config.php not found (checked wp_root and its parent)",
                "wp_root": wp_root,
                "site_base_url": base_url or None,
                "repair_url": repair_url,
            }

        txt = read_remote_text(sftp, wp_config_path)
        info = parse_wp_config_info(txt)

        return {
            "ok": True,
            "wp_root": wp_root,
            "wp_config_path": wp_config_path,
            "site_base_url": base_url or None,
            "repair_url": repair_url,
            "config": info,
            "notes": [
                "This module uses WordPress' built-in repair script (/wp-admin/maint/repair.php).",
                "On apply, wp-config.php is backed up, WP_ALLOW_REPAIR is enabled temporarily, the endpoint is called, then wp-config.php is restored.",
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
