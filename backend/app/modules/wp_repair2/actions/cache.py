#app/modules/wp_repair/actions/cache.py
from __future__ import annotations
import posixpath
import time
import uuid
from typing import Any, Dict, List, Optional

from ..audit import audit_started, audit_success, audit_failed
from ..quarantine_sftp import (
    sftp_exists,
    sftp_is_dir,
    ensure_quarantine_dirs,
    move_into_quarantine,
    write_manifest,
    quarantine_action_dir,
)





# =========================================================
# SFTP: Drop-ins disable (Repair-Beta uses SFTP session)
# =========================================================



def _pjoin(a: str, b: str) -> str:
    return posixpath.join(a.rstrip("/"), b.lstrip("/"))

def disable_dropins_sftp(
    *,
    actor: str,
    sftp,
    root_path: str,
    dry_run: bool = True,
    ticket_id: Optional[int] = None,
) -> Dict[str, Any]:
    action_id = f"dropins_quarantine:{uuid.uuid4().hex}"
    root = root_path.rstrip("/") or "/"

    wp_content = _pjoin(root, "wp-content")
    targets = [
        _pjoin(wp_content, "object-cache.php"),
        _pjoin(wp_content, "advanced-cache.php"),
        _pjoin(wp_content, "db.php"),
    ]

    params = {"dry_run": bool(dry_run), "ticket_id": ticket_id}
    audit_started(actor=actor, root_path=root, action_id=action_id, params=params, meta={"ticket_id": ticket_id})

    moved: List[Dict[str, Any]] = []
    try:
        qdir = quarantine_action_dir(root, action_id)

        if dry_run:
            for t in targets:
                if sftp_exists(sftp, t):
                    moved.append({"path": t, "would_move_to": f"{qdir}/before/{posixpath.basename(t)}"})
            res = {
                "ok": True,
                "action_id": action_id,
                "dry_run": True,
                "quarantine_dir": qdir,
                "planned": moved,
                "message": "Dry-Run: would move drop-ins into sitefixer-quarantaene/",
            }
            audit_success(actor=actor, root_path=root, action_id=action_id, params=params, result=res, meta={"ticket_id": ticket_id})
            return res

        ensure_quarantine_dirs(sftp, root, action_id)

        entries = []
        for t in targets:
            bp = move_into_quarantine(
                sftp=sftp,
                root_path=root,
                action_id=action_id,
                target_path=t,
                rel_name=posixpath.basename(t),
            )
            if bp:
                moved.append({"path": t, "backup_path": bp})
                entries.append({"op": "file_move", "target": t, "backup": bp})

        # detections only (unchanged)
        detections = {
            "cache_dir": _pjoin(wp_content, "cache") if sftp_is_dir(sftp, _pjoin(wp_content, "cache")) else None,
            "w3tc_config": _pjoin(wp_content, "w3tc-config") if sftp_is_dir(sftp, _pjoin(wp_content, "w3tc-config")) else None,
            "litespeed": _pjoin(wp_content, "litespeed") if sftp_is_dir(sftp, _pjoin(wp_content, "litespeed")) else None,
            "maintenance": _pjoin(root, ".maintenance") if sftp_exists(sftp, _pjoin(root, ".maintenance")) else None,
        }

        manifest = {
            "version": 1,
            "action_id": action_id,
            "created_at": int(time.time()),
            "root_path": root,
            "entries": entries,
            "meta": {"ticket_id": ticket_id, "kind": "dropins_disable"},
        }
        mpath = write_manifest(sftp, root, action_id, manifest)

        res = {
            "ok": True,
            "action_id": action_id,
            "dry_run": False,
            "moved": moved,
            "detections": detections,
            "manifest": mpath,
            "quarantine_dir": qdir,
            "rollback_available": True,
        }
        audit_success(actor=actor, root_path=root, action_id=action_id, params=params, result=res, meta={"ticket_id": ticket_id})
        return res

    except Exception as e:
        audit_failed(actor=actor, root_path=root, action_id=action_id, params=params, error=f"{type(e).__name__}: {e}", meta={"ticket_id": ticket_id})
        return {"ok": False, "action_id": action_id, "error": f"{type(e).__name__}: {e}"}


def remove_maintenance_mode_sftp(
    *,
    actor: str,
    sftp,
    root_path: str,
    dry_run: bool = True,
    ticket_id: Optional[int] = None,
) -> Dict[str, Any]:
    action_id = f"maintenance_quarantine:{uuid.uuid4().hex}"
    root = root_path.rstrip("/") or "/"
    m = _pjoin(root, ".maintenance")

    params = {"dry_run": bool(dry_run), "ticket_id": ticket_id}
    audit_started(actor=actor, root_path=root, action_id=action_id, params=params, meta={"ticket_id": ticket_id})

    try:
        qdir = quarantine_action_dir(root, action_id)

        if not sftp_exists(sftp, m):
            res = {"ok": True, "action_id": action_id, "removed": False, "path": m, "note": ".maintenance not present"}
            audit_success(actor=actor, root_path=root, action_id=action_id, params=params, result=res, meta={"ticket_id": ticket_id})
            return res

        if dry_run:
            res = {
                "ok": True,
                "action_id": action_id,
                "dry_run": True,
                "path": m,
                "would_move_to": f"{qdir}/before/.maintenance",
                "quarantine_dir": qdir,
            }
            audit_success(actor=actor, root_path=root, action_id=action_id, params=params, result=res, meta={"ticket_id": ticket_id})
            return res

        ensure_quarantine_dirs(sftp, root, action_id)
        bp = move_into_quarantine(sftp=sftp, root_path=root, action_id=action_id, target_path=m, rel_name=".maintenance")

        manifest = {
            "version": 1,
            "action_id": action_id,
            "created_at": int(time.time()),
            "root_path": root,
            "entries": [{"op": "file_move", "target": m, "backup": bp}],
            "meta": {"ticket_id": ticket_id, "kind": "maintenance_remove"},
        }
        mpath = write_manifest(sftp, root, action_id, manifest)

        res = {
            "ok": True,
            "action_id": action_id,
            "removed": True,
            "path": m,
            "backup_path": bp,
            "manifest": mpath,
            "quarantine_dir": qdir,
            "rollback_available": True,
        }
        audit_success(actor=actor, root_path=root, action_id=action_id, params=params, result=res, meta={"ticket_id": ticket_id})
        return res

    except Exception as e:
        audit_failed(actor=actor, root_path=root, action_id=action_id, params=params, error=f"{type(e).__name__}: {e}", meta={"ticket_id": ticket_id})
        return {"ok": False, "action_id": action_id, "error": f"{type(e).__name__}: {e}"}
