from __future__ import annotations

import os
import posixpath
import stat
import time
import uuid
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional, Tuple

from ..audit import audit_started, audit_success, audit_failed
from ..quarantine_sftp import ensure_quarantine_dirs, write_manifest, quarantine_action_dir

DEFAULT_DIR_MODE = 0o755
DEFAULT_FILE_MODE = 0o644
WPCONFIG_MODE = 0o640

# Hard limits (SFTP can be slow)
MAX_ITEMS = int(os.getenv("WP_REPAIR_PERM_MAX_ITEMS", "8000"))
MAX_DEPTH = int(os.getenv("WP_REPAIR_PERM_MAX_DEPTH", "6"))


@dataclass
class PermChange:
    path: str
    kind: str  # "file"|"dir"|"other"
    before: Optional[str]
    after: Optional[str]
    changed: bool
    error: Optional[str] = None


def _sftp_kind(mode: int) -> str:
    if stat.S_ISDIR(mode):
        return "dir"
    if stat.S_ISREG(mode):
        return "file"
    if stat.S_ISLNK(mode):
        return "symlink"
    return "other"


def _sftp_oct_mode(mode: int) -> str:
    return oct(stat.S_IMODE(mode))


def _is_within(root: str, p: str) -> bool:
    root_n = posixpath.normpath(root).rstrip("/")
    p_n = posixpath.normpath(p)
    return p_n == root_n or p_n.startswith(root_n + "/")


def _iter_tree_sftp(sftp, start: str, root: str) -> Tuple[List[Tuple[str, str, str]], List[str]]:
    warnings: List[str] = []
    out: List[Tuple[str, str, str]] = []

    start = posixpath.normpath(start)
    root = posixpath.normpath(root)

    q: List[Tuple[str, int]] = [(start, 0)]
    seen = 0

    while q:
        p, depth = q.pop(0)
        if depth > MAX_DEPTH:
            warnings.append(f"Max depth reached at {p}")
            continue

        if not _is_within(root, p):
            warnings.append(f"Skipped outside root: {p}")
            continue

        try:
            st = sftp.stat(p)
            kind = _sftp_kind(st.st_mode)
            before = _sftp_oct_mode(st.st_mode)
        except Exception as e:
            warnings.append(f"Cannot stat {p}: {type(e).__name__}: {e}")
            continue

        if kind == "symlink":
            continue

        out.append((p, kind, before))
        seen += 1
        if seen >= MAX_ITEMS:
            warnings.append(f"Max item limit reached ({MAX_ITEMS}). Stopped early.")
            break

        if kind == "dir":
            try:
                for ent in sftp.listdir_attr(p):
                    child = posixpath.join(p.rstrip("/"), ent.filename)
                    q.append((child, depth + 1))
            except Exception as e:
                warnings.append(f"Cannot read dir {p}: {type(e).__name__}: {e}")

    return out, warnings


def normalize_permissions_sftp(
    *,
    actor: str,
    sftp,
    root_path: str,
    target_rel_or_abs: str = "",
    dry_run: bool = True,
    dir_mode: int = DEFAULT_DIR_MODE,
    file_mode: int = DEFAULT_FILE_MODE,
    wpconfig_mode: int = WPCONFIG_MODE,
    ticket_id: Optional[int] = None,
) -> Dict[str, Any]:
    """
    SFTP permissions normalize with:
    - strict limits (MAX_ITEMS/MAX_DEPTH)
    - unique action_id
    - audit log
    - manifest for rollback (chmod)
    """

    action_id = f"permissions_normalize:{uuid.uuid4().hex}"
    root = posixpath.normpath(root_path).rstrip("/")
    if not root:
        return {"ok": False, "error": "root_path is required"}

    if target_rel_or_abs:
        start = target_rel_or_abs.strip()
        target = posixpath.normpath(start) if start.startswith("/") else posixpath.normpath(posixpath.join(root, start))
    else:
        target = root

    params = {
        "target": target_rel_or_abs or ".",
        "dry_run": dry_run,
        "dir_mode": oct(dir_mode),
        "file_mode": oct(file_mode),
        "wpconfig_mode": oct(wpconfig_mode),
        "mode": "sftp",
        "ticket_id": ticket_id,
    }

    audit_started(actor=actor, root_path=root, action_id=action_id, params=params, meta={"ticket_id": ticket_id})

    try:
        wpconfig_path = posixpath.join(root, "wp-config.php")

        t0 = time.time()
        items, warnings = _iter_tree_sftp(sftp, target, root)

        changes: List[PermChange] = []
        manifest_entries: List[Dict[str, Any]] = []
        changed_count = 0
        error_count = 0

        for p, kind, before in items:
            if kind not in ("dir", "file"):
                continue

            if kind == "dir":
                desired = dir_mode
            else:
                desired = wpconfig_mode if posixpath.normpath(p) == posixpath.normpath(wpconfig_path) else file_mode

            after = oct(desired)
            changed = (before != after)

            if changed and not dry_run:
                try:
                    before_int = int(before, 8)
                    after_int = int(after, 8)
                    sftp.chmod(p, desired)
                    manifest_entries.append({"op": "chmod", "path": p, "before_int": before_int, "after_int": after_int})
                except Exception as e:
                    error_count += 1
                    changes.append(PermChange(path=p, kind=kind, before=before, after=after, changed=False, error=f"{type(e).__name__}: {e}"))
                    continue

            if changed:
                changed_count += 1
                changes.append(PermChange(path=p, kind=kind, before=before, after=after, changed=True))

        res: Dict[str, Any] = {
            "ok": True,
            "action_id": action_id,
            "target": target,
            "dry_run": dry_run,
            "changed": changed_count,
            "errors": error_count,
            "warnings": warnings,
            "sec": round(time.time() - t0, 3),
            "changes_sample": [asdict(c) for c in changes[:200]],
            "truncated": len(changes) > 200,
            "rollback_available": False,
        }

        if not dry_run:
            ensure_quarantine_dirs(sftp, root, action_id)
            manifest = {
                "version": 1,
                "action_id": action_id,
                "created_at": int(time.time()),
                "root_path": root,
                "entries": manifest_entries,
                "meta": {"ticket_id": ticket_id, "kind": "permissions_normalize"},
            }
            mpath = write_manifest(sftp, root, action_id, manifest)
            res["manifest"] = mpath
            res["quarantine_dir"] = quarantine_action_dir(root, action_id)
            res["rollback_available"] = True

        audit_success(actor=actor, root_path=root, action_id=action_id, params=params, result=res, meta={"ticket_id": ticket_id})
        return res

    except Exception as e:
        audit_failed(actor=actor, root_path=root, action_id=action_id, params=params, error=f"{type(e).__name__}: {e}", meta={"ticket_id": ticket_id})
        return {"ok": False, "action_id": action_id, "error": f"{type(e).__name__}: {e}"}
