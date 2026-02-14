# app/modules/wp_repair/modules/file_explorer/ai_help.py
from __future__ import annotations

from typing import Any, Dict, Optional

from .guard import assert_in_wp_root
from .read import explorer_read


def explorer_ai_help(
    host: str,
    port: int,
   username: str,
    password: str,
    wp_root: str,
    path: str,
    *,
    log_excerpt: Optional[str] = None,
    goal: Optional[str] = None,
    max_bytes: int = 200_000,
) -> Dict[str, Any]:
    path, wp_root = assert_in_wp_root(path, wp_root)

    file_res = explorer_read(
        host, port, username, password, wp_root, path,
        max_bytes=max_bytes,
        mask_secrets=True,  # wp-config wird automatisch maskiert
    )
    if not file_res.get("ok"):
        return file_res

    p = (path or "").lower()
    is_config = p.endswith(("wp-config.php", ".htaccess", "php.ini", "user.ini"))
    is_php = p.endswith(".php")

    default_mode = "replace_block" if is_config else ("unified_diff" if is_php else "replace_block")

    patch_suggestions = {
        "default_mode": default_mode,
        "rules": {
            "config_files_use_replace_block": True,
            "php_files_can_use_unified_diff_expert": True,
        },
        "replace_block": {
            "enabled": True,
            "fields": ["start_marker", "end_marker", "replacement", "insert_if_missing", "insert_before_marker"],
            "notes": [
                "Use markers to safely edit only a controlled block.",
                "If markers are missing, insert the whole block before insert_before_marker or append at EOF."
            ],
            "examples": [
                {
                    "start_marker": "/* Sitefixer patch */",
                    "end_marker": "/* /Sitefixer patch */",
                    "replacement": "/* Sitefixer patch */\n# your changes here\n/* /Sitefixer patch */\n",
                    "insert_if_missing": True,
                    "insert_before_marker": "/* That's all, stop editing! */",
                }
            ],
        },
        "unified_diff": {
            "enabled": bool(is_php),  # nur sinnvoll bei .php
            "fields": ["diff"],
            "notes": [
                "Expert mode: only for .php files.",
                "Patch must match file context exactly; otherwise validation fails."
            ],
            "example_header": "--- a/path\n+++ b/path\n@@ -1,3 +1,3 @@",
        },
        "flow": [
            "Generate a patch suggestion",
            "Call /fix/explorer/patch/preview to show diff",
            "Optionally call /fix/explorer/patch/validate",
            "Call /fix/explorer/patch/apply to write with quarantine backup",
        ],
    }

    payload: Dict[str, Any] = {
        "ok": True,
        "wp_root": wp_root,
        "path": path,
        "goal": goal or "Fix the issue safely with minimal changes and explain steps.",
        "log_excerpt": (log_excerpt or "")[:50_000],
        "file": {
            "path": path,
            "text": file_res.get("text") or "",
            "truncated": bool(file_res.get("truncated")),
            "masked": bool(file_res.get("masked")),
            "mask_stats": file_res.get("mask_stats") or {},
        },
        "patch_suggestions": patch_suggestions,
        "ai_instructions": [
            "Analyze the file content and provided log excerpt.",
            "Explain likely root cause and safest fix steps.",
            "Return patch suggestions that follow patch_suggestions schema.",
            "Prefer replace_block for wp-config.php/.htaccess/php.ini/user.ini.",
            "Use unified_diff only for .php files (expert mode).",
            "Avoid changing secrets/credentials. Do not output secrets.",
        ],
    }

    return payload
