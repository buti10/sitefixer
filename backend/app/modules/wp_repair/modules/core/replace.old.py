# replace.py
# - Fetch/prepare clean WP core for version
# - Quarantine existing core files before replacing
# - Replace only core paths (exclude wp-content, wp-config.php)
from __future__ import annotations

import os
import posixpath
import time
from typing import Any, Dict, List, Optional

from ..sftp.connect import sftp_connect
from .preview import core_integrity_preview, detect_wp_version_remote
from .manifest import core_file_abs_path, DEFAULT_CORE_CACHE_BASE


DEFAULT_POLICY = {
    "allowed_prefixes": ["wp-admin/", "wp-includes/"],
    "allowed_root_files": [
        "index.php", "wp-activate.php", "wp-blog-header.php", "wp-comments-post.php",
        "wp-config-sample.php", "wp-cron.php", "wp-links-opml.php", "wp-load.php",
        "wp-login.php", "wp-mail.php", "wp-settings.php", "wp-signup.php",
        "wp-trackback.php", "xmlrpc.php",
    ],
    "deny_exact": ["wp-config.php", ".htaccess"],
    "deny_prefixes": ["wp-content/", ".sitefixer/"],
}


def _is_allowed(rel: str, policy: Dict[str, Any]) -> bool:
    rel = rel.lstrip("/")

    if rel in policy.get("deny_exact", []):
        return False
    for pfx in policy.get("deny_prefixes", []):
        if rel.startswith(pfx):
            return False

    # allowed root files
    if "/" not in rel and rel in policy.get("allowed_root_files", []):
        return True

    # allowed prefixes
    for pfx in policy.get("allowed_prefixes", []):
        if rel.startswith(pfx):
            return True

    return False


def core_replace_preview(
    host: str,
    port: int,
    username: str,
    password: str,
    wp_root: str,
    *,
    max_files: int = 5000,
    max_replace: int = 500,
    core_cache_base: str = DEFAULT_CORE_CACHE_BASE,
    policy: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    policy2 = dict(DEFAULT_POLICY)
    if policy:
        policy2.update(policy)

    integrity = core_integrity_preview(
        host, port, username, password, wp_root,
        max_files=max_files,
        core_cache_base=core_cache_base,
        include_ok=False,
    )
    if not integrity.get("ok"):
        return {"ok": False, "error": integrity.get("error"), "integrity": integrity}

    plan: List[Dict[str, Any]] = []
    denied: List[Dict[str, Any]] = []

    for it in (integrity.get("changed_files") or []):
        rel = it["rel"]
        if _is_allowed(rel, policy2):
            plan.append({"rel": rel})
        else:
            denied.append({"rel": rel})

    plan = plan[:max_replace]

    return {
        "ok": True,
        "wp_root": integrity.get("wp_root"),
        "wp_version": integrity.get("wp_version"),
        "integrity": integrity,
        "replace_preview": {
            "ok": True,
            "policy": policy2,
            "plan": plan,
            "plan_count": len(plan),
            "denied": denied,
            "denied_count": len(denied),
            "max_replace": max_replace,
        },
    }


def _upload_local_to_remote(sftp, local_path: str, remote_path: str) -> None:
    # ensure remote parent exists
    parent = posixpath.dirname(remote_path)
    _mkdir_p(sftp, parent)

    with open(local_path, "rb") as fsrc:
        fdst = sftp.open(remote_path, "wb")
        try:
            while True:
                b = fsrc.read(1024 * 1024)
                if not b:
                    break
                fdst.write(b)
        finally:
            fdst.close()


def _mkdir_p(sftp, path: str) -> None:
    path = posixpath.normpath(path)
    if path in ("", "/"):
        return
    cur = ""
    for part in path.split("/"):
        if not part:
            continue
        cur += "/" + part
        try:
            sftp.stat(cur)
        except Exception:
            try:
                sftp.mkdir(cur)
            except Exception:
                pass


def core_replace_apply(
    host: str,
    port: int,
    username: str,
    password: str,
    wp_root: str,
    *,
    rels: List[str],
    wp_version: Optional[str] = None,
    core_cache_base: str = DEFAULT_CORE_CACHE_BASE,
) -> Dict[str, Any]:
    """
    Replaces only provided rel paths. MUST be preflight-safe.
    """
    wp_root = posixpath.normpath(wp_root)
    if not wp_version:
        wp_version = detect_wp_version_remote(host,
