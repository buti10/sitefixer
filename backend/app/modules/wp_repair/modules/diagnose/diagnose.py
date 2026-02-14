# diagnose.py
# - Run the defined set of checks
# - Produce a JSON result (project.json)
# - Support light mode (fast) and deep mode (slower)
# app/modules/wp_repair/modules/diagnose/diagnose.py
from __future__ import annotations

import posixpath
from typing import Dict, Any

from ..sftp.connect import sftp_connect

def _exists(sftp, p: str) -> bool:
    try:
        sftp.stat(p)
        return True
    except Exception:
        return False

def _read_text(sftp, p: str, max_bytes: int = 200_000) -> str:
    f = sftp.open(p, "r")
    try:
        data = f.read(max_bytes)
        if isinstance(data, bytes):
            return data.decode("utf-8", errors="replace")
        return str(data)
    finally:
        f.close()

def run_diagnose(host: str, port: int, username: str, password: str, wp_root: str) -> Dict[str, Any]:
    client = sftp_connect(host, port, username, password)
    sftp = client.open_sftp()
    try:
        wp_root = posixpath.normpath(wp_root)
        if not wp_root.startswith("/"):
            wp_root = "/" + wp_root

        wp_config = posixpath.join(wp_root, "wp-config.php")
        version_php = posixpath.join(wp_root, "wp-includes", "version.php")
        maintenance = posixpath.join(wp_root, ".maintenance")
        htaccess = posixpath.join(wp_root, ".htaccess")
        wp_content = posixpath.join(wp_root, "wp-content")
        uploads = posixpath.join(wp_content, "uploads")

        res: Dict[str, Any] = {
            "wp_root": wp_root,
            "files": {
                "wp-config.php": _exists(sftp, wp_config),
                "version.php": _exists(sftp, version_php),
                ".htaccess": _exists(sftp, htaccess),
                ".maintenance": _exists(sftp, maintenance),
            },
            "paths": {
                "wp-content": _exists(sftp, wp_content),
                "uploads": _exists(sftp, uploads),
            },
            "wp_version": None,
        }

        if res["files"]["version.php"]:
            text = _read_text(sftp, version_php)
            # Minimal parsing: look for $wp_version = 'x.y.z';
            import re
            m = re.search(r"\$wp_version\s*=\s*'([^']+)'", text)
            if m:
                res["wp_version"] = m.group(1)

        return res
    finally:
        try:
            sftp.close()
        except Exception:
            pass
        try:
            client.close()
        except Exception:
            pass
