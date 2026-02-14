# /var/www/sitefixer/backend/app/modules/wp_repair/quarantine_sftp.py
from __future__ import annotations

import json
import posixpath
import time
from typing import Any, Dict, List, Optional

# -------------------------
# SFTP helpers
# -------------------------

def _pjoin(a: str, b: str) -> str:
    return posixpath.join(a.rstrip("/"), b.lstrip("/"))

def sftp_exists(sftp, path: str) -> bool:
    try:
        sftp.stat(path)
        return True
    except Exception:
        return False

def sftp_is_dir(sftp, path: str) -> bool:
    try:
        st = sftp.stat(path)
        import stat as _stat
        return _stat.S_ISDIR(st.st_mode)
    except Exception:
        return False

def sftp_mkdir_p(sftp, path: str) -> None:
    # create recursively (posix)
    path = posixpath.normpath(path)
    if path in ("", "/"):
        return

    parts = path.split("/")
    cur = ""
    if path.startswith("/"):
        cur = "/"

    for part in parts:
        if not part:
            continue
        cur = _pjoin(cur, part) if cur != "/" else "/" + part
        if not sftp_exists(sftp, cur):
            try:
                sftp.mkdir(cur)
            except Exception:
                # race or permission; re-check
                if not sftp_exists(sftp, cur):
                    raise

def sftp_rename_atomic(sftp, src: str, dst: str) -> None:
    try:
        sftp.posix_rename(src, dst)  # paramiko
    except Exception:
        sftp.rename(src, dst)

def sftp_write_text_atomic(sftp, path: str, content: str) -> None:
    # write to temp then rename
    tmp = path + f".tmp_{int(time.time())}"
    with sftp.open(tmp, "w") as f:
        f.write(content)
    sftp_rename_atomic(sftp, tmp, path)

# -------------------------
# Quarantine paths
# -------------------------

def quarantine_base(root_path: str) -> str:
    return _pjoin(root_path.rstrip("/"), "sitefixer-quarantaene")

def quarantine_action_dir(root_path: str, action_id: str) -> str:
    return _pjoin(quarantine_base(root_path), action_id)

def quarantine_before_dir(root_path: str, action_id: str) -> str:
    return _pjoin(quarantine_action_dir(root_path, action_id), "before")

def quarantine_after_dir(root_path: str, action_id: str) -> str:
    return _pjoin(quarantine_action_dir(root_path, action_id), "after")

def manifest_path(root_path: str, action_id: str) -> str:
    return _pjoin(quarantine_action_dir(root_path, action_id), "manifest.json")

# -------------------------
# High level operations
# -------------------------

def ensure_quarantine_dirs(sftp, root_path: str, action_id: str) -> Dict[str, str]:
    q_action = quarantine_action_dir(root_path, action_id)
    q_before = quarantine_before_dir(root_path, action_id)
    q_after = quarantine_after_dir(root_path, action_id)

    sftp_mkdir_p(sftp, q_action)
    sftp_mkdir_p(sftp, q_before)
    sftp_mkdir_p(sftp, q_after)

    return {"action_dir": q_action, "before_dir": q_before, "after_dir": q_after}

def move_into_quarantine(
    *,
    sftp,
    root_path: str,
    action_id: str,
    target_path: str,
    rel_name: Optional[str] = None,
) -> Optional[str]:
    """
    Moves target_path into quarantine/before/<rel_name or filename>.
    Returns backup_path or None if target doesn't exist.
    """
    if not sftp_exists(sftp, target_path):
        return None

    ensure_quarantine_dirs(sftp, root_path, action_id)

    name = rel_name or posixpath.basename(target_path)
    backup_path = _pjoin(quarantine_before_dir(root_path, action_id), name)

    # if backup exists, make it unique
    if sftp_exists(sftp, backup_path):
        backup_path = backup_path + f".{int(time.time())}"

    sftp_rename_atomic(sftp, target_path, backup_path)
    return backup_path

def write_manifest(sftp, root_path: str, action_id: str, manifest: Dict[str, Any]) -> str:
    ensure_quarantine_dirs(sftp, root_path, action_id)
    mpath = manifest_path(root_path, action_id)
    sftp_write_text_atomic(sftp, mpath, json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return mpath

def read_manifest(sftp, root_path: str, action_id: str) -> Dict[str, Any]:
    mpath = manifest_path(root_path, action_id)
    with sftp.open(mpath, "r") as f:
        return json.loads(f.read())

def rollback_from_manifest(*, sftp, root_path: str, action_id: str) -> Dict[str, Any]:
    """
    Restores changes recorded in manifest.json.
    Supports ops: file_replace, file_move, chmod
    """
    manifest = read_manifest(sftp, root_path, action_id)
    entries: List[Dict[str, Any]] = manifest.get("entries") or []

    ensure_quarantine_dirs(sftp, root_path, action_id)
    after_dir = quarantine_after_dir(root_path, action_id)

    rolled = 0
    errors: List[str] = []

    for e in entries:
        try:
            op = e.get("op")
            if op == "file_replace":
                target = e["target"]
                backup = e.get("backup")
                target_existed = bool(e.get("target_existed"))

                # move current target to after/ (if exists)
                if sftp_exists(sftp, target):
                    cur_name = posixpath.basename(target) + f".rolled_{int(time.time())}"
                    cur_dst = _pjoin(after_dir, cur_name)
                    sftp_rename_atomic(sftp, target, cur_dst)

                if target_existed and backup and sftp_exists(sftp, backup):
                    sftp_rename_atomic(sftp, backup, target)
                else:
                    # target didn't exist originally -> remove if recreated
                    if sftp_exists(sftp, target):
                        sftp.remove(target)

                rolled += 1

            elif op == "file_move":
                # restore moved file (drop-ins, .maintenance etc.)
                target = e["target"]
                backup = e.get("backup")
                if backup and sftp_exists(sftp, backup):
                    # if something exists at target, move it aside
                    if sftp_exists(sftp, target):
                        cur_name = posixpath.basename(target) + f".rolled_{int(time.time())}"
                        cur_dst = _pjoin(after_dir, cur_name)
                        sftp_rename_atomic(sftp, target, cur_dst)
                    sftp_rename_atomic(sftp, backup, target)
                rolled += 1

            elif op == "chmod":
                path = e["path"]
                before = e.get("before_int")
                if before is not None and sftp_exists(sftp, path):
                    sftp.chmod(path, int(before))
                rolled += 1

            else:
                # unknown op -> ignore but record
                errors.append(f"Unknown op: {op}")
        except Exception as ex:
            errors.append(f"{e.get('op')} {e.get('target') or e.get('path')}: {type(ex).__name__}: {ex}")

    return {
        "ok": len(errors) == 0,
        "action_id": action_id,
        "rolled_back": rolled,
        "errors": errors,
        "manifest": manifest_path(root_path, action_id),
    }
