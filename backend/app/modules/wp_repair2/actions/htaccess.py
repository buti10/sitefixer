import posixpath
import time
import uuid
from typing import Optional

from ..audit import audit_started, audit_success, audit_failed
from ..quarantine_sftp import (
    ensure_quarantine_dirs,
    move_into_quarantine,
    write_manifest,
    quarantine_action_dir,
)

WP_HTACCESS_DEFAULT = """# BEGIN WordPress
<IfModule mod_rewrite.c>
RewriteEngine On
RewriteBase /
RewriteRule ^index\\.php$ - [L]
RewriteCond %{REQUEST_FILENAME} !-f
RewriteCond %{REQUEST_FILENAME} !-d
RewriteRule . /index.php [L]
</IfModule>
# END WordPress
"""

def reset_htaccess_sftp(*, actor, sftp, root_path, dry_run=True, keep_custom_above=False, ticket_id: Optional[int]=None):
    action_id = f"htaccess_reset:{uuid.uuid4().hex}"
    root = root_path.rstrip("/") or "/"
    htaccess_path = posixpath.join(root, ".htaccess")

    params = {
        "dry_run": bool(dry_run),
        "keep_custom_above": bool(keep_custom_above),
        "ticket_id": ticket_id,
    }

    audit_started(actor=actor, root_path=root, action_id=action_id, params=params, meta={"ticket_id": ticket_id})

    existed = True
    try:
        sftp.stat(htaccess_path)
    except Exception:
        existed = False

    try:
        qdir = quarantine_action_dir(root, action_id)

        # Dry-Run: nur Plan + Audit (kein Write)
        if dry_run:
            res = {
                "ok": True,
                "action_id": action_id,
                "dry_run": True,
                "path": htaccess_path,
                "exists": existed,
                "quarantine_dir": qdir,
                "message": "Dry-Run: would replace .htaccess and store backup in sitefixer-quarantaene/",
            }
            audit_success(actor=actor, root_path=root, action_id=action_id, params=params, result=res, meta={"ticket_id": ticket_id})
            return res

        ensure_quarantine_dirs(sftp, root, action_id)

        backup_path = None
        if existed:
            # move original into quarantine/before/.htaccess
            backup_path = move_into_quarantine(
                sftp=sftp,
                root_path=root,
                action_id=action_id,
                target_path=htaccess_path,
                rel_name=".htaccess",
            )

        # write new htaccess atomically
        content = WP_HTACCESS_DEFAULT.strip() + "\n"
        tmp = htaccess_path + f".tmp_{int(time.time())}"
        with sftp.open(tmp, "w") as f:
            f.write(content)

        try:
            sftp.posix_rename(tmp, htaccess_path)
        except Exception:
            sftp.rename(tmp, htaccess_path)

        manifest = {
            "version": 1,
            "action_id": action_id,
            "created_at": int(time.time()),
            "root_path": root,
            "entries": [
                {
                    "op": "file_replace",
                    "target": htaccess_path,
                    "backup": backup_path,
                    "target_existed": bool(existed),
                }
            ],
            "meta": {"ticket_id": ticket_id, "kind": "htaccess_reset"},
        }

        mpath = write_manifest(sftp, root, action_id, manifest)

        res = {
            "ok": True,
            "action_id": action_id,
            "dry_run": False,
            "path": htaccess_path,
            "written": True,
            "backup_path": backup_path,
            "manifest": mpath,
            "quarantine_dir": qdir,
            "rollback_available": True,
        }
        audit_success(actor=actor, root_path=root, action_id=action_id, params=params, result=res, meta={"ticket_id": ticket_id})
        return res

    except Exception as e:
        audit_failed(actor=actor, root_path=root, action_id=action_id, params=params, error=str(e), meta={"ticket_id": ticket_id})
        return {"ok": False, "action_id": action_id, "error": str(e), "path": htaccess_path}
