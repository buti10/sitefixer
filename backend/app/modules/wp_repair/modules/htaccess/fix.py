# fix.py
# - Decide correct template (single/multisite-subdir/multisite-subdomain)
# - Quarantine existing .htaccess into .sitefixer/quarantine/
# - Write template to .htaccess
# - Postcheck (exists, readable; optional HTTP probe)

from __future__ import annotations

import posixpath

from ..sftp.connect import sftp_connect


def _read_local_template(template_name: str) -> str:
    import os
    here = os.path.dirname(__file__)
    path = os.path.join(here, "templates", template_name)
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def apply_htaccess_fix(host: str, port: int, username: str, password: str, wp_root: str, template: str = "single.htaccess") -> dict:
    """
    Writes a clean .htaccess to wp_root/.htaccess.
    Caller must handle quarantine + audit.
    """
    wp_root = posixpath.normpath(wp_root)
    ht_path = posixpath.join(wp_root, ".htaccess")

    content = _read_local_template(template)

    client = sftp_connect(host, port, username, password)
    sftp = client.open_sftp()
    try:
        # write htaccess (overwrite)
        f = sftp.open(ht_path, "w")
        try:
            f.write(content)
        finally:
            f.close()

        return {"ok": True, "written": ht_path, "template": template}
    finally:
        try:
            sftp.close()
        except Exception:
            pass
        try:
            client.close()
        except Exception:
            pass
