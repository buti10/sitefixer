from __future__ import annotations
from dataclasses import dataclass
from typing import List, Optional, Tuple
import posixpath
import re

WP_CONFIG = "wp-config.php"
WP_VERSION = "wp-includes/version.php"

@dataclass
class WPRoot:
    path: str
    version: Optional[str] = None

def _join(a: str, b: str) -> str:
    a = a if a else "/"
    if not a.endswith("/"):
        a += "/"
    return posixpath.normpath(posixpath.join(a, b)).replace("\\", "/")

def _is_wp_root(sftp, path: str) -> bool:
    # path ist ein Ordnerpfad
    try:
        sftp.stat(_join(path, WP_CONFIG))
        sftp.stat(_join(path, WP_VERSION))
        return True
    except Exception:
        return False

def _read_wp_version(sftp, root: str) -> Optional[str]:
    p = _join(root, WP_VERSION)
    try:
        with sftp.open(p, "r") as f:
            data = f.read()
        if isinstance(data, bytes):
            data = data.decode("utf-8", "ignore")
        m = re.search(r"\$wp_version\s*=\s*'([^']+)'", data)
        return m.group(1) if m else None
    except Exception:
        return None

def find_wp_projects(
    sftp,
    start_path: str = "/",
    max_depth: int = 4,
    max_dirs_per_level: int = 250,
    ignore_dirs: Tuple[str, ...] = ("logs", ".cache", ".composer", ".opcache", ".quarantine", "tmp", "temp", "backup", "backups", "node_modules", "vendor"),
) -> List[WPRoot]:
    start_path = start_path or "/"
    if not start_path.endswith("/"):
        start_path += "/"

    found: List[WPRoot] = []
    seen = set()

    def walk(path: str, depth: int):
        if depth > max_depth:
            return
        key = posixpath.normpath(path)
        if key in seen:
            return
        seen.add(key)

        # WP Root?
        if _is_wp_root(sftp, path):
            found.append(WPRoot(path=path, version=_read_wp_version(sftp, path)))
            # trotzdem weiter suchen (weil z.B. Subsites möglich), aber flach halten:
            # return

        # children dirs
        try:
            items = sftp.listdir_attr(path)
        except Exception:
            return

        dirs = []
        for it in items:
            name = getattr(it, "filename", None) or getattr(it, "longname", "")
            if not name or name in (".", ".."):
                continue
            # dir bit check (paramiko SFTPAttributes.st_mode)
            try:
                import stat
                if not stat.S_ISDIR(it.st_mode):
                    continue
            except Exception:
                continue

            low = name.lower()
            if any(low == x or low.startswith(x + "_") for x in ignore_dirs):
                continue
            dirs.append(name)

        # limiter (Sicherheit/Performance)
        dirs = sorted(dirs)[:max_dirs_per_level]

        for d in dirs:
            walk(_join(path, d) + "/", depth + 1)

    walk(start_path, 0)
    # Sort: kürzeste Pfade zuerst
    found.sort(key=lambda x: len(x.path))
    return found
