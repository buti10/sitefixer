from __future__ import annotations

import posixpath
from typing import Any, Dict, List, Optional

from .preview import core_integrity_preview


DEFAULT_POLICY = {
    "deny_exact": ["wp-config.php", ".htaccess"],
    "deny_prefixes": ["wp-content/", ".sitefixer/"],
    "allowed_prefixes": ["wp-admin/", "wp-includes/"],
    "allowed_root_files": [
        "index.php",
        "wp-activate.php",
        "wp-blog-header.php",
        "wp-comments-post.php",
        "wp-config-sample.php",
        "wp-cron.php",
        "wp-links-opml.php",
        "wp-load.php",
        "wp-login.php",
        "wp-mail.php",
        "wp-settings.php",
        "wp-signup.php",
        "wp-trackback.php",
        "xmlrpc.php",
    ],
}


def _is_allowed_rel(rel: str, policy: Dict[str, Any]) -> bool:
    rel = rel.lstrip("/").replace("\\", "/")
    if rel in set(policy.get("deny_exact") or []):
        return False
    for p in (policy.get("deny_prefixes") or []):
        if rel.startswith(p):
            return False

    # allow root files explicitly
    if "/" not in rel and rel in set(policy.get("allowed_root_files") or []):
        return True

    # allow wp-admin/ and wp-includes/
    for p in (policy.get("allowed_prefixes") or []):
        if rel.startswith(p):
            return True

    return False


def core_replace_preview(
    host: str,
    port: int,
    username: str,
    password: str,
    wp_root: str,
    *,
    wp_version: Optional[str] = None,
    core_cache_base: str = "/var/www/sitefixer/core-cache/wordpress",
    max_files: int = 5000,
    policy: Dict[str, Any] | None = None,
    # --- compatibility with your endpoints ---
    allow_changed: bool = True,
    allow_missing: bool = False,
    max_replace: int | None = None,
    **_ignored: Any,
) -> Dict[str, Any]:
    """
    Builds a replace plan from integrity results.
    - allow_changed: include changed core files in plan
    - allow_missing: include missing core files in plan (optional; default False)
    - max_replace: optional limit (can also be enforced in apply)
    """
    wp_root = posixpath.normpath(wp_root)
    pol = dict(DEFAULT_POLICY)
    if policy:
        pol.update(policy)

    integrity = core_integrity_preview(
        host, port, username, password,
        wp_root,
        wp_version=wp_version,
        core_cache_base=core_cache_base,
        max_files=max_files,
        include_ok=False,
    )
    if not integrity.get("ok"):
        return {"ok": False, "error": integrity.get("error"), "integrity": integrity}

    plan: List[Dict[str, Any]] = []
    denied: List[Dict[str, Any]] = []

    if allow_changed:
        for it in (integrity.get("changed_files") or []):
            rel = it["rel"]
            if _is_allowed_rel(rel, pol):
                plan.append({"rel": rel})
            else:
                denied.append({"rel": rel, "reason": "policy_denied"})

    if allow_missing:
        for it in (integrity.get("missing_files") or []):
            rel = it["rel"]
            if _is_allowed_rel(rel, pol):
                plan.append({"rel": rel})
            else:
                denied.append({"rel": rel, "reason": "policy_denied"})

    if max_replace is not None and max_replace > 0:
        plan = plan[: int(max_replace)]

    return {
        "ok": True,
        "wp_root": wp_root,
        "wp_version": integrity.get("wp_version"),
        "policy": pol,
        "plan": plan,
        "plan_count": len(plan),
        "denied": denied,
        "denied_count": len(denied),
        "integrity": integrity,
    }
