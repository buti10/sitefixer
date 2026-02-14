# app/modules/wp_repair/modules/permissions/fix.py
# - Load rules.json (optional via caller)
# - Traverse within allowed root
# - Apply chmod where permitted
# - Returns deterministic, deduplicated change lists (stable rollback logs)
from __future__ import annotations

import posixpath
import stat
from typing import Any, Dict, List, Tuple, Set, Optional

from ..sftp.connect import sftp_connect


DEFAULTS: Dict[str, Any] = {
    "dir_mode": 0o755,
    "file_mode": 0o644,
    "wp_config_mode": 0o640,
    "max_items": 5000,  # safety
}


def _is_excluded(path: str) -> bool:
    """
    Exclude internal/ignored directories from permission normalization.
    """
    p = posixpath.normpath(path)

    # exclude .sitefixer internal folder
    if "/.sitefixer" in p or p.endswith("/.sitefixer"):
        return True

    # optional other internal dirs
    if "/.opcache" in p or p.endswith("/.opcache"):
        return True

    return False


def _target_mode(path: str, is_dir: bool, rules: Dict[str, Any]) -> int:
    base = posixpath.basename(path)
    if base == "wp-config.php":
        return int(rules["wp_config_mode"])
    return int(rules["dir_mode"] if is_dir else rules["file_mode"])


def _walk(sftp, root: str, max_items: int) -> List[Tuple[str, bool, int]]:
    """
    Deterministic DFS walk with de-duplication.
    Returns list of (path, is_dir, current_mode) limited by max_items.

    Notes:
    - We dedupe by normalized absolute path so paths never appear twice.
    - We only add a directory to stack once.
    - We rely on listdir_attr for entries and stat for the root.
    """
    root = posixpath.normpath(root)
    out: List[Tuple[str, bool, int]] = []
    stack: List[str] = [root]
    seen: Set[str] = set()

    def _push(p: str) -> None:
        p = posixpath.normpath(p)
        if p in seen:
            return
        if _is_excluded(p):
            return
        seen.add(p)
        stack.append(p)

    # seed root
    _push(root)

    while stack and len(out) < max_items:
        cur = stack.pop()

        # stat current path
        try:
            st = sftp.stat(cur)
        except Exception:
            continue

        is_dir = stat.S_ISDIR(st.st_mode)
        out.append((cur, is_dir, st.st_mode & 0o777))

        if len(out) >= max_items:
            break

        if not is_dir:
            continue

        # list children
        try:
            entries = sftp.listdir_attr(cur)
        except Exception:
            continue

        for e in entries:
            name = e.filename
            if name in (".", ".."):
                continue
            p = posixpath.normpath(posixpath.join(cur, name))
            if _is_excluded(p):
                continue

            # record child once
            if p in seen:
                continue
            seen.add(p)

            is_d = stat.S_ISDIR(e.st_mode)
            out.append((p, is_d, e.st_mode & 0o777))

            if len(out) >= max_items:
                break

            # only traverse into dirs
            if is_d:
                stack.append(p)

        # continue while-loop

    return out


def _dedupe_change_dicts(changes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Deduplicate change records by (type, path). Keeps first occurrence.
    """
    seen: Set[tuple] = set()
    out: List[Dict[str, Any]] = []
    for c in changes:
        key = (c.get("type"), posixpath.normpath(c.get("path", "")))
        if key in seen:
            continue
        seen.add(key)
        # normalize path in output as well
        c = dict(c)
        c["path"] = posixpath.normpath(c["path"])
        out.append(c)
    return out


def _rules_payload(rules2: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "dir_mode": oct(int(rules2["dir_mode"])),
        "file_mode": oct(int(rules2["file_mode"])),
        "wp_config_mode": oct(int(rules2["wp_config_mode"])),
        "max_items": int(rules2["max_items"]),
    }


def permissions_preview(
    host: str,
    port: int,
    username: str,
    password: str,
    wp_root: str,
    rules: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    rules2 = dict(DEFAULTS)
    if rules:
        rules2.update(rules)

    client = sftp_connect(host, port, username, password)
    sftp = client.open_sftp()
    try:
        items = _walk(sftp, wp_root, int(rules2["max_items"]))
        scanned = len(items)

        changes: List[Dict[str, Any]] = []
        for path, is_dir, cur_mode in items:
            want = _target_mode(path, is_dir, rules2)
            if cur_mode != want:
                changes.append(
                    {
                        "path": posixpath.normpath(path),
                        "type": "dir" if is_dir else "file",
                        "from": oct(cur_mode),
                        "to": oct(want),
                    }
                )

        changes = _dedupe_change_dicts(changes)

        return {
            "ok": True,
            "wp_root": posixpath.normpath(wp_root),
            "scanned": scanned,
            "changes": changes,
            "rules": _rules_payload(rules2),
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


def permissions_apply(
    host: str,
    port: int,
    username: str,
    password: str,
    wp_root: str,
    rules: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Applies chmod changes. Returns list of changed items with old/new.
    Output is deduplicated by (type, path) so rollback logs are stable.
    """
    rules2 = dict(DEFAULTS)
    if rules:
        rules2.update(rules)

    client = sftp_connect(host, port, username, password)
    sftp = client.open_sftp()
    try:
        items = _walk(sftp, wp_root, int(rules2["max_items"]))

        changed: List[Dict[str, Any]] = []
        errors: List[Dict[str, Any]] = []

        # Apply chmod; we still keep per-path results stable
        for path, is_dir, cur_mode in items:
            want = _target_mode(path, is_dir, rules2)
            if cur_mode == want:
                continue
            try:
                sftp.chmod(path, want)
                changed.append(
                    {
                        "path": posixpath.normpath(path),
                        "type": "dir" if is_dir else "file",
                        "old_mode": oct(cur_mode),
                        "new_mode": oct(want),
                    }
                )
            except Exception as e:
                errors.append({"path": posixpath.normpath(path), "error": str(e)})

        # Deduplicate changed list
        # If the same path appears multiple times, keep the first result.
        dedup_changed: List[Dict[str, Any]] = []
        seen: Set[tuple] = set()
        for c in changed:
            key = (c.get("type"), c.get("path"))
            if key in seen:
                continue
            seen.add(key)
            dedup_changed.append(c)

        return {
            "ok": True,
            "wp_root": posixpath.normpath(wp_root),
            "changed": dedup_changed,
            "errors": errors,
            "rules": _rules_payload(rules2),
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
