from __future__ import annotations

from typing import Any, Dict, Optional

from app.modules.wp_repair.modules.audit.actions import create_action, quarantine_move
from app.modules.wp_repair.modules.sftp.connect import sftp_connect
from .guard import assert_in_wp_root
from .patch_engine import _unify_newlines

from .guard import assert_in_wp_root
from .read import explorer_read
from .patch_engine import (
    PatchError,
    choose_mode_by_path,
    apply_replace_block,
    apply_unified_diff_strict,
    _build_unified_diff,
)


def patch_preview(
    host: str,
    port: int,
    username: str,
    password: str,
    wp_root: str,
    *,
    path: str,
    mode: Optional[str],
    replace_block: Optional[Dict[str, Any]] = None,
    unified_diff: Optional[str] = None,
    max_bytes: int = 200_000,
) -> Dict[str, Any]:
    path, wp_root = assert_in_wp_root(path, wp_root)

    r = explorer_read(host, port, username, password, wp_root, path, max_bytes=max_bytes)
    if not r.get("ok"):
        return r

    old_text = r.get("text") or ""
    chosen = choose_mode_by_path(path, requested=mode)

    if chosen == "replace_block":
        if not replace_block:
            return {"ok": False, "error": "replace_block payload missing", "mode": "replace_block"}
        try:
            new_text, info = apply_replace_block(
                old_text,
                start_marker=str(replace_block.get("start_marker") or ""),
                end_marker=str(replace_block.get("end_marker") or ""),
                replacement=str(replace_block.get("replacement") or ""),
                insert_if_missing=bool(replace_block.get("insert_if_missing", True)),
                insert_before_marker=replace_block.get("insert_before_marker"),
            )
        except PatchError as e:
            return {"ok": False, "error": str(e), "mode": "replace_block"}

        diff = _build_unified_diff(old_text, new_text, path)
        return {"ok": True, "mode": "replace_block", "path": path, "patch_info": info, "diff": diff}

    if chosen == "unified_diff":
        if not unified_diff:
            return {"ok": False, "error": "unified_diff missing", "mode": "unified_diff"}
        # apply to validate
        try:
            new_text, info = apply_unified_diff_strict(old_text, unified_diff)
        except PatchError as e:
            return {"ok": False, "error": str(e), "mode": "unified_diff"}
        # show normalized diff (what would be applied)
        diff = _build_unified_diff(old_text, new_text, path)
        return {"ok": True, "mode": "unified_diff", "path": path, "patch_info": info, "diff": diff}

    return {"ok": False, "error": f"Unsupported mode: {chosen}"}


def patch_apply(
    host: str,
    port: int,
    username: str,
    password: str,
    wp_root: str,
    *,
    path: str,
    mode: Optional[str],
    replace_block: Optional[Dict[str, Any]],
    unified_diff: Optional[str],
    reason: str,
    ticket_id: int,
    actor_user_id: int,
    actor_name: Optional[str] = None,
    project_root: Optional[str] = None,
    max_bytes: int = 500_000,
) -> Dict[str, Any]:
    path, wp_root = assert_in_wp_root(path, wp_root)

    # read full enough for patch
    r = explorer_read(host, port, username, password, wp_root, path, max_bytes=2_000_000)
    if not r.get("ok"):
        return r
    old_text = r.get("text") or ""

    chosen = choose_mode_by_path(path, requested=mode)

    # enforce your policy: config files => replace-block by default
    # allow unified diff only when explicitly requested AND file endswith .php
    if chosen == "unified_diff" and not path.lower().endswith(".php"):
        return {"ok": False, "error": "Unified diff allowed only for .php files", "mode": "unified_diff"}

    if chosen == "replace_block":
        if not replace_block:
            return {"ok": False, "error": "replace_block payload missing", "mode": "replace_block"}
        new_text, info = apply_replace_block(
            old_text,
            start_marker=str(replace_block.get("start_marker") or ""),
            end_marker=str(replace_block.get("end_marker") or ""),
            replacement=str(replace_block.get("replacement") or ""),
            insert_if_missing=bool(replace_block.get("insert_if_missing", True)),
            insert_before_marker=replace_block.get("insert_before_marker"),
        )
    else:
        if not unified_diff:
            return {"ok": False, "error": "unified_diff missing", "mode": "unified_diff"}
        new_text, info = apply_unified_diff_strict(old_text, unified_diff)

    # size guard
    if len(new_text.encode("utf-8", errors="replace")) > max_bytes:
        return {"ok": False, "error": f"Result too large (>{max_bytes} bytes)"}

    action = create_action(
        host, port, username, password, wp_root,
        fix_id="explorer_patch_apply",
        context={"path": path, "mode": chosen, "reason": reason},
        ticket_id=int(ticket_id or 0),
        actor_user_id=int(actor_user_id or 0),
        actor_name=actor_name,
        project_root=project_root,
    )

    client = sftp_connect(host, port, username, password)
    sftp = client.open_sftp()
    try:
        qm = quarantine_move(
            host, port, username, password,
            wp_root=wp_root,
            src_path=path,
            action_id=action["action_id"],
            kind="FILE",
        )
        backup_path = qm.get("dst_path") if qm.get("ok") else None


        f = sftp.open(path, "wb")
        try:
            f.write(new_text.encode("utf-8", errors="replace"))
        finally:
            f.close()

        diff = _build_unified_diff(old_text, new_text, path)

        return {
            "ok": True,
            "action_id": action["action_id"],
            "path": path,
            "mode": chosen,
            "backup_path": backup_path,
            "patch_info": info,
            "diff": diff,
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
def patch_validate(
    host: str,
    port: int,
    username: str,
    password: str,
    wp_root: str,
    *,
    path: str,
    mode: Optional[str],
    replace_block: Optional[Dict[str, Any]] = None,
    unified_diff: Optional[str] = None,
    max_bytes: int = 200_000,
) -> Dict[str, Any]:
    """
    Validate patch applicability without returning a diff.
    - For replace_block: checks markers OR insert conditions
    - For unified_diff: attempts apply to confirm context match
    """
    path, wp_root = assert_in_wp_root(path, wp_root)

    r = explorer_read(host, port, username, password, wp_root, path, max_bytes=2_000_000)
    if not r.get("ok"):
        return r

    old_text = r.get("text") or ""
    chosen = choose_mode_by_path(path, requested=mode)

    if chosen == "replace_block":
        if not replace_block:
            return {"ok": False, "error": "replace_block payload missing", "mode": "replace_block"}
        start_marker = str(replace_block.get("start_marker") or "")
        end_marker = str(replace_block.get("end_marker") or "")
        insert_before_marker = replace_block.get("insert_before_marker")
        insert_if_missing = bool(replace_block.get("insert_if_missing", True))

        src = _unify_newlines(old_text)
        start = src.find(start_marker) if start_marker else -1
        end = src.find(end_marker) if end_marker else -1

        if start != -1 and end != -1 and end >= start:
            return {"ok": True, "mode": "replace_block", "path": path, "valid": True, "status": "markers_found"}

        if not insert_if_missing:
            return {"ok": False, "mode": "replace_block", "path": path, "valid": False, "error": "Markers not found"}

        if insert_before_marker:
            idx = src.find(str(insert_before_marker))
            if idx != -1:
                return {"ok": True, "mode": "replace_block", "path": path, "valid": True, "status": "will_insert_before_marker"}

        return {"ok": True, "mode": "replace_block", "path": path, "valid": True, "status": "will_append"}

    if chosen == "unified_diff":
        if not unified_diff:
            return {"ok": False, "error": "unified_diff missing", "mode": "unified_diff"}
        if not path.lower().endswith(".php"):
            return {"ok": False, "error": "Unified diff allowed only for .php files", "mode": "unified_diff"}

        try:
            _new_text, info = apply_unified_diff_strict(old_text, unified_diff)
            return {"ok": True, "mode": "unified_diff", "path": path, "valid": True, "patch_info": info}
        except PatchError as e:
            return {"ok": False, "mode": "unified_diff", "path": path, "valid": False, "error": str(e)}

    return {"ok": False, "error": f"Unsupported mode: {chosen}"}
