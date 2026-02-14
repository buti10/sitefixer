from __future__ import annotations

import posixpath
from typing import Any, Dict, List

from .helpers import read_text_remote, sftp_exists, tail_text, extract_errors, detect_plugin_from_log


def _try_read(host, port, username, password, path: str, max_bytes: int) -> str:
    try:
        return read_text_remote(host, port, username, password, path, max_bytes=max_bytes)
    except Exception:
        return ""


def diagnostics_scan(host: str, port: int, username: str, password: str, wp_root: str, *, tail_lines: int = 250) -> Dict[str, Any]:
    wp_root = posixpath.normpath(wp_root)

    candidates: List[str] = [
        posixpath.join(wp_root, "wp-content", "debug.log"),
        posixpath.join(wp_root, "wp-content", "php-errors.log"),
        posixpath.join(wp_root, "error_log"),
        posixpath.join(wp_root, "wp-content", "error_log"),
        posixpath.join(posixpath.dirname(wp_root), "error_log"),
    ]

    sources = []
    tails = {}
    merged_tail = ""

    for p in candidates:
        if not sftp_exists(host, port, username, password, p):
            continue
        raw = _try_read(host, port, username, password, p, max_bytes=2_000_000)
        t = tail_text(raw, max_lines=tail_lines)
        if not t.strip():
            continue
        sources.append({"path": p})
        tails[p] = t
        merged_tail += "\n" + t

    merged_tail = tail_text(merged_tail, max_lines=tail_lines * 2)

    errors = extract_errors(merged_tail)
    plugin = detect_plugin_from_log(merged_tail)

    recommendations = []
    if plugin:
        recommendations.append({
            "fix_id": "disable_plugin",
            "risk": "medium",
            "title": f"Disable plugin '{plugin}' (rename folder) based on log hint",
            "params": {"plugin_slug": plugin},
        })
    if any("Allowed memory size" in e.get("line", "") for e in errors):
        recommendations.append({
            "fix_id": "set_wp_memory_limit",
            "risk": "low",
            "title": "Set WP_MEMORY_LIMIT to 256M in wp-config.php",
            "params": {"memory": "256M"},
        })

    return {
        "ok": True,
        "wp_root": wp_root,
        "sources": sources,
        "errors": errors,
        "recommendations": recommendations,
        "tails": tails,  # keyed by path
    }
