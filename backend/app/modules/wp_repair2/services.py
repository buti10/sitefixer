#app/modules/wp_repair/services.py
from __future__ import annotations
from typing import Dict, Any, Optional, Tuple
import os
import json
import hashlib
import datetime as dt

from flask import current_app

from app.extensions import db
from .models import RepairRun, RepairActionLog, RepairArtifact
from .session_store import store
from .sftp import SftpCreds, connect_sftp, sftp_ls, find_wp_roots

ART_BASE = "/var/www/sitefixer/repair_artifacts"

def _sha256_bytes(b: bytes) -> str:
    h = hashlib.sha256()
    h.update(b)
    return h.hexdigest()

def _ensure_dir(p: str) -> None:
    os.makedirs(p, exist_ok=True)

def _ticket_access(ticket: Dict[str, Any]) -> Tuple[str, str, str, int]:
    # Passe hier an dein Ticket-Schema an (du hast ftp_host/ftp_user/ftp_pass etc.)
    host = ticket.get("ftp_host") or ticket.get("ftp_server") or ""
    user = ticket.get("ftp_user") or ""
    pw = ticket.get("ftp_pass") or ""
    port = int(ticket.get("ftp_port") or ticket.get("sftp_port") or 22)
    if not host or not user or not pw:
        raise ValueError("Ticket hat keine vollständigen SFTP Zugangsdaten (host/user/pass).")
    return host, user, pw, port

def start_run(ticket_id: int, kind: str, root_path: Optional[str] = None, actor_user_id: Optional[int] = None) -> RepairRun:
    run = RepairRun(ticket_id=ticket_id, kind=kind, root_path=root_path, actor_user_id=actor_user_id, status="running")
    db.session.add(run)
    db.session.commit()
    return run

def finish_run(run: RepairRun, status: str, summary: Optional[Dict[str, Any]] = None) -> None:
    run.status = status
    run.finished_at = dt.datetime.utcnow()
    run.summary_json = summary or None
    db.session.commit()

def log_action(run_id: int, ticket_id: int, action_key: str, status: str, message: str = "", details: Optional[Dict[str, Any]] = None) -> None:
    row = RepairActionLog(
        run_id=run_id, ticket_id=ticket_id, action_key=action_key,
        status=status, message=message, details_json=details or None
    )
    db.session.add(row)
    db.session.commit()

def add_artifact(run_id: int, ticket_id: int, type_: str, path: str, content: Optional[bytes] = None, meta: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    sha = None
    size = None
    if content is not None:
        sha = _sha256_bytes(content)
        size = len(content)
    row = RepairArtifact(run_id=run_id, ticket_id=ticket_id, type=type_, path=path, sha256=sha, size=size, meta_json=meta or None)
    db.session.add(row)
    db.session.commit()
    return {"id": row.id, "type": type_, "path": path, "sha256": sha, "size": size}

# ---- Core service calls used by frontend ----

def sftp_connect(ticket_id: int, ticket: Dict[str, Any]) -> Dict[str, Any]:
    host, user, pw, port = _ticket_access(ticket)
    # Validate credentials by real connect
    client, sftp = connect_sftp(SftpCreds(host=host, username=user, password=pw, port=port))
    # store only creds; open connection per request (simple & robust)
    sftp.close()
    client.close()
    sid = store.create({"host": host, "user": user, "pass": pw, "port": port}, ttl_seconds=1800)
    return {"sftp_session_id": sid, "expires_in": 1800}

def sftp_projects(session_id: str) -> Dict[str, Any]:
    s = store.get(session_id)
    if not s:
        return {"error": "Session ungültig oder abgelaufen."}
    creds = SftpCreds(host=s.data["host"], username=s.data["user"], password=s.data["pass"], port=s.data.get("port", 22))
    client, sftp = connect_sftp(creds)
    try:
        items = find_wp_roots(sftp, start="/", max_depth=7)
        return {"items": items}
    finally:
        sftp.close()
        client.close()

def sftp_ls_path(session_id: str, path: str) -> Dict[str, Any]:
    s = store.get(session_id)
    if not s:
        return {"error": "Session ungültig oder abgelaufen."}
    creds = SftpCreds(host=s.data["host"], username=s.data["user"], password=s.data["pass"], port=s.data.get("port", 22))
    client, sftp = connect_sftp(creds)
    try:
        items = sftp_ls(sftp, path or "/")
        return {"items": items}
    finally:
        sftp.close()
        client.close()

def set_root(ticket_id: int, root_path: str) -> Dict[str, Any]:
    # Minimal: speichere root_path in letzter RepairRun summary oder Setting/Meta.
    # Empfohlen: eigenes TicketMeta Feld. Für jetzt: create a run entry "set_root".
    run = start_run(ticket_id, kind="set_root", root_path=root_path)
    log_action(run.id, ticket_id, "set_root", "ok", "Root gesetzt", {"root_path": root_path})
    finish_run(run, "success", {"root_path": root_path})
    return {"ok": True, "root_path": root_path, "run_id": run.id}

# ---- Diagnose (minimal stub) ----
def diagnose(ticket_id: int) -> Dict[str, Any]:
    run = start_run(ticket_id, kind="diagnose")
    try:
        # TODO: echte Diagnose später (HTTP, WP detection, core hash etc.)
        result = {
            "triage": {"frontend": "unknown", "login": "unknown", "admin": "unknown"},
            "inventory": {"wp_detected": None, "wp_version": None, "plugins": []},
            "suspected_cause": "TBD",
            "run_id": run.id,
        }
        log_action(run.id, ticket_id, "diagnose", "ok", "Diagnose (stub)", result)
        finish_run(run, "success", {"note": "stub"})
        return result
    except Exception as e:
        log_action(run.id, ticket_id, "diagnose", "fail", str(e))
        finish_run(run, "failed", {"error": str(e)})
        return {"error": str(e), "run_id": run.id}

# ---- Fixes (minimal: audit + artifact stub) ----
def fix_htaccess(ticket_id: int) -> Dict[str, Any]:
    run = start_run(ticket_id, kind="fix")
    try:
        # TODO: echte Umsetzung mit SFTP + root_path + backup
        payload = {"ok": True, "note": "htaccess fix stub", "run_id": run.id}
        log_action(run.id, ticket_id, "fix_htaccess", "ok", "Stub", payload)
        finish_run(run, "success", {"action": "fix_htaccess"})
        return payload
    except Exception as e:
        log_action(run.id, ticket_id, "fix_htaccess", "fail", str(e))
        finish_run(run, "failed", {"error": str(e)})
        return {"error": str(e), "run_id": run.id}

def fix_dropins(ticket_id: int) -> Dict[str, Any]:
    run = start_run(ticket_id, kind="fix")
    try:
        payload = {"ok": True, "note": "dropins fix stub", "run_id": run.id}
        log_action(run.id, ticket_id, "fix_dropins", "ok", "Stub", payload)
        finish_run(run, "success", {"action": "fix_dropins"})
        return payload
    except Exception as e:
        log_action(run.id, ticket_id, "fix_dropins", "fail", str(e))
        finish_run(run, "failed", {"error": str(e)})
        return {"error": str(e), "run_id": run.id}

def fix_permissions(ticket_id: int, dry_run: bool = True) -> Dict[str, Any]:
    run = start_run(ticket_id, kind="fix")
    try:
        payload = {"ok": True, "dry_run": dry_run, "note": "permissions stub", "run_id": run.id}
        log_action(run.id, ticket_id, "fix_permissions", "ok", "Stub", payload)
        finish_run(run, "success", {"action": "fix_permissions", "dry_run": dry_run})
        return payload
    except Exception as e:
        log_action(run.id, ticket_id, "fix_permissions", "fail", str(e))
        finish_run(run, "failed", {"error": str(e)})
        return {"error": str(e), "run_id": run.id}

def fix_maintenance(ticket_id: int) -> Dict[str, Any]:
    run = start_run(ticket_id, kind="fix")
    try:
        payload = {"ok": True, "note": "maintenance stub", "run_id": run.id}
        log_action(run.id, ticket_id, "fix_maintenance", "ok", "Stub", payload)
        finish_run(run, "success", {"action": "fix_maintenance"})
        return payload
    except Exception as e:
        log_action(run.id, ticket_id, "fix_maintenance", "fail", str(e))
        finish_run(run, "failed", {"error": str(e)})
        return {"error": str(e), "run_id": run.id}

# ---- Audit endpoints helpers ----
def list_runs(ticket_id: int) -> Dict[str, Any]:
    rows = (RepairRun.query.filter_by(ticket_id=ticket_id).order_by(RepairRun.started_at.desc()).limit(50).all())
    return {"items": [{
        "id": r.id,
        "ticket_id": r.ticket_id,
        "kind": r.kind,
        "status": r.status,
        "root_path": r.root_path,
        "started_at": r.started_at.isoformat() if r.started_at else None,
        "finished_at": r.finished_at.isoformat() if r.finished_at else None,
        "summary": r.summary_json,
    } for r in rows]}

def run_detail(run_id: int) -> Dict[str, Any]:
    r = RepairRun.query.get(run_id)
    if not r:
        return {"error": "Run nicht gefunden"}
    actions = (RepairActionLog.query.filter_by(run_id=run_id).order_by(RepairActionLog.created_at.asc()).all())
    arts = (RepairArtifact.query.filter_by(run_id=run_id).order_by(RepairArtifact.created_at.asc()).all())
    return {
        "run": {
            "id": r.id, "ticket_id": r.ticket_id, "kind": r.kind, "status": r.status,
            "root_path": r.root_path,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            "summary": r.summary_json,
        },
        "actions": [{
            "id": a.id, "action_key": a.action_key, "status": a.status, "message": a.message,
            "details": a.details_json, "created_at": a.created_at.isoformat() if a.created_at else None
        } for a in actions],
        "artifacts": [{
            "id": x.id, "type": x.type, "path": x.path, "sha256": x.sha256, "size": x.size,
            "meta": x.meta_json, "created_at": x.created_at.isoformat() if x.created_at else None
        } for x in arts]
    }
