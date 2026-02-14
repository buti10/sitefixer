from __future__ import annotations

import posixpath
from ..sftp.connect import sftp_connect


def maintenance_exists(host: str, port: int, username: str, password: str, wp_root: str) -> bool:
    client = sftp_connect(host, port, username, password)
    sftp = client.open_sftp()
    try:
        p = posixpath.join(posixpath.normpath(wp_root), ".maintenance")
        try:
            sftp.stat(p)
            return True
        except Exception:
            return False
    finally:
        try:
            sftp.close()
        except Exception:
            pass
        try:
            client.close()
        except Exception:
            pass
