# app/modules/wp_repair/modules/themes/ops.py
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.modules.wp_repair.modules.sftp.connect import sftp_connect


def themes_restore_apply(
    host: str,
    port: int,
    username: str,
    password: str,
    *,
    wp_root: str,
    slugs: List[str],
    themes_dir: Optional[str] = None,
    connect_timeout: int = 15,
    op_timeout: int = 20,
) -> Dict[str, Any]:
    """
    Restore (undo disable) themes by renaming:
      wp-content/themes/<slug>.disabled  ->  wp-content/themes/<slug>

    Returns:
      {
        "ok": True,
        "counts": {"restored": X, "skipped": Y, "errors": Z},
        "restored": [{slug,src,dst}],
        "skipped": [{slug,src,dst,reason}],
        "errors":  [{slug,src,dst,error}]
      }
    """
    if not wp_root:
        raise ValueError("wp_root required")

    themes_dir = themes_dir or (wp_root.rstrip("/") + "/wp-content/themes")

    client = sftp_connect(
        host,
        port,
        username,
        password,
        connect_timeout=connect_timeout,
        op_timeout=op_timeout,
    )
    sftp = client.open_sftp()

    restored: List[dict] = []
    skipped: List[dict] = []
    errors: List[dict] = []

    def exists(p: str) -> bool:
        try:
            sftp.stat(p)
            return True
        except Exception:
            return False

    try:
        for slug in slugs or []:
            slug = (slug or "").strip()
            if not slug:
                continue

            src = f"{themes_dir.rstrip('/')}/{slug}.disabled"
            dst = f"{themes_dir.rstrip('/')}/{slug}"

            if not exists(src):
                skipped.append({"slug": slug, "src": src, "dst": dst, "reason": "src_missing"})
                continue

            # wenn dst schon existiert, NICHT überschreiben (sicherheits-first)
            if exists(dst):
                skipped.append({"slug": slug, "src": src, "dst": dst, "reason": "dst_exists"})
                continue

            try:
                sftp.rename(src, dst)
                restored.append({"slug": slug, "src": src, "dst": dst})
            except Exception as e:
                errors.append({"slug": slug, "src": src, "dst": dst, "error": str(e)})

        return {
            "ok": True,
            "counts": {"restored": len(restored), "skipped": len(skipped), "errors": len(errors)},
            "restored": restored,
            "skipped": skipped,
            "errors": errors,
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
