# app/modules/wp_repair/modules/themes/restore.py
from __future__ import annotations

import posixpath
from typing import Any, Dict, List

from app.modules.wp_repair.modules.sftp.connect import sftp_connect


def themes_restore_apply(
    host: str,
    port: int,
    username: str,
    password: str,
    *,
    wp_root: str,
    slugs: List[str],
    connect_timeout: int = 15,
    op_timeout: int = 20,
) -> Dict[str, Any]:
    """
    Restore disabled themes by renaming:
      wp-content/themes/<slug>.disabled  ->  wp-content/themes/<slug>

    Returns:
      {
        ok: True,
        restored: [{slug, src, dst}],
        skipped:  [{slug, src, dst, reason}],
        errors:   [{slug, src, dst, error}],
        counts:   {restored, skipped, errors}
      }
    """
    wp_root = (wp_root or "").rstrip("/")
    themes_dir = posixpath.join(wp_root, "wp-content", "themes")

    slugs = [str(s).strip().strip("/") for s in (slugs or []) if str(s).strip()]
    slugs = list(dict.fromkeys(slugs))  # dedupe preserve order

    restored: List[dict] = []
    skipped: List[dict] = []
    errors: List[dict] = []

    client = None
    sftp = None
    try:
        client = sftp_connect(
            host,
            port,
            username,
            password,
            connect_timeout=connect_timeout,
            op_timeout=op_timeout,
        )
        sftp = client.open_sftp()

        for slug in slugs:
            src = posixpath.join(themes_dir, slug + ".disabled")
            dst = posixpath.join(themes_dir, slug)

            # src must exist
            try:
                sftp.stat(src)
            except FileNotFoundError:
                skipped.append({"slug": slug, "src": src, "dst": dst, "reason": "src_missing"})
                continue
            except Exception as e:
                errors.append({"slug": slug, "src": src, "dst": dst, "error": f"stat(src) failed: {e}"})
                continue

            # dst must NOT exist (avoid overwrite)
            try:
                sftp.stat(dst)
                skipped.append({"slug": slug, "src": src, "dst": dst, "reason": "dst_exists"})
                continue
            except FileNotFoundError:
                pass
            except Exception as e:
                errors.append({"slug": slug, "src": src, "dst": dst, "error": f"stat(dst) failed: {e}"})
                continue

            # rename
            try:
                sftp.rename(src, dst)
                restored.append({"slug": slug, "src": src, "dst": dst})
            except Exception as e:
                errors.append({"slug": slug, "src": src, "dst": dst, "error": str(e)})

        return {
            "ok": True,
            "restored": restored,
            "skipped": skipped,
            "errors": errors,
            "counts": {
                "restored": len(restored),
                "skipped": len(skipped),
                "errors": len(errors),
            },
        }

    finally:
        try:
            if sftp is not None:
                sftp.close()
        except Exception:
            pass
        try:
            if client is not None:
                client.close()
        except Exception:
            pass
