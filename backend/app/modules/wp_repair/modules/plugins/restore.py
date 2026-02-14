from __future__ import annotations

import posixpath
from typing import Any, Dict, List

from app.modules.wp_repair.modules.sftp.connect import sftp_connect


def _is_safe_slug(slug: str) -> bool:
    if not slug or "/" in slug or "\\" in slug or ".." in slug:
        return False
    return True


def plugins_restore_apply(
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
    Restore disabled plugins by renaming:
      wp-content/plugins/<slug>.disabled -> wp-content/plugins/<slug>
    """
    slugs = [str(s).strip().strip("/") for s in (slugs or []) if str(s).strip()]
    slugs = [s for s in slugs if _is_safe_slug(s)]

    client = sftp_connect(
        host=host,
        port=int(port),
        username=username,
        password=password,
        connect_timeout=connect_timeout,
        op_timeout=op_timeout,
    )
    sftp = client.open_sftp()

    restored = []
    skipped = []
    errors = []

    plugins_dir = posixpath.join(wp_root.rstrip("/"), "wp-content", "plugins")

    try:
        for slug in slugs:
            dst = posixpath.join(plugins_dir, slug)
            src = dst + ".disabled"

            # src missing => skip
            try:
                sftp.stat(src)
            except FileNotFoundError:
                skipped.append({"slug": slug, "src": src, "dst": dst, "reason": "src_missing"})
                continue
            except Exception as e:
                errors.append({"slug": slug, "src": src, "dst": dst, "error": f"stat(src) failed: {e}"})
                continue

            # dst exists => skip (collision)
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
            sftp.close()
        except Exception:
            pass
        try:
            client.close()
        except Exception:
            pass