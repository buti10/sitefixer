# /var/www/sitefixer/backend/app/modules/wp-repair/backup.py
from __future__ import annotations

import hashlib
import os
import shutil
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


# Where backups live (default inside backend). Override via env if you want.
DEFAULT_BACKUP_BASE = os.getenv("WP_REPAIR_BACKUP_DIR", "/var/www/sitefixer/core-cache/repair-backups")
MAX_FILE_BYTES = int(os.getenv("WP_REPAIR_MAX_BACKUP_FILE_BYTES", "200000000"))  # 200MB safety
MAX_DIR_BYTES = int(os.getenv("WP_REPAIR_MAX_BACKUP_DIR_BYTES", "1500000000"))  # 1.5GB safety


def _safe_realpath(p: str) -> Path:
    return Path(p).expanduser().resolve(strict=False)


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _sha256_file(path: Path, limit_bytes: Optional[int] = None) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        if limit_bytes is None:
            for chunk in iter(lambda: f.read(1024 * 1024), b""):
                h.update(chunk)
        else:
            remaining = limit_bytes
            while remaining > 0:
                chunk = f.read(min(1024 * 1024, remaining))
                if not chunk:
                    break
                h.update(chunk)
                remaining -= len(chunk)
    return h.hexdigest()


def _dir_size_bytes(path: Path, max_files: int = 200000) -> int:
    """
    Compute directory size with hard caps to avoid runaway scans.
    """
    total = 0
    count = 0
    for p in path.rglob("*"):
        count += 1
        if count > max_files:
            break
        try:
            if p.is_file():
                total += p.stat().st_size
        except Exception:
            continue
    return total


def _clamp_target(root_path: str, target_path: str) -> Tuple[bool, str, Path, Path]:
    """
    Ensure target_path is within root_path.
    """
    root = _safe_realpath(root_path)
    target = _safe_realpath(target_path)

    try:
        target.relative_to(root)
    except Exception:
        return False, "target_path is outside root_path (path clamp)", root, target

    return True, "", root, target


def _job_id(prefix: str = "bk") -> str:
    return f"{prefix}-{int(time.time())}"


@dataclass
class BackupMeta:
    ok: bool
    kind: str  # "file" | "dir"
    root_path: str
    target_path: str
    backup_base: str
    backup_path: str
    created_at: int
    sha256_before: Optional[str] = None
    bytes: Optional[int] = None
    error: Optional[str] = None


def backup_file(
    *,
    root_path: str,
    target_rel_or_abs: str,
    label: str,
    backup_base: str = DEFAULT_BACKUP_BASE,
    compute_sha256: bool = True,
) -> Dict[str, Any]:
    """
    Backup a single file (copy2).
    - root_path: WordPress root (clamp boundary)
    - target_rel_or_abs: file path (relative to root or absolute)
    - label: e.g. "htaccess_reset"
    """
    # Resolve paths
    root = _safe_realpath(root_path)
    target = _safe_realpath(target_rel_or_abs) if os.path.isabs(target_rel_or_abs) else _safe_realpath(str(root / target_rel_or_abs))

    ok, err, root2, target2 = _clamp_target(str(root), str(target))
    if not ok:
        return asdict(BackupMeta(
            ok=False, kind="file", root_path=str(root2), target_path=str(target2),
            backup_base=backup_base, backup_path="", created_at=int(time.time()),
            error=err
        ))

    if not target2.exists() or not target2.is_file():
        return asdict(BackupMeta(
            ok=False, kind="file", root_path=str(root2), target_path=str(target2),
            backup_base=backup_base, backup_path="", created_at=int(time.time()),
            error="target file not found"
        ))

    size = target2.stat().st_size
    if size > MAX_FILE_BYTES:
        return asdict(BackupMeta(
            ok=False, kind="file", root_path=str(root2), target_path=str(target2),
            backup_base=backup_base, backup_path="", created_at=int(time.time()),
            bytes=size,
            error=f"file too large for backup (>{MAX_FILE_BYTES} bytes)"
        ))

    sha = _sha256_file(target2) if compute_sha256 else None

    job = _job_id("file")
    rel = str(target2.relative_to(root2)).replace("/", "__")
    backup_dir = _safe_realpath(backup_base) / "wp-repair" / job / label
    _ensure_dir(backup_dir)
    dest = backup_dir / rel

    try:
        shutil.copy2(str(target2), str(dest))
        return asdict(BackupMeta(
            ok=True, kind="file",
            root_path=str(root2), target_path=str(target2),
            backup_base=str(_safe_realpath(backup_base)),
            backup_path=str(dest),
            created_at=int(time.time()),
            sha256_before=sha,
            bytes=size
        ))
    except Exception as e:
        return asdict(BackupMeta(
            ok=False, kind="file",
            root_path=str(root2), target_path=str(target2),
            backup_base=str(_safe_realpath(backup_base)),
            backup_path=str(dest),
            created_at=int(time.time()),
            sha256_before=sha,
            bytes=size,
            error=f"{type(e).__name__}: {e}"
        ))


def backup_dir(
    *,
    root_path: str,
    target_rel_or_abs: str,
    label: str,
    backup_base: str = DEFAULT_BACKUP_BASE,
    max_bytes: int = MAX_DIR_BYTES,
) -> Dict[str, Any]:
    """
    Backup a directory (copytree) under a job folder.
    Used for: plugin/theme folder backups before replace.
    """
    root = _safe_realpath(root_path)
    target = _safe_realpath(target_rel_or_abs) if os.path.isabs(target_rel_or_abs) else _safe_realpath(str(root / target_rel_or_abs))

    ok, err, root2, target2 = _clamp_target(str(root), str(target))
    if not ok:
        return asdict(BackupMeta(
            ok=False, kind="dir", root_path=str(root2), target_path=str(target2),
            backup_base=backup_base, backup_path="", created_at=int(time.time()),
            error=err
        ))

    if not target2.exists() or not target2.is_dir():
        return asdict(BackupMeta(
            ok=False, kind="dir", root_path=str(root2), target_path=str(target2),
            backup_base=backup_base, backup_path="", created_at=int(time.time()),
            error="target directory not found"
        ))

    size = _dir_size_bytes(target2)
    if size > max_bytes:
        return asdict(BackupMeta(
            ok=False, kind="dir", root_path=str(root2), target_path=str(target2),
            backup_base=backup_base, backup_path="", created_at=int(time.time()),
            bytes=size,
            error=f"directory too large for backup (>{max_bytes} bytes)"
        ))

    job = _job_id("dir")
    rel = str(target2.relative_to(root2)).replace("/", "__")
    backup_dir_path = _safe_realpath(backup_base) / "wp-repair" / job / label / rel
    _ensure_dir(backup_dir_path.parent)

    try:
        # copytree requires dest not exist
        shutil.copytree(str(target2), str(backup_dir_path))
        return asdict(BackupMeta(
            ok=True, kind="dir",
            root_path=str(root2), target_path=str(target2),
            backup_base=str(_safe_realpath(backup_base)),
            backup_path=str(backup_dir_path),
            created_at=int(time.time()),
            bytes=size
        ))
    except Exception as e:
        return asdict(BackupMeta(
            ok=False, kind="dir",
            root_path=str(root2), target_path=str(target2),
            backup_base=str(_safe_realpath(backup_base)),
            backup_path=str(backup_dir_path),
            created_at=int(time.time()),
            bytes=size,
            error=f"{type(e).__name__}: {e}"
        ))


def rollback_backup(*, backup_path: str, restore_to: str) -> Dict[str, Any]:
    """
    Restores a backup file/dir back to restore_to.
    - backup_path: path returned from backup_* meta
    - restore_to: absolute path to restore destination
    """
    b = _safe_realpath(backup_path)
    dest = _safe_realpath(restore_to)

    if not b.exists():
        return {"ok": False, "error": "backup_path not found", "backup_path": str(b), "restore_to": str(dest)}

    try:
        if b.is_file():
            _ensure_dir(dest.parent)
            shutil.copy2(str(b), str(dest))
        elif b.is_dir():
            # restore by replacing dest (move away existing)
            if dest.exists():
                tmp_old = dest.with_name(dest.name + f".rollback_old_{int(time.time())}")
                shutil.move(str(dest), str(tmp_old))
            shutil.copytree(str(b), str(dest))
        else:
            return {"ok": False, "error": "backup_path is neither file nor dir", "backup_path": str(b), "restore_to": str(dest)}

        return {"ok": True, "backup_path": str(b), "restore_to": str(dest)}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}", "backup_path": str(b), "restore_to": str(dest)}

# wp_repair/backup.py (am Ende ergänzen)
import posixpath

def backup_file_sftp(*, sftp, root_path: str, target_rel_or_abs: str, label: str,
                     backup_base: str = DEFAULT_BACKUP_BASE, compute_sha256: bool = True) -> Dict[str, Any]:
    root = root_path.rstrip("/") or "/"
    target = target_rel_or_abs
    if not target.startswith("/"):
        target = posixpath.join(root, target.lstrip("/"))

    # Clamp: target muss unter root liegen
    root_norm = posixpath.normpath(root)
    target_norm = posixpath.normpath(target)
    if not (target_norm == root_norm or target_norm.startswith(root_norm.rstrip("/") + "/")):
        return {"ok": False, "error": "target_path is outside root_path (path clamp)", "root_path": root_norm, "target_path": target_norm}

    # Read remote bytes (cap)
    try:
        st = sftp.stat(target_norm)
        size = int(getattr(st, "st_size", 0) or 0)
        if size > MAX_FILE_BYTES:
            return {"ok": False, "error": f"file too large for backup (>{MAX_FILE_BYTES} bytes)", "bytes": size, "target_path": target_norm}

        with sftp.open(target_norm, "rb") as f:
            data = f.read(min(size, MAX_FILE_BYTES))
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}", "target_path": target_norm}

    sha = hashlib.sha256(data).hexdigest() if compute_sha256 else None

    job = _job_id("sftp-file")
    rel = target_norm[len(root_norm.rstrip("/")) + 1:].replace("/", "__") if target_norm != root_norm else "ROOT"
    backup_dir = _safe_realpath(backup_base) / "wp-repair" / job / label
    _ensure_dir(backup_dir)
    dest = backup_dir / rel

    try:
        dest.write_bytes(data)
        return {
            "ok": True, "kind": "file", "root_path": root_norm, "target_path": target_norm,
            "backup_base": str(_safe_realpath(backup_base)), "backup_path": str(dest),
            "created_at": int(time.time()), "sha256_before": sha, "bytes": len(data)
        }
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}", "backup_path": str(dest), "target_path": target_norm}


def rollback_file_sftp(*, sftp, backup_path: str, restore_to: str) -> Dict[str, Any]:
    b = _safe_realpath(backup_path)
    if not b.exists() or not b.is_file():
        return {"ok": False, "error": "backup_path not found", "backup_path": str(b), "restore_to": restore_to}

    try:
        data = b.read_bytes()
        # atomic-ish: write to temp then rename (remote rename ok)
        tmp = restore_to + f".sitefixer_tmp_{int(time.time())}"
        with sftp.open(tmp, "wb") as f:
            f.write(data)
        try:
            sftp.posix_rename(tmp, restore_to)
        except Exception:
            # fallback
            sftp.rename(tmp, restore_to)
        return {"ok": True, "backup_path": str(b), "restore_to": restore_to, "bytes": len(data)}
    except Exception as e:
        return {"ok": False, "error": f"{type(e).__name__}: {e}", "backup_path": str(b), "restore_to": restore_to}
