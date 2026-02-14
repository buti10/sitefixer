#app/modules/wp_repair/routes.py
from __future__ import annotations

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import get_jwt_identity
from .services import start_run, finish_run, log_action, add_artifact
from .models import RepairRun, RepairActionLog, RepairArtifact

from app.wp_bridge import get_kundendetails

from .diagnose import run_diagnose
from .sftp_sessions import get_sftp_client
from .audit import read_audit_events

from .actions.cache import disable_dropins_sftp, remove_maintenance_mode_sftp
from .actions.permissions import normalize_permissions_sftp
from .actions.htaccess import reset_htaccess_sftp


from .session_store import store
from .sftp import SftpCreds, connect_sftp, sftp_ls, find_wp_roots

bp = Blueprint("wp_repair", __name__, url_prefix="/api/wp-repair")


def _actor() -> str:
    try:
        ident = get_jwt_identity()
        return str(ident) if ident is not None else "system"
    except Exception:
        return "system"


@bp.post("/diagnose")
def diagnose_route():
    data = request.get_json(silent=True) or {}

    root_path = (data.get("root_path") or "").strip()
    base_url = (data.get("base_url") or "").strip()
    session_id = (data.get("session_id") or "").strip()

    if not root_path or not base_url or not session_id:
        return jsonify({"ok": False, "error": "root_path, base_url, session_id are required"}), 400

    res = run_diagnose(
        root_path=root_path,
        base_url=base_url,
        session_id=session_id,
        verify_ssl=bool(data.get("verify_ssl", True)),
        capture_snippet=bool(data.get("capture_snippet", True)),
        tail_lines=int(data.get("tail_lines", 300)),
        redact_logs=bool(data.get("redact_logs", True)),
    )
    return jsonify(res)


# -------------------------
# Schnell-Fixes (SFTP)
# -------------------------

@bp.post("/fix/htaccess/reset")
def htaccess_reset_route():
    data = request.get_json(silent=True) or {}

    root_path = (data.get("root_path") or "").strip()
    session_id = (data.get("session_id") or "").strip()
    ticket_id = data.get("ticket_id")
    dry_run = bool(data.get("dry_run", True))
    keep_custom_above = bool(data.get("keep_custom_above", False))

    if not root_path or not session_id:
        return jsonify({"ok": False, "error": "root_path and session_id are required"}), 400

    try:
        client, sftp = get_sftp_client(session_id)
    except Exception as e:
        return jsonify({"ok": False, "error": f"SFTP session invalid: {e}"}), 401

    try:
        result = reset_htaccess_sftp(
            actor=_actor(),
            sftp=sftp,
            root_path=root_path,
            dry_run=dry_run,
            keep_custom_above=keep_custom_above,
            ticket_id=ticket_id,
        )

        # DB log (nur wenn nicht dry-run oder auch dry-run loggen? -> ich logge BEIDES, weil Verlauf wichtig ist)
        _db_log_fix(ticket_id=ticket_id, root_path=root_path, action_key="htaccess_reset", result=result)

        return jsonify(result), (200 if result.get("ok") else 500)

    except Exception as e:
        current_app.logger.exception("htaccess reset failed")
        return jsonify({"ok": False, "error": str(e)}), 500

    finally:
        try:
            sftp.close()
            client.close()
        except Exception:
            pass



@bp.post("/fix/permissions/normalize")
def permissions_normalize_route():
    data = request.get_json(silent=True) or {}

    root_path = (data.get("root_path") or "").strip()
    session_id = (data.get("session_id") or "").strip()
    ticket_id = data.get("ticket_id")
    target = (data.get("target") or "").strip()
    dry_run = bool(data.get("dry_run", True))

    if not root_path or not session_id:
        return jsonify({"ok": False, "error": "root_path and session_id are required"}), 400

    try:
        client, sftp = get_sftp_client(session_id)
    except Exception as e:
        return jsonify({"ok": False, "error": f"SFTP session invalid: {e}"}), 401

    try:
        result = normalize_permissions_sftp(
            actor=_actor(),
            sftp=sftp,
            root_path=root_path,
            target_rel_or_abs=target,
            dry_run=dry_run,
            ticket_id=ticket_id,
        )

        _db_log_fix(ticket_id=ticket_id, root_path=root_path, action_key="permissions_normalize", result=result)

        return jsonify(result), (200 if result.get("ok") else 500)

    except Exception as e:
        current_app.logger.exception("permissions normalize failed")
        return jsonify({"ok": False, "error": str(e)}), 500

    finally:
        try:
            sftp.close()
            client.close()
        except Exception:
            pass






@bp.post("/fix/maintenance/remove")
def maintenance_remove_route():
    data = request.get_json(silent=True) or {}

    root_path = (data.get("root_path") or "").strip()
    session_id = (data.get("session_id") or "").strip()
    ticket_id = data.get("ticket_id")
    dry_run = bool(data.get("dry_run", True))

    if not root_path or not session_id:
        return jsonify({"ok": False, "error": "root_path and session_id are required"}), 400

    try:
        client, sftp = get_sftp_client(session_id)
    except Exception as e:
        return jsonify({"ok": False, "error": f"SFTP session invalid: {e}"}), 401

    try:
        result = remove_maintenance_mode_sftp(
            actor=_actor(),
            sftp=sftp,
            root_path=root_path,
            dry_run=dry_run,
            ticket_id=ticket_id,
        )

        _db_log_fix(ticket_id=ticket_id, root_path=root_path, action_key="maintenance_remove", result=result)

        return jsonify(result), (200 if result.get("ok") else 500)

    except Exception as e:
        current_app.logger.exception("maintenance remove failed")
        return jsonify({"ok": False, "error": str(e)}), 500

    finally:
        try:
            sftp.close()
            client.close()
        except Exception:
            pass



# -------------------------
# SFTP Wizard
# -------------------------

def _ticket_sftp_access(ticket: dict) -> tuple[str, str, str, int]:
    host = ticket.get("ftp_host") or ticket.get("ftp_server") or ""
    user = ticket.get("ftp_user") or ""
    pw = ticket.get("ftp_pass") or ""
    port = int(ticket.get("ftp_port") or ticket.get("sftp_port") or 22)

    if not host or not user or not pw:
        raise ValueError("Ticket hat keine vollständigen SFTP Zugangsdaten (host/user/pass).")

    return host, user, pw, port


@bp.post("/tickets/<int:ticket_id>/sftp/connect")
def sftp_connect_route(ticket_id: int):
    ticket = get_kundendetails(ticket_id)
    if not ticket:
        return jsonify({"error": "Ticket nicht gefunden"}), 404

    try:
        host, user, pw, port = _ticket_sftp_access(ticket)

        client, sftp = connect_sftp(SftpCreds(host=host, username=user, password=pw, port=port))
        sftp.close()
        client.close()

        sid = store.create({"host": host, "user": user, "pass": pw, "port": port}, ttl_seconds=1800)
        return jsonify({"sftp_session_id": sid, "expires_in": 1800})

    except Exception as e:
        return jsonify({"error": str(e)}), 400


@bp.get("/sftp/<session_id>/projects")
def sftp_projects_route(session_id: str):
    s = store.get(session_id)
    if not s:
        return jsonify({"error": "Session ungültig oder abgelaufen."}), 400

    creds = SftpCreds(
        host=s.data["host"],
        username=s.data["user"],
        password=s.data["pass"],
        port=int(s.data.get("port", 22)),
    )

    try:
        client, sftp = connect_sftp(creds)
        items = find_wp_roots(sftp, start="/", max_depth=7)
        sftp.close()
        client.close()
        return jsonify({"items": items})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@bp.get("/sftp/<session_id>/ls")
def sftp_ls_route(session_id: str):
    s = store.get(session_id)
    if not s:
        return jsonify({"error": "Session ungültig oder abgelaufen."}), 400

    path = (request.args.get("path") or "/").strip() or "/"
    creds = SftpCreds(
        host=s.data["host"],
        username=s.data["user"],
        password=s.data["pass"],
        port=int(s.data.get("port", 22)),
    )

    try:
        client, sftp = connect_sftp(creds)
        items = sftp_ls(sftp, path)
        sftp.close()
        client.close()
        return jsonify({"items": items})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@bp.post("/tickets/<int:ticket_id>/root")
def set_root_route(ticket_id: int):
    data = request.get_json(silent=True) or {}
    root_path = (data.get("root_path") or "").strip()
    if not root_path:
        return jsonify({"error": "root_path is required"}), 400

    key = f"root:{ticket_id}"
    store.create({"key": key, "root_path": root_path}, ttl_seconds=7 * 24 * 3600)
    return jsonify({"ok": True, "root_path": root_path})


# -------------------------
# Audit / Verlauf
# -------------------------

@bp.get("/actions")
def actions_list():
    root_path = (request.args.get("root_path") or "").strip()
    ticket_id = request.args.get("ticket_id", type=int)

    items = read_audit_events(limit=50, root_path=root_path, ticket_id=ticket_id)
    return jsonify({"ok": True, "items": items})


from .quarantine_sftp import rollback_from_manifest
from .audit import audit_started, audit_success, audit_failed

@bp.post("/actions/<action_id>/rollback")
def rollback_action(action_id: str):
    data = request.get_json(silent=True) or {}
    root_path = (data.get("root_path") or "").strip()
    session_id = (data.get("session_id") or "").strip()
    ticket_id = data.get("ticket_id")

    if not root_path or not session_id:
        return jsonify({"ok": False, "error": "root_path and session_id are required"}), 400

    try:
        client, sftp = get_sftp_client(session_id)
    except Exception as e:
        return jsonify({"ok": False, "error": f"SFTP session invalid: {e}"}), 401

    rollback_event_id = f"rollback:{action_id}"
    params = {"root_path": root_path, "ticket_id": ticket_id, "rollback_of": action_id}

    try:
        audit_started(actor=_actor(), root_path=root_path, action_id=rollback_event_id, params=params, meta={"ticket_id": ticket_id})
        res = rollback_from_manifest(sftp=sftp, root_path=root_path, action_id=action_id)
        if res.get("ok"):
            audit_success(actor=_actor(), root_path=root_path, action_id=rollback_event_id, params=params, result=res, meta={"ticket_id": ticket_id})
            return jsonify(res), 200
        audit_failed(actor=_actor(), root_path=root_path, action_id=rollback_event_id, params=params, error="rollback had errors", result=res, meta={"ticket_id": ticket_id})
        return jsonify(res), 500

    except Exception as e:
        audit_failed(actor=_actor(), root_path=root_path, action_id=rollback_event_id, params=params, error=str(e), meta={"ticket_id": ticket_id})
        return jsonify({"ok": False, "error": str(e), "action_id": action_id}), 500

    finally:
        try:
            sftp.close()
            client.close()
        except Exception:
            pass

# -------------------------
# Cache / Drop-ins
# -------------------------

@bp.post("/fix/cache/disable-dropins")
def cache_disable_dropins_route():
    data = request.get_json(silent=True) or {}

    root_path = (data.get("root_path") or "").strip()
    session_id = (data.get("session_id") or "").strip()
    ticket_id = data.get("ticket_id")
    dry_run = bool(data.get("dry_run", True))

    if not root_path or not session_id:
        return jsonify({"ok": False, "error": "root_path and session_id are required"}), 400

    try:
        client, sftp = get_sftp_client(session_id)
    except Exception as e:
        return jsonify({"ok": False, "error": f"SFTP session invalid: {e}"}), 401

    try:
        result = disable_dropins_sftp(
            actor=_actor(),
            sftp=sftp,
            root_path=root_path,
            dry_run=dry_run,
            ticket_id=ticket_id,
        )

        _db_log_fix(ticket_id=ticket_id, root_path=root_path, action_key="disable_dropins", result=result)

        return jsonify(result), (200 if result.get("ok") else 500)

    except Exception as e:
        current_app.logger.exception("disable dropins failed")
        return jsonify({"ok": False, "error": str(e)}), 500

    finally:
        try:
            sftp.close()
            client.close()
        except Exception:
            pass

def _db_log_fix(*, ticket_id: int | None, root_path: str, action_key: str, result: dict, actor_user_id=None):
    """
    Spiegelt Fix-Ergebnis in DB (Run + ActionLog + Artifact falls Manifest vorhanden).
    Fail-safe: DB-Fehler dürfen Fix nicht kaputt machen.
    """
    if not ticket_id:
        return

    try:
        run = start_run(ticket_id=ticket_id, kind="fix", root_path=root_path, actor_user_id=actor_user_id)

        log_action(
            run_id=run.id,
            ticket_id=ticket_id,
            action_key=action_key,
            status="ok" if result.get("ok") else "fail",
            message=result.get("message") or result.get("note") or "",
            details=result,
        )

        # Manifest/Quarantine als Artifact speichern (falls vorhanden)
        if result.get("manifest"):
            add_artifact(
                run_id=run.id,
                ticket_id=ticket_id,
                type_="manifest",
                path=result["manifest"],
                meta={"action_key": action_key, "action_id": result.get("action_id")},
            )
        if result.get("quarantine_dir"):
            add_artifact(
                run_id=run.id,
                ticket_id=ticket_id,
                type_="quarantine_dir",
                path=result["quarantine_dir"],
                meta={"action_key": action_key, "action_id": result.get("action_id")},
            )
        if result.get("backup_path"):
            add_artifact(
                run_id=run.id,
                ticket_id=ticket_id,
                type_="backup_path",
                path=result["backup_path"],
                meta={"action_key": action_key, "action_id": result.get("action_id")},
            )

        finish_run(run, "success" if result.get("ok") else "failed", result)

    except Exception:
        # DB logging darf niemals den Fix kaputt machen
        current_app.logger.exception("DB log for fix failed")
        return

# -------------------------
# DB Verlauf (Runs + Details)
# -------------------------

@bp.get("/db/runs")
def db_runs_list():
    """
    Listet die letzten Runs für ein Ticket.
    Frontend: zeigt Verlauf-Timeline / Tabelle.
    """
    ticket_id = request.args.get("ticket_id", type=int)
    if not ticket_id:
        return jsonify({"ok": False, "error": "ticket_id is required"}), 400

    try:
        rows = (
            RepairRun.query
            .filter_by(ticket_id=ticket_id)
            .order_by(RepairRun.started_at.desc())
            .limit(100)
            .all()
        )

        items = []
        for r in rows:
            items.append({
                "id": r.id,
                "ticket_id": r.ticket_id,
                "kind": r.kind,
                "status": r.status,
                "root_path": r.root_path,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "finished_at": r.finished_at.isoformat() if r.finished_at else None,
                "summary": r.summary_json,
            })

        return jsonify({"ok": True, "items": items}), 200

    except Exception as e:
        current_app.logger.exception("db_runs_list failed")
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.get("/db/runs/<int:run_id>")
def db_run_detail(run_id: int):
    """
    Liefert Details eines Runs inkl. Actions + Artifacts.
    Frontend: Detailansicht (was wurde gemacht, rollback möglich via action_id).
    """
    try:
        r = RepairRun.query.get(run_id)
        if not r:
            return jsonify({"ok": False, "error": "Run nicht gefunden"}), 404

        actions = (
            RepairActionLog.query
            .filter_by(run_id=run_id)
            .order_by(RepairActionLog.created_at.asc())
            .all()
        )

        artifacts = (
            RepairArtifact.query
            .filter_by(run_id=run_id)
            .order_by(RepairArtifact.created_at.asc())
            .all()
        )

        run_obj = {
            "id": r.id,
            "ticket_id": r.ticket_id,
            "kind": r.kind,
            "status": r.status,
            "root_path": r.root_path,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
            "summary": r.summary_json,
        }

        actions_out = []
        for a in actions:
            actions_out.append({
                "id": a.id,
                "run_id": a.run_id,
                "ticket_id": a.ticket_id,
                "action_key": a.action_key,
                "status": a.status,
                "message": a.message,
                "details": a.details_json,
                "created_at": a.created_at.isoformat() if a.created_at else None,
                # convenience: action_id direkt oben rausziehen (falls in details)
                "action_id": (a.details_json or {}).get("action_id"),
                "rollback_available": bool((a.details_json or {}).get("rollback_available")),
            })

        artifacts_out = []
        for x in artifacts:
            artifacts_out.append({
                "id": x.id,
                "run_id": x.run_id,
                "ticket_id": x.ticket_id,
                "type": x.type,
                "path": x.path,
                "sha256": x.sha256,
                "size": x.size,
                "meta": x.meta_json,
                "created_at": x.created_at.isoformat() if x.created_at else None,
            })

        return jsonify({
            "ok": True,
            "run": run_obj,
            "actions": actions_out,
            "artifacts": artifacts_out,
        }), 200

    except Exception as e:
        current_app.logger.exception("db_run_detail failed")
        return jsonify({"ok": False, "error": str(e)}), 500
