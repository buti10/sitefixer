from __future__ import annotations

import posixpath
import time
from typing import Any, Dict, Optional

import requests

from ..sftp.connect import sftp_connect
from ..audit.actions import quarantine_move, read_text_remote, write_text_remote
from .helpers import (
    find_wp_config_path,
    ensure_site_base_url,
    build_repair_url,
    patch_enable_wp_allow_repair,
)


_USER_AGENT = "Sitefixer-WP-Repair/1.0"


def _http_get(url: str, *, timeout: int = 25, max_body: int = 400_000) -> Dict[str, Any]:
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


def _try_http_repair(base_url: str, *, mode: str, timeout: int) -> Dict[str, Any]:
    """Call WordPress repair endpoint.

    mode:
      - "repair" -> ?repair=1
      - "repair_optimize" -> ?repair=2
    """

    repair_url = build_repair_url(base_url)
    if mode not in {"repair", "repair_optimize"}:
        raise ValueError("mode must be 'repair' or 'repair_optimize'")

    param = "1" if mode == "repair" else "2"
    url = f"{repair_url}?repair={param}"
    r = _http_get(url, timeout=timeout)

    # Identify typical WP responses
    text = (r.get("text") or "")
    low = text.lower()
    requires_flag = ("wp_allow_repair" in low) or ("allow use of this tool" in low)

    # Very light parsing: count success/fail phrases
    success = low.count("success")
    failed = low.count("failed") + low.count("error")

    r.update(
        {
            "url": url,
            "requires_wp_allow_repair": bool(requires_flag),
            "counts": {"success_markers": success, "error_markers": failed},
            "snippet": text[:2000].replace("\n", " ")[:2000],
        }
    )
    return r


def db_repair_apply(
    host: str,
    port: int,
    username: str,
    password: str,
    wp_root: str,
    *,
    action_id: str,
    moved_dir: str,
    meta_path: str,
    domain: Optional[str] = None,
    mode: str = "repair_optimize",
    http_timeout: int = 25,
) -> Dict[str, Any]:
    """Apply database repair via WP built-in repair.php.

    This function:
      - backs up wp-config.php to moved_dir (quarantine_move)
      - writes a temporary wp-config.php enabling WP_ALLOW_REPAIR
      - calls repair.php endpoint over HTTP
      - restores the original wp-config.php
    """

    wp_root = posixpath.normpath(wp_root)
    base_url = ensure_site_base_url(domain or "")
    if not base_url:
        raise ValueError("Missing domain/site_url")

    client = sftp_connect(host, port, username, password)
    sftp = client.open_sftp()
    wp_config_path = None
    moved_orig_path = None
    try:
        wp_config_path = find_wp_config_path(sftp, wp_root)
        if not wp_config_path:
            return {
                "ok": False,
                "error": "wp-config.php not found (checked wp_root and its parent)",
                "wp_root": wp_root,
                "site_base_url": base_url,
            }

        original = read_text_remote(host, port, username, password, wp_config_path)
        patched, changed = patch_enable_wp_allow_repair(original)

        if changed:
            # quarantine original, then write patched file
            moved_orig_path = quarantine_move(
                host,
                port,
                username,
                password,
                wp_config_path,
                moved_dir,
                meta_path,
                action_id=action_id,
            )
            write_text_remote(host, port, username, password, wp_config_path, patched)

        # Call repair tool
        http_res = _try_http_repair(base_url, mode=mode, timeout=http_timeout)
        ok = bool(http_res.get("ok")) and not bool(http_res.get("requires_wp_allow_repair"))

        return {
            "ok": ok,
            "wp_root": wp_root,
            "site_base_url": base_url,
            "wp_config_path": wp_config_path,
            "wp_config_patched": bool(changed),
            "wp_config_backup_path": moved_orig_path,
            "repair": http_res,
        }

    finally:
        # Always restore wp-config.php if we patched it
        if wp_config_path and moved_orig_path:
            try:
                # Remove temporary patched file, restore original name
                try:
                    sftp.remove(wp_config_path)
                except Exception:
                    pass
                try:
                    sftp.rename(moved_orig_path, wp_config_path)
                except Exception:
                    # If rename fails, we at least keep the backup in moved_dir.
                    pass
            except Exception:
                pass

        try:
            sftp.close()
        except Exception:
            pass
        try:
            client.close()
        except Exception:
            pass