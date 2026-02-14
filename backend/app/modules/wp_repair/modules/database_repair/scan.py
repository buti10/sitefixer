from __future__ import annotations

import time
from typing import Any, Dict, Optional

import requests

from ..sftp.connect import sftp_connect
from .helpers import (
    find_wp_config_path,
    read_remote_text,
    parse_wp_config_info,
    ensure_site_base_url,
    build_repair_url,
)


_USER_AGENT = "Sitefixer-WP-Repair/1.0"


def _http_get(url: str, *, timeout: int = 15, max_body: int = 250_000) -> Dict[str, Any]:
    t0 = time.time()
    try:
        r = requests.get(
            url,
            timeout=timeout,
            allow_redirects=True,
            headers={"User-Agent": _USER_AGENT},
        )
        elapsed_ms = int((time.time() - t0) * 1000)
        text = (r.text or "")[:max_body]
        return {"ok": True, "status_code": r.status_code, "elapsed_ms": elapsed_ms, "text": text}
    except Exception as e:
        elapsed_ms = int((time.time() - t0) * 1000)
        return {"ok": False, "status_code": None, "elapsed_ms": elapsed_ms, "error": str(e), "text": ""}


def db_repair_scan(
    host: str,
    port: int,
    username: str,
    password: str,
    wp_root: str,
    *,
    domain: Optional[str] = None,
    timeout: int = 15,
) -> Dict[str, Any]:
    """Scan (non-invasive) database-repair readiness.

    Because WordPress' built-in repair tool does not offer a true read-only
    "check" mode over HTTP, this scan focuses on:

    - wp-config.php presence and WP_ALLOW_REPAIR state
    - expected core table names based on $table_prefix (best-effort)
    - reachability of /wp-admin/maint/repair.php
    """

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

        prefix = info.get("table_prefix") or "wp_"
        core_tables = [
            "commentmeta",
            "comments",
            "links",
            "options",
            "postmeta",
            "posts",
            "termmeta",
            "terms",
            "term_relationships",
            "term_taxonomy",
            "usermeta",
            "users",
        ]
        expected_tables = [prefix + t for t in core_tables]

        http = None
        if repair_url:
            http = _http_get(repair_url, timeout=timeout)

        # Heuristics for repair tool availability
        available = None
        requires_flag = None
        if http and http.get("ok") and http.get("text"):
            body = (http.get("text") or "").lower()
            if "wp_allow_repair" in body or "allow use of this tool" in body:
                available = False
                requires_flag = True
            elif "repair database" in body and "optimize" in body:
                available = True
                requires_flag = False

        return {
            "ok": True,
            "wp_root": wp_root,
            "wp_config_path": wp_config_path,
            "site_base_url": base_url or None,
            "repair_url": repair_url,
            "config": info,
            "repair_endpoint": {
                "reachable": bool(http and http.get("ok")),
                "status_code": (http or {}).get("status_code"),
                "elapsed_ms": (http or {}).get("elapsed_ms"),
                "available": available,
                "requires_wp_allow_repair": requires_flag,
            },
            "expected_tables": expected_tables,
            "notes": [
                "Scan does not execute database changes.",
                "Apply triggers WordPress' repair endpoint, which will perform the selected operation.",
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
