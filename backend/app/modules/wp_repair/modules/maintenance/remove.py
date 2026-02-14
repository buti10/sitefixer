# app/modules/wp_repair/modules/maintenance/remove.py
from __future__ import annotations

import posixpath
from typing import Dict, Any

from ..sftp.connect import sftp_connect


def remove_maintenance(host: str, port: int, username: str, password: str, wp_root: str) -> Dict[str, Any]:
    """
    Checks if wp_root/.maintenance exists.
    Endpoint will quarantine-move it (for rollback).
    """
    wp_root = posixpath.normpath(wp_root)
    maintenance_path = posixpath.join(wp_root, ".maintenance")

    client = sftp_connect(host=host, port=port, username=username, password=password)
    sftp = client.open_sftp()
    try:
        try:
            sftp.stat(maintenance_path)
        except Exception:
            return {"ok": True, "skipped": True, "reason": ".maintenance not present"}

        return {"ok": True, "skipped": False, "path": maintenance_path}
    finally:
        try:
            sftp.close()
        except Exception:
            pass
        try:
            client.close()
        except Exception:
            pass