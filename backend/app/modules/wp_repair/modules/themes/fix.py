# app/modules/wp_repair/modules/themes/fix.py
from __future__ import annotations

import posixpath
from typing import Any, Dict, List

from app.modules.wp_repair.modules.sftp.connect import sftp_connect


def themes_disable_apply(
    host: str,
    port: int,
    username: str,
    password: str,
    wp_root: str,
    *,
    slugs: List[str],
) -> Dict[str, Any]:
    """
    Disable themes by renaming:
      wp-content/themes/<slug> -> wp-content/themes/<slug>.disabled
    """
    wp_root = (wp_root or "").rstrip("/")
    themes_dir = posixpath.join(wp_root, "wp-content", "themes")

    client = sftp_connect(host, port, username, password)
    sftp = client.open_sftp()

    disabled: List[Dict[str, str]] = []
    skipped: List[Dict[str, str]] = []
    errors: List[Dict[str, str]] = []

    try:
        for slug in slugs:
            slug = (slug or "").strip().strip("/")
            if not slug:
                continue

            src = posixpath.join(themes_dir, slug)
            dst = src + ".disabled"

            # dst exists -> skip
            try:
                sftp.stat(dst)
                skipped.append({"slug": slug, "src": src, "dst": dst, "reason": "dst_exists"})
                continue
            except FileNotFoundError:
                pass
            except Exception as e:
                errors.append({"slug": slug, "src": src, "dst": dst, "error": f"stat(dst) failed: {e}"})
                continue

            # src missing -> skip
            try:
                sftp.stat(src)
            except FileNotFoundError:
                skipped.append({"slug": slug, "src": src, "dst": dst, "reason": "src_missing"})
                continue
            except Exception as e:
                errors.append({"slug": slug, "src": src, "dst": dst, "error": f"stat(src) failed: {e}"})
                continue

            # rename
            try:
                sftp.rename(src, dst)
                disabled.append({"slug": slug, "src": src, "dst": dst})
            except Exception as e:
                errors.append({"slug": slug, "src": src, "dst": dst, "error": str(e)})

        return {
            "ok": True if (disabled or skipped) and not (not disabled and errors) else False,
            "disabled": disabled,
            "skipped": skipped,
            "errors": errors,
            "counts": {"disabled": len(disabled), "skipped": len(skipped), "errors": len(errors)},
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
