# app/modules/wp_repair/modules/themes/preview.py
from __future__ import annotations

import posixpath
from stat import S_ISDIR
from typing import Any, Dict, List

from app.modules.wp_repair.modules.sftp.connect import sftp_connect


def themes_preview(
    host: str,
    port: int,
    username: str,
    password: str,
    wp_root: str,
    *,
    max_themes: int = 500,
) -> Dict[str, Any]:
    """
    List themes in wp-content/themes.
    Detect disabled themes by suffix ".disabled".
    """
    wp_root = (wp_root or "").rstrip("/")
    themes_dir = posixpath.join(wp_root, "wp-content", "themes")

    client = sftp_connect(host, port, username, password)
    sftp = client.open_sftp()

    items: List[Dict[str, Any]] = []
    errors: List[Dict[str, str]] = []

    try:
        try:
            entries = sftp.listdir_attr(themes_dir)
        except Exception as e:
            return {"ok": False, "error": f"cannot_list_themes_dir: {e}", "themes_dir": themes_dir}

        for a in entries:
            if len(items) >= int(max_themes):
                break

            name = a.filename
            full = posixpath.join(themes_dir, name)

            try:
                if not S_ISDIR(a.st_mode):
                    continue
            except Exception:
                # if st_mode is missing, fall back to stat
                try:
                    st = sftp.stat(full)
                    if not S_ISDIR(st.st_mode):
                        continue
                except Exception:
                    continue

            disabled = False
            slug = name
            if name.endswith(".disabled"):
                disabled = True
                slug = name[: -len(".disabled")]

            items.append(
                {
                    "slug": slug,
                    "dir_name": name,
                    "path": full,
                    "enabled": not disabled,
                    "disabled": disabled,
                }
            )

        # stable sort: enabled first, then slug
        items.sort(key=lambda x: (x["disabled"], x["slug"].lower()))

        return {
            "ok": True,
            "themes_dir": themes_dir,
            "count": len(items),
            "items": items,
            "errors": errors[:50],
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
