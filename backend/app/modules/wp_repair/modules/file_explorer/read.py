# app/modules/wp_repair/modules/file_explorer/read.py
from __future__ import annotations

import stat
from typing import Any, Dict

from app.modules.wp_repair.modules.sftp.connect import sftp_connect
from .guard import assert_in_wp_root
from .masking import apply_masking


def explorer_read(
    host: str,
    port: int,
    username: str,
    password: str,
    wp_root: str,
    path: str,
    *,
    max_bytes: int = 200_000,
    mask_secrets: bool = True,   # <-- optionaler Schalter
) -> Dict[str, Any]:
    path, wp_root = assert_in_wp_root(path, wp_root)

    if max_bytes <= 0:
        max_bytes = 200_000
    max_bytes = min(int(max_bytes), 2_000_000)

    client = sftp_connect(host, port, username, password)
    sftp = client.open_sftp()
    try:
        try:
            st = sftp.stat(path)
        except Exception as e:
            return {"ok": False, "error": f"File not found/stat failed: {e}", "path": path}

        if stat.S_ISDIR(getattr(st, "st_mode", 0)):
            return {"ok": False, "error": "Path is a directory", "path": path}

        size = int(getattr(st, "st_size", 0) or 0)

        f = sftp.open(path, "rb")
        try:
            data = f.read(max_bytes)
        finally:
            f.close()

        if b"\x00" in data:
            return {
                "ok": False,
                "error": "Binary file not supported",
                "path": path,
                "meta": {"size": size, "mtime": int(getattr(st, "st_mtime", 0) or 0)},
            }

        text = data.decode("utf-8", errors="replace")

        mask_stats = {}
        masked = False
        if mask_secrets:
            text2, mask_stats = apply_masking(path, text)
            text = text2
            masked = bool(mask_stats)

        return {
            "ok": True,
            "wp_root": wp_root,
            "path": path,
            "text": text,
            "truncated": size > max_bytes,
            "meta": {"size": size, "mtime": int(getattr(st, "st_mtime", 0) or 0)},
            "masked": masked,            # <-- neu
            "mask_stats": mask_stats,    # <-- neu
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
