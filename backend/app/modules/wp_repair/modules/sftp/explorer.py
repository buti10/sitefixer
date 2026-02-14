# explorer.py
# - Safe remote directory listing (ls)
# - Enforce boundaries:
#   - cannot escape selected project root
#   - limit depth / number of entries
#   - optional: block symlinks
# app/modules/wp_repair/modules/sftp/explorer.py
from __future__ import annotations

from typing import List, Dict, Optional
import posixpath

from .connect import sftp_connect

def _clamp_path(path: str, boundary_root: Optional[str]) -> str:
    p = posixpath.normpath(path or "/")
    if not p.startswith("/"):
        p = "/" + p

    if boundary_root:
        br = posixpath.normpath(boundary_root)
        if not br.startswith("/"):
            br = "/" + br
        # allow listing boundary itself or subpaths
        if p != br and not p.startswith(br.rstrip("/") + "/"):
            raise ValueError("Path outside project boundary")
    return p

def sftp_ls_safe(
    host: str, port: int, username: str, password: str,
    path: str, boundary_root: Optional[str] = None,
    max_entries: int = 500
) -> List[Dict]:
    """
    Safe remote ls:
    returns [{name, path, type, size}, ...]
    type: "dir" | "file"
    """
    client = sftp_connect(host, port, username, password)
    sftp = client.open_sftp()

    try:
        p = _clamp_path(path, boundary_root)
        out: List[Dict] = []
        for e in sftp.listdir_attr(p)[:max_entries]:
            is_dir = str(e.longname).startswith("d")
            child = posixpath.join(p, e.filename)
            out.append({
                "name": e.filename,
                "path": child,
                "type": "dir" if is_dir else "file",
                "size": int(getattr(e, "st_size", 0) or 0),
            })
        return out
    finally:
        try:
            sftp.close()
        except Exception:
            pass
        try:
            client.close()
        except Exception:
            pass


def sftp_path_is_dir(host: str, port: int, username: str, password: str, path: str) -> bool:
    client = sftp_connect(host, port, username, password)
    sftp = client.open_sftp()
    try:
        st = sftp.stat(path)
        # POSIX: directory bit check (works with paramiko)
        import stat as pystat
        return pystat.S_ISDIR(st.st_mode)
    finally:
        try: sftp.close()
        except Exception: pass
        try: client.close()
        except Exception: pass

