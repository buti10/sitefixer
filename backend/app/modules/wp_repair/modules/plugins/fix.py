from __future__ import annotations

import posixpath
from typing import Any, Dict, List, Optional

# Keep this module pure: it only builds a plan (src/dst),
# the caller performs SFTP rename + meta updates for consistent rollback.

_MAX_DISABLE_DEFAULT = 50


def _is_safe_slug(slug: str) -> bool:
    if not slug or "/" in slug or "\\" in slug:
        return False
    if slug in (".", ".."):
        return False
    if ".." in slug:
        return False
    return True


def plugins_disable_plan(
    wp_root: str,
    slugs: Optional[List[str]],
    *,
    action_id: str,
    max_disable: int = _MAX_DISABLE_DEFAULT,
) -> Dict[str, Any]:
    wp_root = (wp_root or "").rstrip("/")
    plugins_root = posixpath.join(wp_root, "wp-content", "plugins")

    req = [str(s).strip() for s in (slugs or []) if str(s).strip()]
    uniq: List[str] = []
    seen = set()
    for s in req:
        if s in seen:
            continue
        seen.add(s)
        uniq.append(s)

    if len(uniq) > int(max_disable or _MAX_DISABLE_DEFAULT):
        return {"ok": False, "error": "too_many_plugins", "max_disable": int(max_disable)}

    plan: List[Dict[str, str]] = []
    invalid: List[str] = []

    for slug in uniq:
        if not _is_safe_slug(slug):
            invalid.append(slug)
            continue

        src = posixpath.join(plugins_root, slug)
        dst = posixpath.join(plugins_root, f"{slug}.disabled_{action_id}")
        plan.append({"slug": slug, "src": src, "dst": dst})

    return {"ok": len(invalid) == 0, "invalid": invalid, "plan": plan, "plugins_root": plugins_root}
