from __future__ import annotations

import posixpath
import stat
from typing import Any, Dict, List, Optional

from app.modules.wp_repair.modules.sftp.connect import sftp_connect
from .guard import assert_in_wp_root


def explorer_ls(
    host: str,
    port: int,
    username: str,
    password: str,
    wp_root: str,
    path: str,
    *,
    max_entries: int = 400,
) -> Dict[str, Any]:
    path, wp_root = assert_in_wp_root(path, wp_root)

    client = sftp_connect(host, port, username, password)
    sftp = client.open_sftp()
    try:
        try:
            attrs = sftp.listdir_attr(path)
        except Exception as e:
            return {"ok": False, "error": f"Cannot list directory: {e}", "path": path}

        entries: List[Dict[str, Any]] = []
        for a in attrs[: max_entries or 400]:
            mode = getattr(a, "st_mode", 0)
            is_dir = stat.S_ISDIR(mode)
            name = getattr(a, "filename", None) or getattr(a, "longname", "").split()[-1]
            full = posixpath.join(path, name)

            entries.append(
                {
                    "name": name,
                    "path": full,
                    "type": "dir" if is_dir else "file",
                    "size": int(getattr(a, "st_size", 0) or 0),
                    "mtime": int(getattr(a, "st_mtime", 0) or 0),
                }
            )

        # sort dirs first, then name
        entries.sort(key=lambda x: (0 if x["type"] == "dir" else 1, x["name"].lower()))

        return {
            "ok": True,
            "wp_root": wp_root,
            "path": path,
            "entries": entries,
            "truncated": len(attrs) > len(entries),
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
