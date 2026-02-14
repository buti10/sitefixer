# projects.py
# - Detect and list project root candidates (public_html/httpdocs/clickandbuilds/* etc.)
# - Normalize for UI:
#   - label (string)
#   - root_path (absolute path on the SFTP)
# app/modules/wp_repair/modules/sftp/projects.py
from __future__ import annotations

from typing import List, Dict
from .connect import sftp_connect

COMMON_ROOTS = [
    "/httpdocs", "/htdocs", "/public_html", "/www",
    "/clickandbuilds",
]

def sftp_discover_projects(host: str, port: int, username: str, password: str) -> List[Dict]:
    """
    Returns list of project root candidates:
    [{ "label": "...", "root_path": "..." }, ...]
    """
    client = sftp_connect(host, port, username, password)
    sftp = client.open_sftp()
    items: List[Dict] = []

    try:
        # Try common roots
        for root in COMMON_ROOTS:
            try:
                st = sftp.stat(root)
            except Exception:
                continue

            # clickandbuilds: list children projects
            if root == "/clickandbuilds":
                try:
                    for e in sftp.listdir_attr(root):
                        if str(e.longname).startswith("d"):
                            rp = f"{root}/{e.filename}"
                            items.append({"label": rp, "root_path": rp})
                except Exception:
                    pass
            else:
                items.append({"label": root, "root_path": root})

        # Deduplicate
        seen = set()
        uniq = []
        for it in items:
            if it["root_path"] in seen:
                continue
            seen.add(it["root_path"])
            uniq.append(it)
        return uniq
    finally:
        try:
            sftp.close()
        except Exception:
            pass
        try:
            client.close()
        except Exception:
            pass
