# wp_repair.py — Single entry point (API / Orchestrator)
#
# Responsibilities
# - Expose endpoints for the internal Repair Wizard (employees).
# - Coordinate workflow steps:
#   1) SFTP connect
#   2) project discovery + selection
#   3) wp-root selection
#   4) diagnose
#   5) run a selected fix module
#   6) rollback
#
# What should NOT live here
# - No fix logic (htaccess/permissions/malware/etc.). Those live under modules/.
# - No templates/rules. Those live inside each module.
#
# app/modules/wp_repair/wp_repair.py

from __future__ import annotations

import time
import os
import secrets
import json
import posixpath
from rq import Queue
from redis import Redis

from typing import Dict, Any

from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models import User

# NOTE: add_finding was used below but not imported before
from app.modules.wp_repair.db_audit import set_action_status, add_file_op, add_finding, get_action_ctx


# Module imports (deine Skeleton-Struktur)
from .modules.sftp.connect import sftp_connect
from .modules.sftp.projects import sftp_discover_projects
from .modules.sftp.explorer import sftp_ls_safe, sftp_path_is_dir
from .modules.sftp.find_wp_root import find_wp_roots
from .modules.diagnose.diagnose import run_diagnose
from .modules.audit.routes import bp_audit
from app.modules.wp_repair.modules.malware.scan import malware_scan_apply
from .session_store import set_session

from .modules.audit.actions import (
    ensure_dirs,
    create_action,
    append_log,
    quarantine_move,
    rollback,
    read_text_remote,
    write_text_remote,
)

from .modules.htaccess.fix import apply_htaccess_fix
from .modules.permissions.fix import permissions_preview, permissions_apply
from .modules.maintenance.remove import remove_maintenance
from .modules.dropins.preview import dropins_preview
from .modules.dropins.fix import dropins_apply_disable

from .modules.core.preview import core_integrity_preview
from .modules.core.replace_preview import core_replace_preview as core_replace_preview_fn
from .modules.core.replace_apply import core_replace_apply as core_replace_apply_fn

from .modules.plugins.preview import plugins_preview
from .modules.plugins.fix import plugins_disable_plan
from app.modules.wp_repair.modules.plugins.recover import recover_preview, recover_apply
from .modules.themes.preview import themes_preview
from .modules.themes.fix import themes_disable_apply
from .modules.themes.scan import theme_code_scan_apply
from .modules.themes.restore import themes_restore_apply
from .modules.plugins.restore import plugins_restore_apply
from .modules.plugins.scan import plugin_code_scan_apply


# Database repair (wp-admin/maint/repair.php)
from .modules.database_repair.preview import db_repair_preview
from .modules.database_repair.scan import db_repair_scan
from .modules.database_repair.fix import db_repair_apply

from app.modules.wp_repair.modules.diagnostics.preview import diagnostics_preview
from app.modules.wp_repair.modules.diagnostics.enable import diagnostics_enable
from app.modules.wp_repair.modules.diagnostics.scan import diagnostics_scan
from app.modules.wp_repair.modules.diagnostics.fixes import diagnostics_apply_fix

from app.modules.wp_repair.modules.file_explorer.ls import explorer_ls
from app.modules.wp_repair.modules.file_explorer.read import explorer_read
from app.modules.wp_repair.modules.file_explorer.write import explorer_write
from app.modules.wp_repair.modules.file_explorer.ai_help import explorer_ai_help

from app.modules.wp_repair.modules.file_explorer.patch_ops import patch_preview, patch_apply
from app.modules.wp_repair.modules.file_explorer.patch_ops import patch_validate


# ---------------------------------------------------------------------
# DB Audit helper (never block fixes if DB fails)
# ---------------------------------------------------------------------
def _db_status(action_id: str, status: str, *, result=None, error=None, meta=None):
    try:
        set_action_status(action_id, status, result_json=result, error_json=error, meta_json=meta)
    except Exception:
        pass


def _meta_ensure(meta: dict) -> dict:
    # notes: string summary
    notes = meta.get("notes")
    if isinstance(notes, list):
        meta.setdefault("events", [])
        meta["events"].extend([str(x) for x in notes if x is not None])
        meta["notes"] = ""
    elif notes is None:
        meta["notes"] = ""
    else:
        meta["notes"] = str(notes)

    # events: list of strings
    if not isinstance(meta.get("events"), list):
        meta["events"] = []

    return meta


def _meta_event(meta: dict, line: str) -> None:
    _meta_ensure(meta)
    meta["events"].append(str(line))


def _meta_note(meta: dict, note: str) -> None:
    _meta_ensure(meta)
    meta["notes"] = str(note)


bp = Blueprint("wp_repair", __name__, url_prefix="/api/wp-repair")

bp.register_blueprint(bp_audit)


@bp.errorhandler(Exception)
def _repair_error(err):
    current_app.logger.exception("Unhandled wp_repair error")
    return jsonify({"ok": False, "error": str(err)}), 500


# ------------------------------------------------------------
# Simple in-memory session store (für Start ok)
# Später ersetzen durch Redis/DB, damit Restarts kein Problem sind.
# ------------------------------------------------------------
_SESSIONS: Dict[str, Dict[str, Any]] = {}
_SESSION_TTL_SECONDS = 60 * 30  # 30 Minuten


def _now() -> int:
    return int(time.time())


def _cleanup_sessions() -> None:
    now = _now()
    expired = [
        sid
        for sid, v in _SESSIONS.items()
        if now - v.get("ts", now) > _SESSION_TTL_SECONDS
    ]
    for sid in expired:
        _SESSIONS.pop(sid, None)


def _get_session(session_id: str) -> Dict[str, Any]:
    _cleanup_sessions()
    s = _SESSIONS.get(session_id)
    if not s:
        raise ValueError("Invalid or expired session_id")
    s["ts"] = _now()
    return s
def get_session_or_400(session_id: str):
    sid = (session_id or "").strip()
    if not sid:
        return None, (jsonify({"ok": False, "error": "Missing session_id"}), 400)
    try:
        return _get_session(sid), None
    except Exception as e:
        # Vereinheitlichte Fehlermeldung statt 500
        return None, (jsonify({"ok": False, "error": str(e)}), 400)

def _ensure_context(s: dict, data: dict) -> tuple[str | None, str | None]:
    # allow passing context in any POST
    pr = (data.get("project_root") or s.get("project_root") or "").strip()
    wr = (data.get("wp_root") or s.get("wp_root") or "").strip()

    if pr:
        s["project_root"] = pr
    if wr:
        # safety: wp_root must be inside project_root if project_root is known
        if pr:
            prn = pr.rstrip("/")
            if wr != prn and not wr.startswith(prn + "/"):
                raise ValueError("wp_root outside selected project_root")
        s["wp_root"] = wr

    return (s.get("project_root"), s.get("wp_root"))


@bp.get("/health")
def health():
    return jsonify({"ok": True})


# ------------------------------------------------------------
# Session start from ticket (JWT protected)
# ------------------------------------------------------------
@bp.post("/session/start")
@jwt_required()
def api_session_start():
    """
    Start session from frontend-provided ticket data.
    Expected JSON:
    {
      "ticket_id": 123,
      "domain": "...",
      "ftp_host": "...",
      "ftp_user": "...",
      "ftp_pass": "...",
      "ftp_port": 22   # optional
    }
    """
    data = request.get_json(silent=True) or {}
    ticket_id = int(data.get("ticket_id") or 0)
    if not ticket_id:
        return jsonify({"ok": False, "error": "Missing ticket_id"}), 400

    actor_user_id = int(get_jwt_identity())
    u = User.query.get(actor_user_id)
    actor_name = u.name if u else None

    domain = (data.get("domain") or "").strip()

    host = (data.get("ftp_host") or data.get("sftp_host") or "").strip()
    username = (data.get("ftp_user") or data.get("sftp_user") or "").strip()
    password = data.get("ftp_pass") or data.get("sftp_pass") or ""
    port = int(data.get("ftp_port") or data.get("sftp_port") or 22)

    if not host or not username or not password:
        return jsonify(
            {
                "ok": False,
                "error": "Missing SFTP credentials (ftp_host/ftp_user/ftp_pass)",
            }
        ), 400

    session_id = secrets.token_urlsafe(24)
    _SESSIONS[session_id] = {
        "ts": _now(),
        "host": host,
        "port": port,
        "username": username,
        "password": password,  # nur im RAM
        "domain": domain,
        "website_user": (data.get("website_user") or "").strip(),
        "website_pass": (data.get("website_pass") or ""),
        "website_login": (data.get("website_login") or "").strip(),
        "project_root": None,
        "wp_root": None,
        "ticket_id": ticket_id,
        "actor_user_id": actor_user_id,
        "actor_name": actor_name,
    }

    return jsonify({"ok": True, "session_id": session_id})


# ------------------------------------------------------------
# 1) SFTP connect (legacy/manual)
# ------------------------------------------------------------
@bp.post("/sftp/connect")
def api_sftp_connect():
    """
    Body JSON example:
    {
      "host": "example.com",
      "port": 22,
      "username": "user",
      "password": "secret"
    }
    """
    data = request.get_json(silent=True) or {}
    host = (data.get("host") or "").strip()
    port = int(data.get("port") or 22)
    username = (data.get("username") or "").strip()
    password = data.get("password") or ""

    if not host or not username or not password:
        return jsonify({"ok": False, "error": "Missing host/username/password"}), 400

    try:
        client_handle = sftp_connect(
            host=host, port=port, username=username, password=password
        )
    except Exception as e:
        current_app.logger.exception("SFTP connect failed")
        return jsonify({"ok": False, "error": str(e)}), 400

    session_id = secrets.token_urlsafe(24)
    _SESSIONS[session_id] = {
        "ts": _now(),
        "host": host,
        "port": port,
        "username": username,
        "password": password,
        "project_root": None,
        "wp_root": None,
    }

    try:
        client_handle.close()
    except Exception:
        pass

    return jsonify({"ok": True, "session_id": session_id})


# ------------------------------------------------------------
# 2) Projects discover
# ------------------------------------------------------------
@bp.get("/sftp/projects")
def api_sftp_projects():
    session_id = (request.args.get("session_id") or "").strip()
    if not session_id:
        return jsonify({"ok": False, "error": "Missing session_id"}), 400

    try:
        s = _get_session(session_id)
        items = sftp_discover_projects(
            host=s["host"],
            port=s["port"],
            username=s["username"],
            password=s["password"],
        )
        return jsonify({"ok": True, "items": items})
    except Exception as e:
        current_app.logger.exception("Project discovery failed")
        return jsonify({"ok": False, "error": str(e)}), 400


# ------------------------------------------------------------
# 3) Explorer ls (safe)
# ------------------------------------------------------------
@bp.get("/sftp/ls")
def api_sftp_ls():
    session_id = (request.args.get("session_id") or "").strip()
    path = request.args.get("path") or "/"
    if not session_id:
        return jsonify({"ok": False, "error": "Missing session_id"}), 400

    try:
        s = _get_session(session_id)

        boundary = s.get("project_root")
        if not boundary:
            return jsonify(
                {
                    "ok": False,
                    "error": "No project selected (call /sftp/select_project first)",
                }
            ), 400

        items = sftp_ls_safe(
            host=s["host"],
            port=s["port"],
            username=s["username"],
            password=s["password"],
            path=path,
            boundary_root=boundary,
        )
        return jsonify({"ok": True, "items": items, "boundary_root": boundary})
    except Exception as e:
        current_app.logger.exception("SFTP ls failed")
        return jsonify({"ok": False, "error": str(e)}), 400


# ------------------------------------------------------------
# 4) Diagnose
# ------------------------------------------------------------
@bp.post("/diagnose")
def api_diagnose():
    data = request.get_json(silent=True) or {}
    session_id = (data.get("session_id") or "").strip()
    wp_root = (data.get("wp_root") or "").strip()

    if not session_id:
        return jsonify({"ok": False, "error": "Missing session_id"}), 400

    try:
        s = _get_session(session_id)

        if not wp_root:
            wp_root = (s.get("wp_root") or "").strip()
        if not wp_root:
            return jsonify(
                {
                    "ok": False,
                    "error": "Missing wp_root (call /sftp/find_wp_root or provide wp_root)",
                }
            ), 400

        s["wp_root"] = wp_root

        result = run_diagnose(
            host=s["host"],
            port=s["port"],
            username=s["username"],
            password=s["password"],
            wp_root=wp_root,
        )

        return jsonify({"ok": True, "diagnose": result})
    except Exception as e:
        current_app.logger.exception("Diagnose failed")
        return jsonify({"ok": False, "error": str(e)}), 400


# ------------------------------------------------------------
# Project / wp-root selection
# ------------------------------------------------------------
@bp.post("/sftp/select_project")
def api_sftp_select_project():
    data = request.get_json(silent=True) or {}
    session_id = (data.get("session_id") or "").strip()
    project_root = (data.get("project_root") or "").strip()

    if not session_id or not project_root:
        return jsonify({"ok": False, "error": "Missing session_id/project_root"}), 400

    try:
        s = _get_session(session_id)

        if not sftp_path_is_dir(
            host=s["host"],
            port=s["port"],
            username=s["username"],
            password=s["password"],
            path=project_root,
        ):
            return jsonify(
                {"ok": False, "error": "project_root does not exist or is not a directory"}
            ), 400

        s["project_root"] = project_root
        s["wp_root"] = None

        return jsonify({"ok": True, "project_root": project_root})
    except Exception as e:
        current_app.logger.exception("Select project failed")
        return jsonify({"ok": False, "error": str(e)}), 400


@bp.post("/sftp/find_wp_root")
def api_sftp_find_wp_root():
    """
    Body JSON:
    {
      "session_id": "...",
      "max_depth": 4
    }
    Uses selected project_root from session.
    Stores best candidate into session.wp_root.
    """
    data = request.get_json(silent=True) or {}
    session_id = (data.get("session_id") or "").strip()
    max_depth = int(data.get("max_depth") or 4)

    if not session_id:
        return jsonify({"ok": False, "error": "Missing session_id"}), 400

    try:
        s = _get_session(session_id)
        project_root = s.get("project_root")
        if not project_root:
            return jsonify(
                {"ok": False, "error": "No project selected (call /sftp/select_project first)"}
            ), 400

        candidates = find_wp_roots(
            host=s["host"],
            port=s["port"],
            username=s["username"],
            password=s["password"],
            project_root=project_root,
            max_depth=max_depth,
        )

        best = candidates[0]["wp_root"] if candidates else None
        s["wp_root"] = best

        return jsonify(
            {"ok": True, "project_root": project_root, "wp_root": best, "candidates": candidates}
        )
    except Exception as e:
        current_app.logger.exception("Find WP root failed")
        return jsonify({"ok": False, "error": str(e)}), 400


@bp.post("/sftp/select_wp_root")
def api_sftp_select_wp_root():
    data = request.get_json(silent=True) or {}
    session_id = (data.get("session_id") or "").strip()
    wp_root = (data.get("wp_root") or "").strip()

    if not session_id or not wp_root:
        return jsonify({"ok": False, "error": "Missing session_id/wp_root"}), 400

    try:
        s = _get_session(session_id)
        if not s.get("project_root"):
            return jsonify({"ok": False, "error": "No project selected"}), 400

        pr = s["project_root"].rstrip("/")
        if wp_root != pr and not wp_root.startswith(pr + "/"):
            return jsonify({"ok": False, "error": "wp_root outside selected project"}), 400

        s["wp_root"] = wp_root
        return jsonify({"ok": True, "wp_root": wp_root})
    except Exception as e:
        current_app.logger.exception("Select wp_root failed")
        return jsonify({"ok": False, "error": str(e)}), 400


# ------------------------------------------------------------
# Rollback (updates DB status too)
# ------------------------------------------------------------
@bp.post("/rollback")
def api_rollback():
    data = request.get_json(silent=True) or {}
    session_id = (data.get("session_id") or "").strip()
    action_id = (data.get("action_id") or "").strip()

    if not session_id or not action_id:
        return jsonify({"ok": False, "error": "Missing session_id/action_id"}), 400

    try:
        s = _get_session(session_id)
        wp_root = (s.get("wp_root") or "").strip()
        if not wp_root:
            return jsonify({"ok": False, "error": "No wp_root selected"}), 400

        # local meta.json (stored on Sitefixer server)
        ticket_id, _ = get_action_ctx(action_id)
        storage_root = (current_app.config.get("WP_REPAIR_STORAGE_ROOT") or "/var/www/sitefixer/wp-repair-storage").strip()
        meta_path = os.path.join(storage_root, "quarantine", str(int(ticket_id or 0)), str(action_id), "meta.json")

        meta = rollback(s["host"], s["port"], s["username"], s["password"], meta_path)

        append_log(
            s["host"],
            s["port"],
            s["username"],
            s["password"],
            wp_root,
            {
                "ts": int(time.time()),
                "type": "rollback",
                "action_id": action_id,
                "fix_id": meta.get("fix_id"),
                "ok": True,
            },
        )

        _db_status(action_id, "rolled_back", result={"fix_id": meta.get("fix_id")}, meta=meta)
        return jsonify({"ok": True, "meta": meta})
    except Exception as e:
        current_app.logger.exception("Rollback failed")
        _db_status(action_id, "rollback_failed", error={"error": str(e)})
        return jsonify({"ok": False, "error": str(e)}), 400


# ------------------------------------------------------------
# FIX: htaccess (DB status)
# ------------------------------------------------------------
@bp.post("/fix/htaccess")
def api_fix_htaccess():
    data = request.get_json(silent=True) or {}
    session_id = (data.get("session_id") or "").strip()
    template = (data.get("template") or "single.htaccess").strip()

    if not session_id:
        return jsonify({"ok": False, "error": "Missing session_id"}), 400

    action = None
    try:
        s = _get_session(session_id)
        wp_root = (s.get("wp_root") or "").strip()
        if not wp_root:
            return jsonify({"ok": False, "error": "No wp_root selected"}), 400

        action = create_action(
            s["host"],
            s["port"],
            s["username"],
            s["password"],
            wp_root=wp_root,
            fix_id="htaccess",
            context={"template": template},
            ticket_id=int(s.get("ticket_id") or 0),
            actor_user_id=int(s.get("actor_user_id") or 0),
            actor_name=s.get("actor_name"),
            project_root=s.get("project_root"),
        )

        # --- FIX: indentation/try-except correctness ---
        ht_path = f"{wp_root.rstrip('/')}/.htaccess"
        moved = False
        backup_path = None
        try:
            qm = quarantine_move(
                s["host"], s["port"], s["username"], s["password"],
                wp_root=wp_root,
                src_path=ht_path,
                action_id=action["action_id"],
                kind="FILE",
            )
            backup_path = qm.get("dst_path") if qm.get("ok") else None
            moved = bool(backup_path)
        except Exception:
            moved = False

        res = apply_htaccess_fix(
            host=s["host"],
            port=s["port"],
            username=s["username"],
            password=s["password"],
            wp_root=wp_root,
            template=template,
        )

        append_log(
            s["host"],
            s["port"],
            s["username"],
            s["password"],
            wp_root,
            {
                "ts": int(time.time()),
                "type": "fix",
                "fix_id": "htaccess",
                "action_id": action["action_id"],
                "ok": True,
                "details": {"template": template, "moved_old": moved},
            },
        )

        _db_status(action["action_id"], "applied", result=res)
        return jsonify({"ok": True, "action_id": action["action_id"], "result": res})
    except Exception as e:
        current_app.logger.exception("htaccess fix failed")
        if action:
            _db_status(action["action_id"], "failed", error={"error": str(e)})
        return jsonify({"ok": False, "error": str(e)}), 400


# ------------------------------------------------------------
# Permissions
# ------------------------------------------------------------
@bp.post("/permissions/preview")
def api_permissions_preview():
    data = request.get_json(silent=True) or {}
    session_id = (data.get("session_id") or "").strip()
    rules = data.get("rules") or {}

    if not session_id:
        return jsonify({"ok": False, "error": "Missing session_id"}), 400

    try:
        s = _get_session(session_id)
        _, wp_root = _ensure_context(s, data)
        if not wp_root:
            return jsonify({"ok": False, "error": "No wp_root selected"}), 400

        res = permissions_preview(
            host=s["host"],
            port=s["port"],
            username=s["username"],
            password=s["password"],
            wp_root=wp_root,
            rules=rules,
        )
        return jsonify(res)
    except Exception as e:
        current_app.logger.exception("permissions preview failed")
        return jsonify({"ok": False, "error": str(e)}), 400


@bp.post("/permissions/apply")
def api_permissions_apply():
    data = request.get_json(silent=True) or {}
    session_id = (data.get("session_id") or "").strip()

    # rules can be:
    # - dict of modes/max_items
    # - plus optional scope controls:
    #   include_core: bool
    #   start_paths: ["wp-admin", "wp-includes", "wp-content"]
    #   rel_paths:   ["wp-admin/about.php"]
    #   paths:       ["/abs/path/to/wp-admin/about.php"]
    rules = data.get("rules") or {}

    # allow shorthand parameters on root-level too (frontend convenience)
    include_core = data.get("include_core", None)
    start_paths = data.get("start_paths", None)
    rel_paths = data.get("rel_paths", None)
    paths = data.get("paths", None)

    if include_core is not None and isinstance(rules, dict) and "include_core" not in rules:
        rules["include_core"] = bool(include_core)
    if start_paths is not None and isinstance(rules, dict) and "start_paths" not in rules:
        rules["start_paths"] = start_paths
    if rel_paths is not None and isinstance(rules, dict) and "rel_paths" not in rules:
        rules["rel_paths"] = rel_paths
    if paths is not None and isinstance(rules, dict) and "paths" not in rules:
        rules["paths"] = paths

    # normalize list fields
    def _norm_list(v):
        if v is None:
            return []
        if isinstance(v, str):
            # allow comma/newline separated
            parts = [p.strip() for p in v.replace("\n", ",").split(",")]
            return [p for p in parts if p]
        if isinstance(v, list):
            out = []
            for x in v:
                if x is None:
                    continue
                s = str(x).strip()
                if s:
                    out.append(s)
            return out
        return []

    if isinstance(rules, dict):
        rules["start_paths"] = _norm_list(rules.get("start_paths"))
        rules["rel_paths"] = _norm_list(rules.get("rel_paths"))
        rules["paths"] = _norm_list(rules.get("paths"))
        if "include_core" in rules:
            rules["include_core"] = bool(rules.get("include_core"))

    if not session_id:
        return jsonify({"ok": False, "error": "Missing session_id"}), 400

    action = None
    try:
        s = _get_session(session_id)
        _, wp_root = _ensure_context(s, data)
        if not wp_root:
            return jsonify({"ok": False, "error": "No wp_root selected"}), 400

        # if frontend sends rel_paths, expand to abs paths for convenience
        # (only if you prefer to work with abs paths in permissions_apply)
        if isinstance(rules, dict) and rules.get("rel_paths"):
            expanded = []
            for rel in rules["rel_paths"]:
                # safe join (simple join; ensure your permissions_apply clamps properly)
                expanded.append(f"{wp_root.rstrip('/')}/{rel.lstrip('/')}")
            # keep both (permissions_apply can choose)
            rules["paths"] = list(dict.fromkeys((rules.get("paths") or []) + expanded))

        action = create_action(
            s["host"],
            s["port"],
            s["username"],
            s["password"],
            wp_root=wp_root,
            fix_id="permissions",
            context={"rules": rules},
            ticket_id=int(s.get("ticket_id") or 0),
            actor_user_id=int(s.get("actor_user_id") or 0),
            actor_name=s.get("actor_name"),
            project_root=s.get("project_root"),
        )

        res = permissions_apply(
            host=s["host"],
            port=s["port"],
            username=s["username"],
            password=s["password"],
            wp_root=wp_root,
            rules=rules,
        )

        meta_txt = read_text_remote(s["host"], s["port"], s["username"], s["password"], action["meta_path"])
        meta = json.loads(meta_txt)
        _meta_ensure(meta)

        # IMPORTANT: treat "applied"/"partial"/"skipped" as terminal statuses
        status = "partial" if res.get("errors") else "applied"
        if res.get("skipped"):
            status = "skipped"

        meta["status"] = status
        _meta_note(
            meta,
            f"chmod_changed={len(res.get('changed', []))} errors={len(res.get('errors', []))} skipped={bool(res.get('skipped'))}"
        )

        for ch in (res.get("changed") or []):
            p = ch.get("path")
            frm = ch.get("from") or ch.get("old_mode")
            to = ch.get("to") or ch.get("new_mode")
            if p:
                _meta_event(meta, f"chmod {p}: {frm} -> {to}")

        # if permissions_apply returns a "targets" list, store it (optional)
        if res.get("targets"):
            _meta_note(meta, f"targets={len(res.get('targets') or [])}")

        write_text_remote(
            s["host"],
            s["port"],
            s["username"],
            s["password"],
            action["meta_path"],
            json.dumps(meta, ensure_ascii=False, indent=2),
        )

        _db_status(action["action_id"], status, result=res)

        append_log(
            s["host"],
            s["port"],
            s["username"],
            s["password"],
            wp_root,
            {
                "ts": int(time.time()),
                "type": "fix",
                "fix_id": "permissions",
                "action_id": action["action_id"],
                "ok": True,
                "details": {
                    "changed": len(res.get("changed", [])),
                    "errors": len(res.get("errors", [])),
                    "skipped": bool(res.get("skipped")),
                },
            },
        )

        # return action_id + result (your UI polls action anyway)
        return jsonify({"ok": True, "action_id": action["action_id"], "result": res})
    except Exception as e:
        current_app.logger.exception("permissions apply failed")
        if action:
            _db_status(action["action_id"], "failed", error={"error": str(e)})
        return jsonify({"ok": False, "error": str(e)}), 400



# ------------------------------------------------------------
# Maintenance remove (DB status for skipped/applied)
# ------------------------------------------------------------
@bp.post("/fix/maintenance/remove")
def api_fix_maintenance_remove():
    data = request.get_json(silent=True) or {}
    session_id = (data.get("session_id") or "").strip()
    if not session_id:
        return jsonify({"ok": False, "error": "Missing session_id"}), 400

    action = None
    try:
        s = _get_session(session_id)
        _, wp_root = _ensure_context(s, data)
        if not wp_root:
            return jsonify({"ok": False, "error": "No wp_root selected"}), 400

        action = create_action(
            s["host"],
            s["port"],
            s["username"],
            s["password"],
            wp_root=wp_root,
            fix_id="maintenance",
            context={},
            ticket_id=int(s.get("ticket_id") or 0),
            actor_user_id=int(s.get("actor_user_id") or 0),
            actor_name=s.get("actor_name"),
            project_root=s.get("project_root"),
        )

        res = remove_maintenance(
            host=s["host"],
            port=s["port"],
            username=s["username"],
            password=s["password"],
            wp_root=wp_root,
        )

        meta_txt = read_text_remote(s["host"], s["port"], s["username"], s["password"], action["meta_path"])
        meta = json.loads(meta_txt)

        if res.get("skipped"):
            _meta_ensure(meta)
            meta["status"] = "skipped"
            _meta_note(meta, "skipped")

            write_text_remote(
                s["host"],
                s["port"],
                s["username"],
                s["password"],
                action["meta_path"],
                json.dumps(meta, ensure_ascii=False, indent=2),
            )

            _db_status(action["action_id"], "skipped", result=res, meta=meta)

            append_log(
                s["host"],
                s["port"],
                s["username"],
                s["password"],
                wp_root,
                {
                    "ts": int(time.time()),
                    "type": "fix",
                    "fix_id": "maintenance",
                    "action_id": action["action_id"],
                    "ok": True,
                    "skipped": True,
                },
            )
            return jsonify(
                {"ok": True, "action_id": action["action_id"], "result": res, "skipped": True}
            )

        qm = quarantine_move(
            s["host"], s["port"], s["username"], s["password"],
            wp_root=wp_root,
            src_path=res["path"],
            action_id=action["action_id"],
            kind="FILE",
        )
        moved_to = qm.get("dst_path") if qm.get("ok") else None

        meta_txt = read_text_remote(s["host"], s["port"], s["username"], s["password"], action["meta_path"])
        meta = json.loads(meta_txt)
        _meta_ensure(meta)
        meta["status"] = "applied"
        _meta_note(meta, f"moved=1")
        _meta_event(meta, f"moved {res['path']} -> {moved_to}")

        write_text_remote(
            s["host"],
            s["port"],
            s["username"],
            s["password"],
            action["meta_path"],
            json.dumps(meta, ensure_ascii=False, indent=2),
        )

        _db_status(
            action["action_id"],
            "applied",
            result={"path": res["path"], "moved_to": moved_to},
            meta=meta,
        )

        append_log(
            s["host"],
            s["port"],
            s["username"],
            s["password"],
            wp_root,
            {
                "ts": int(time.time()),
                "type": "fix",
                "fix_id": "maintenance",
                "action_id": action["action_id"],
                "ok": True,
                "skipped": False,
            },
        )

        return jsonify(
            {
                "ok": True,
                "action_id": action["action_id"],
                "result": {"ok": True, "path": res["path"], "moved_to": moved_to},
            }
        )

    except Exception as e:
        current_app.logger.exception("maintenance remove failed")
        if action:
            _db_status(action["action_id"], "failed", error={"error": str(e)})
        return jsonify({"ok": False, "error": str(e)}), 400


# ------------------------------------------------------------
# Dropins
# ------------------------------------------------------------
@bp.post("/fix/dropins/preview")
def api_fix_dropins_preview():
    data = request.get_json(silent=True) or {}
    session_id = (data.get("session_id") or "").strip()
    if not session_id:
        return jsonify({"ok": False, "error": "Missing session_id"}), 400

    try:
        s = _get_session(session_id)
        _, wp_root = _ensure_context(s, data)
        if not wp_root:
            return jsonify({"ok": False, "error": "No wp_root selected"}), 400

        res = dropins_preview(
            host=s["host"],
            port=s["port"],
            username=s["username"],
            password=s["password"],
            wp_root=wp_root,
        )
        return jsonify(res)
    except Exception as e:
        current_app.logger.exception("dropins preview failed")
        return jsonify({"ok": False, "error": str(e)}), 400


@bp.post("/fix/dropins/apply")
def api_fix_dropins_apply():
    data = request.get_json(silent=True) or {}
    session_id = (data.get("session_id") or "").strip()
    if not session_id:
        return jsonify({"ok": False, "error": "Missing session_id"}), 400

    action = None
    try:
        s = _get_session(session_id)
        _, wp_root = _ensure_context(s, data)
        if not wp_root:
            return jsonify({"ok": False, "error": "No wp_root selected"}), 400

        disable = data.get("disable")
        plan = dropins_apply_disable(
            host=s["host"],
            port=s["port"],
            username=s["username"],
            password=s["password"],
            wp_root=wp_root,
            disable=disable,
        )

        action = create_action(
            s["host"],
            s["port"],
            s["username"],
            s["password"],
            wp_root=wp_root,
            fix_id="dropins",
            context={"mode": "disable", "disable": plan.get("requested", [])},
            ticket_id=int(s.get("ticket_id") or 0),
            actor_user_id=int(s.get("actor_user_id") or 0),
            actor_name=s.get("actor_name"),
            project_root=s.get("project_root"),
        )

        # always define moved so skipped path can't crash
        moved = []

        if not plan.get("found"):
            moved = []  # <— wichtig
            meta = json.loads(
                read_text_remote(s["host"], s["port"], s["username"], s["password"], action["meta_path"])
            )
            _meta_ensure(meta)
            meta["status"] = "skipped"
            _meta_note(meta, "no_dropins_found")
            _meta_event(meta, "No dropins found to disable")
            meta.setdefault("result", {})
            meta["result"] = {"plan": plan, "moved": moved}

            write_text_remote(
                s["host"],
                s["port"],
                s["username"],
                s["password"],
                action["meta_path"],
                json.dumps(meta, ensure_ascii=False, indent=2),
            )

            _db_status(action["action_id"], "skipped", result={"plan": plan, "moved": []}, meta=meta)

            append_log(
                s["host"],
                s["port"],
                s["username"],
                s["password"],
                wp_root,
                {
                    "ts": int(time.time()),
                    "type": "fix",
                    "fix_id": "dropins",
                    "action_id": action["action_id"],
                    "ok": True,
                    "skipped": True,
                },
            )
            return jsonify({"ok": True, "action_id": action["action_id"], "result": plan, "skipped": True})

        # applied path: move found dropins into quarantine
        for t in plan["found"]:
            qm = quarantine_move(
                s["host"], s["port"], s["username"], s["password"],
                wp_root=wp_root,
                src_path=t["path"],
                action_id=action["action_id"],
                kind="FILE",
            )
            moved_to = qm.get("dst_path") if qm.get("ok") else None

            moved.append({"name": t["name"], "src": t["path"], "dst": moved_to})

        meta = json.loads(
            read_text_remote(s["host"], s["port"], s["username"], s["password"], action["meta_path"])
        )
        _meta_ensure(meta)
        meta["status"] = "applied"
        _meta_note(meta, f"disabled={len(moved)}")
        _meta_event(meta, f"disabled {len(moved)} dropin(s)")
        meta.setdefault("result", {})["plan"] = plan
        meta["result"]["moved"] = moved

        write_text_remote(
            s["host"],
            s["port"],
            s["username"],
            s["password"],
            action["meta_path"],
            json.dumps(meta, ensure_ascii=False, indent=2),
        )

        _db_status(action["action_id"], "applied", result={"plan": plan, "moved": moved}, meta=meta)

        append_log(
            s["host"],
            s["port"],
            s["username"],
            s["password"],
            wp_root,
            {
                "ts": int(time.time()),
                "type": "fix",
                "fix_id": "dropins",
                "action_id": action["action_id"],
                "ok": True,
                "skipped": False,
            },
        )

        return jsonify({"ok": True, "action_id": action["action_id"], "result": {"plan": plan, "moved": moved}})

    except Exception as e:
        current_app.logger.exception("dropins apply failed")
        if action:
            _db_status(action["action_id"], "failed", error={"error": str(e)})
        return jsonify({"ok": False, "error": str(e)}), 400


# ------------------------------------------------------------
# Core integrity preview
# ------------------------------------------------------------
@bp.post("/core/preview")
def api_core_preview():
    """
    Body JSON:
    {
      "session_id": "...",
      "wp_root": "...",          # optional, wenn bereits in Session
      "wp_version": "6.8",       # optional (wenn weggelassen, wird version.php gelesen)
      "max_files": 2500,         # optional
      "include_ok": false        # optional
    }
    """
    data = request.get_json(silent=True) or {}
    session_id = (data.get("session_id") or "").strip()
    if not session_id:
        return jsonify({"ok": False, "error": "Missing session_id"}), 400

    try:
        s = _get_session(session_id)
        _, wp_root = _ensure_context(s, data)
        if not wp_root:
            return jsonify({"ok": False, "error": "No wp_root selected"}), 400

        wp_version = (data.get("wp_version") or "").strip() or None
        max_files = int(data.get("max_files") or 2500)
        include_ok = bool(data.get("include_ok") or False)

        res = core_integrity_preview(
            host=s["host"],
            port=s["port"],
            username=s["username"],
            password=s["password"],
            wp_root=wp_root,
            wp_version=wp_version,
            max_files=max_files,
            include_ok=include_ok,
        )
        return jsonify(res)
    except Exception as e:
        current_app.logger.exception("core preview failed")
        return jsonify({"ok": False, "error": str(e)}), 400


# ------------------------------------------------------------
# Core replace preview/apply (DB status on apply)
# ------------------------------------------------------------
@bp.post("/core/replace/preview")
def api_core_replace_preview():
    data = request.get_json(silent=True) or {}
    session_id = (data.get("session_id") or "").strip()
    if not session_id:
        return jsonify({"ok": False, "error": "Missing session_id"}), 400

    try:
        s = _get_session(session_id)
        _, wp_root = _ensure_context(s, data)
        if not wp_root:
            return jsonify({"ok": False, "error": "No wp_root selected"}), 400

        max_files = int(data.get("max_files") or 5000)
        max_replace = data.get("max_replace", None)
        if max_replace is not None:
            max_replace = int(max_replace)

        allow_changed = bool(data.get("allow_changed", True))
        allow_missing = bool(data.get("allow_missing", False))
        policy = data.get("policy")

        preview = core_replace_preview_fn(
            s["host"],
            s["port"],
            s["username"],
            s["password"],
            wp_root,
            max_files=max_files,
            max_replace=max_replace,
            allow_changed=allow_changed,
            allow_missing=allow_missing,
            policy=policy,
        )
        return jsonify(preview)
    except Exception as e:
        current_app.logger.exception("core replace preview failed")
        return jsonify({"ok": False, "error": str(e)}), 400


@bp.post("/core/replace/apply")
def api_core_replace_apply():
    data = request.get_json(silent=True) or {}
    session_id = (data.get("session_id") or "").strip()
    if not session_id:
        return jsonify({"ok": False, "error": "Missing session_id"}), 400

    action = None
    try:
        s = _get_session(session_id)
        _, wp_root = _ensure_context(s, data)
        if not wp_root:
            return jsonify({"ok": False, "error": "No wp_root selected"}), 400

        max_files = int(data.get("max_files") or 5000)
        max_replace = int(data.get("max_replace") or 500)
        allow_changed = bool(data.get("allow_changed", True))
        allow_missing = bool(data.get("allow_missing", False))
        policy = data.get("policy")

        action = create_action(
            s["host"],
            s["port"],
            s["username"],
            s["password"],
            wp_root=wp_root,
            fix_id="core_replace",
            context={
                "max_files": max_files,
                "max_replace": max_replace,
                "allow_changed": allow_changed,
                "allow_missing": allow_missing,
                "policy": policy,
            },
            ticket_id=int(s.get("ticket_id") or 0),
            actor_user_id=int(s.get("actor_user_id") or 0),
            actor_name=s.get("actor_name"),
            project_root=s.get("project_root"),
        )

        result = core_replace_apply_fn(
            s["host"],
            s["port"],
            s["username"],
            s["password"],
            wp_root=wp_root,
            action_meta_path=action["meta_path"],
            action_moved_dir=action["moved_dir"],
            max_files=max_files,
            max_replace=max_replace,
            allow_changed=allow_changed,
            allow_missing=allow_missing,
            policy=policy,
        )

        # ---- final status decision ----
        errors = result.get("errors") or []
        replaced = result.get("replaced") or []
        ok_flag = bool(result.get("ok"))
        if ok_flag and errors:
            final_status = "partial"
        else:
            final_status = "applied" if ok_flag else "failed"

        # ---- update remote meta.json (FIX: keep meta format consistent with _meta_ensure) ----
        meta = json.loads(
            read_text_remote(s["host"], s["port"], s["username"], s["password"], action["meta_path"])
        )
        _meta_ensure(meta)

        meta["status"] = final_status
        _meta_note(meta, f"core_replace_apply replaced={len(replaced)} errors={len(errors)}")
        _meta_event(meta, f"core_replace_apply status={final_status} replaced={len(replaced)} errors={len(errors)}")

        meta.setdefault("result", {})
        meta["result"]["replaced"] = replaced
        meta["result"]["errors"] = errors

        write_text_remote(
            s["host"],
            s["port"],
            s["username"],
            s["password"],
            action["meta_path"],
            json.dumps(meta, ensure_ascii=False, indent=2),
        )

        # ---- DB status (single write) ----
        _db_status(
            action["action_id"],
            final_status,
            result=result if final_status in ("applied", "partial") else None,
            error=None if final_status in ("applied", "partial") else result,
            meta=meta,
        )

        # ---- append log (optional) ----
        append_log(
            s["host"],
            s["port"],
            s["username"],
            s["password"],
            wp_root,
            {
                "ts": int(time.time()),
                "type": "fix",
                "fix_id": "core_replace",
                "action_id": action["action_id"],
                "ok": final_status in ("applied", "partial"),
                "replaced": len(replaced),
                "errors": len(errors),
                "status": final_status,
            },
        )

        return jsonify({"ok": True, "action_id": action["action_id"], "result": result})

    except Exception as e:
        current_app.logger.exception("core replace apply failed")
        if action:
            _db_status(action["action_id"], "failed", error={"error": str(e)})
        return jsonify({"ok": False, "error": str(e)}), 400


# ------------------------------------------------------------
# Plugins preview / disable (DB status for skipped/applied/partial)
# ------------------------------------------------------------
@bp.post("/fix/plugins/preview")
def api_fix_plugins_preview():
    data = request.get_json(silent=True) or {}
    session_id = (data.get("session_id") or "").strip()
    include_ok = bool(data.get("include_ok", True))
    max_plugins = int(data.get("max_plugins") or 500)

    if not session_id:
        return jsonify({"ok": False, "error": "Missing session_id"}), 400

    try:
        s = _get_session(session_id)
        _, wp_root = _ensure_context(s, data)
        if not wp_root:
            return jsonify({"ok": False, "error": "No wp_root selected"}), 400

        res = plugins_preview(
            s["host"],
            s["port"],
            s["username"],
            s["password"],
            wp_root,
            max_plugins=max_plugins,
            include_ok=include_ok,
        )
        return jsonify(res)
    except Exception as e:
        current_app.logger.exception("plugins preview failed")
        return jsonify({"ok": False, "error": str(e)}), 400


@bp.post("/fix/plugins/disable")
@jwt_required()
def api_fix_plugins_disable():
    """
    Disable WP plugins by renaming their plugin directory:
      wp-content/plugins/<slug>  ->  wp-content/plugins/<slug>.disabled

    - Logs each successful rename in DB via add_file_op(op="renamed", ...)
      (DB errors ignored)
    - Updates remote meta.json: meta["moved"] += [{"src","dst"}]
    - Status: applied / partial / failed
    - Skips: dst exists OR src missing
    - Errors: rename/stat exceptions
    """
    data = request.get_json(silent=True) or {}

    session_id = (data.get("session_id") or "").strip()
    if not session_id:
        return jsonify({"ok": False, "error": "Missing session_id"}), 400

    # inputs
    slugs = data.get("slugs") or []
    reason = (data.get("reason") or "manual_disable").strip()

    if isinstance(slugs, str):
        slugs = [slugs]
    slugs = [s.strip().strip("/") for s in slugs if isinstance(s, str) and s.strip()]

    if not slugs:
        return jsonify({"ok": False, "error": "No plugin slugs provided (slugs[])"}), 400

    action = None
    client = None
    sftp = None

    try:
        s = _get_session(session_id)
        _, wp_root = _ensure_context(s, data)
        if not wp_root:
            return jsonify({"ok": False, "error": "No wp_root selected"}), 400

        action = create_action(
            s["host"],
            s["port"],
            s["username"],
            s["password"],
            wp_root=wp_root,
            fix_id="plugins_disable",
            context={"reason": reason, "slugs": slugs},
            ticket_id=int(s.get("ticket_id") or 0),
            actor_user_id=int(s.get("actor_user_id") or 0),
            actor_name=s.get("actor_name"),
            project_root=s.get("project_root"),
        )

        client = sftp_connect(s["host"], s["port"], s["username"], s["password"])
        sftp = client.open_sftp()

        meta = json.loads(
            read_text_remote(s["host"], s["port"], s["username"], s["password"], action["meta_path"])
        )
        _meta_ensure(meta)
        meta.setdefault("moved", [])
        meta.setdefault("result", {})
        meta["status"] = "running"

        disabled = []
        skipped = []
        errors = []

        plugins_dir = posixpath.join(wp_root, "wp-content", "plugins")

        for slug in slugs:
            src = posixpath.join(plugins_dir, slug)
            dst = src + ".disabled"

            # collision: dst exists => skip
            try:
                sftp.stat(dst)
                skipped.append({"slug": slug, "src": src, "dst": dst, "reason": "dst_exists"})
                continue
            except FileNotFoundError:
                pass
            except Exception as e:
                errors.append({"slug": slug, "src": src, "dst": dst, "error": f"stat(dst) failed: {e}"})
                continue

            # missing: src not exists => skip
            try:
                sftp.stat(src)
            except FileNotFoundError:
                skipped.append({"slug": slug, "src": src, "dst": dst, "reason": "src_missing"})
                continue
            except Exception as e:
                errors.append({"slug": slug, "src": src, "dst": dst, "error": f"stat(src) failed: {e}"})
                continue

            # rename => disable
            try:
                sftp.rename(src, dst)
                disabled.append({"slug": slug, "src": src, "dst": dst})
                meta["moved"].append({"src": src, "dst": dst})

                try:
                    add_file_op(
                        action["action_id"],
                        op="renamed",
                        src_path=src,
                        dst_path=dst,
                        payload_json={"slug": slug, "reason": reason},
                    )
                except Exception:
                    pass

            except Exception as e:
                errors.append({"slug": slug, "src": src, "dst": dst, "error": str(e)})

        # status logic (consistent)
        if len(disabled) > 0 and len(errors) == 0:
            final_status = "applied"
        elif len(disabled) > 0 and len(errors) > 0:
            final_status = "partial"
        elif len(disabled) == 0 and len(errors) > 0:
            final_status = "failed"
        else:
            final_status = "skipped"

        meta["status"] = final_status
        _meta_note(meta, f"disabled={len(disabled)} skipped={len(skipped)} errors={len(errors)}")
        _meta_event(meta, f"plugins_disable status={final_status} disabled={len(disabled)} skipped={len(skipped)} errors={len(errors)}")
        meta["result"] = {
            "disabled": disabled,
            "skipped": skipped,
            "errors": errors,
            "counts": {"disabled": len(disabled), "skipped": len(skipped), "errors": len(errors)},
        }

        write_text_remote(
            s["host"],
            s["port"],
            s["username"],
            s["password"],
            action["meta_path"],
            json.dumps(meta, ensure_ascii=False, indent=2),
        )

        _db_status(
            action["action_id"],
            final_status,
            result=meta["result"] if final_status in ("applied", "partial", "skipped") else None,
            error=None if final_status in ("applied", "partial", "skipped") else {"errors": errors},
            meta=meta,
        )

        append_log(
            s["host"],
            s["port"],
            s["username"],
            s["password"],
            wp_root,
            {
                "ts": int(time.time()),
                "type": "fix",
                "fix_id": "plugins_disable",
                "action_id": action["action_id"],
                "ok": final_status in ("applied", "partial"),
                "status": final_status,
                "disabled": len(disabled),
                "skipped": len(skipped),
                "errors": len(errors),
            },
        )

        return jsonify(
            {
                "ok": True,
                "action_id": action["action_id"],
                "status": final_status,
                "result": meta["result"],
            }
        )

    except Exception as e:
        current_app.logger.exception("plugins disable failed")
        if action:
            _db_status(action["action_id"], "failed", error={"error": str(e)})
        return jsonify({"ok": False, "error": str(e)}), 400

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


# ------------------------------------------------------------
# Plugins recover (no DB action created here)
# ------------------------------------------------------------
@bp.post("/fix/plugins/recover/preview")
def api_plugins_recover_preview():
    data = request.get_json(silent=True) or {}
    session_id = (data.get("session_id") or "").strip()
    if not session_id:
        return jsonify({"ok": False, "error": "Missing session_id"}), 400

    batch_size = int(data.get("batch_size") or 2)
    max_disable_total = int(data.get("max_disable_total") or 10)
    exclude = data.get("exclude") or []
    mode = (data.get("mode") or "risky_only").strip()

    try:
        s = _get_session(session_id)
        _, wp_root = _ensure_context(s, data)
        if not wp_root:
            return jsonify({"ok": False, "error": "No wp_root selected"}), 400

        domain = (s.get("domain") or s.get("site_url") or data.get("domain") or "").strip()
        if not domain:
            return jsonify({"ok": False, "error": "Missing domain (site_url)"}), 400

        res = recover_preview(
            host=s["host"],
            port=s["port"],
            username=s["username"],
            password=s["password"],
            wp_root=wp_root,
            domain=domain,
            batch_size=batch_size,
            max_disable_total=max_disable_total,
            exclude=exclude,
            mode=mode,
        )
        return jsonify(res)
    except Exception as e:
        current_app.logger.exception("plugins recover preview failed")
        return jsonify({"ok": False, "error": str(e)}), 400


@bp.post("/fix/plugins/recover/apply")
def api_plugins_recover_apply():
    data = request.get_json(silent=True) or {}
    session_id = (data.get("session_id") or "").strip()
    if not session_id:
        return jsonify({"ok": False, "error": "Missing session_id"}), 400

    batch_size = int(data.get("batch_size") or 2)
    max_disable_total = int(data.get("max_disable_total") or 10)
    verify_timeout = int(data.get("verify_timeout") or 10)
    exclude = data.get("exclude") or []
    mode = (data.get("mode") or "risky_only").strip()
    force = bool(data.get("force", False))

    try:
        s = _get_session(session_id)
        _, wp_root = _ensure_context(s, data)
        if not wp_root:
            return jsonify({"ok": False, "error": "No wp_root selected"}), 400

        domain = (s.get("domain") or s.get("site_url") or data.get("domain") or "").strip()
        if not domain:
            return jsonify({"ok": False, "error": "Missing domain (site_url)"}), 400

        res = recover_apply(
            host=s["host"],
            port=s["port"],
            username=s["username"],
            password=s["password"],
            wp_root=wp_root,
            domain=domain,
            batch_size=batch_size,
            max_disable_total=max_disable_total,
            verify_timeout=verify_timeout,
            exclude=exclude,
            mode=mode,
            force=force,
        )
        return jsonify(res)
    except Exception as e:
        current_app.logger.exception("plugins recover apply failed")
        return jsonify({"ok": False, "error": str(e)}), 400


@bp.post("/fix/malware/scan")
@jwt_required()
def api_fix_malware_scan():
    """
    Body JSON:
    {
      "session_id": "...",
      "wp_root": "...",        # optional if session has it
      "start_path": "...",     # optional (default wp_root)
      "max_files": 4000,       # optional
      "max_bytes": 2000000,    # optional
      "yara_enabled": true,    # optional
      "connect_timeout": 15,   # optional
      "op_timeout": 20         # optional
    }

    Enqueue WP-Repair malware scan into queue "wp_repair".
    IMPORTANT: store worker context in Redis because worker can't access Flask RAM session.
    """
    data = request.get_json(silent=True) or {}
    session_id = (data.get("session_id") or "").strip()
    if not session_id:
        return jsonify({"ok": False, "error": "Missing session_id"}), 400

    action = None
    try:
        s = _get_session(session_id)
        _, wp_root = _ensure_context(s, data)
        if not wp_root:
            return jsonify({"ok": False, "error": "No wp_root selected"}), 400

        start_path = (data.get("start_path") or "").strip() or None
        max_files = int(data.get("max_files") or 4000)
        max_bytes = int(data.get("max_bytes") or 2_000_000)

        yara_enabled = bool(data.get("yara_enabled", True))
        connect_timeout = int(data.get("connect_timeout") or 15)
        op_timeout = int(data.get("op_timeout") or 20)

        action = create_action(
            s["host"],
            s["port"],
            s["username"],
            s["password"],
            wp_root=wp_root,
            fix_id="malware_scan",
            context={
                "start_path": start_path,
                "max_files": max_files,
                "max_bytes": max_bytes,
                "yara_enabled": yara_enabled,
                "connect_timeout": connect_timeout,
                "op_timeout": op_timeout,
            },
            ticket_id=int(s.get("ticket_id") or 0),
            actor_user_id=int(s.get("actor_user_id") or 0),
            actor_name=s.get("actor_name"),
            project_root=s.get("project_root"),
        )

        import os, json as _json
        from redis import Redis

        redis_url = os.getenv("REDIS_URL") or "redis://127.0.0.1:6379/0"
        r = Redis.from_url(redis_url)

        ctx_key = f"wp_repair:ctx:{action['action_id']}"
        ctx = {
            "action_id": action["action_id"],
            "ticket_id": int(s.get("ticket_id") or 0),
            "actor_user_id": int(s.get("actor_user_id") or 0),
            "actor_name": s.get("actor_name"),

            "host": s["host"],
            "port": int(s["port"]),
            "username": s["username"],
            "password": s["password"],

            "project_root": s.get("project_root"),
            "wp_root": wp_root,

            "start_path": start_path,
            "max_files": max_files,
            "max_bytes": max_bytes,
            "yara_enabled": yara_enabled,
            "connect_timeout": connect_timeout,
            "op_timeout": op_timeout,
        }
        r.setex(ctx_key, 60 * 60 * 2, _json.dumps(ctx))

        _db_status(
            action["action_id"],
            "queued",
            result=None,
            error=None,
            meta={"fix_id": "malware_scan", "queued": True, "queue": "wp_repair"},
        )

        from rq import Queue
        q = Queue("wp_repair", connection=r)

        job = q.enqueue(
            "app.modules.wp_repair.workers.malware_scan_worker.perform_wp_repair_malware_scan",
            action["action_id"],
            job_timeout=60 * 60 * 2,
        )

        _db_status(
            action["action_id"],
            "queued",
            result=None,
            error=None,
            meta={
                "fix_id": "malware_scan",
                "queued": True,
                "job_id": job.id,
                "queue": "wp_repair",
                "ctx_key": ctx_key,
            },
        )

        return jsonify({"ok": True, "action_id": action["action_id"], "job_id": job.id, "status": "queued"})

    except Exception as e:
        current_app.logger.exception("malware scan enqueue failed")
        if action:
            _db_status(action["action_id"], "failed", error={"error": str(e)})
        return jsonify({"ok": False, "error": str(e)}), 400


@bp.post("/fix/plugins/restore")
@jwt_required()
def api_fix_plugins_restore():
    data = request.get_json(silent=True) or {}
    session_id = (data.get("session_id") or "").strip()
    if not session_id:
        return jsonify({"ok": False, "error": "Missing session_id"}), 400

    slugs = data.get("slugs") or []
    if isinstance(slugs, str):
        slugs = [slugs]
    slugs = [s.strip().strip("/") for s in slugs if isinstance(s, str) and s.strip()]
    if not slugs:
        return jsonify({"ok": False, "error": "No plugin slugs provided (slugs[])"}), 400

    reason = (data.get("reason") or "restore_plugin").strip()
    connect_timeout = int(data.get("connect_timeout") or 15)
    op_timeout = int(data.get("op_timeout") or 20)

    action = None
    try:
        s = _get_session(session_id)
        _, wp_root = _ensure_context(s, data)
        if not wp_root:
            return jsonify({"ok": False, "error": "No wp_root selected"}), 400

        action = create_action(
            s["host"], s["port"], s["username"], s["password"],
            wp_root=wp_root,
            fix_id="plugins_restore",
            context={"reason": reason, "slugs": slugs, "connect_timeout": connect_timeout, "op_timeout": op_timeout},
            ticket_id=int(s.get("ticket_id") or 0),
            actor_user_id=int(s.get("actor_user_id") or 0),
            actor_name=s.get("actor_name"),
            project_root=s.get("project_root"),
        )

        result = plugins_restore_apply(
            s["host"], int(s["port"]), s["username"], s["password"],
            wp_root=wp_root,
            slugs=slugs,
            connect_timeout=connect_timeout,
            op_timeout=op_timeout,
        )

        counts = result.get("counts") or {}
        restored = int(counts.get("restored") or 0)
        errors = int(counts.get("errors") or 0)
        skipped = int(counts.get("skipped") or 0)

        for item in (result.get("restored") or []):
            try:
                add_file_op(
                    action["action_id"],
                    op="renamed",
                    src_path=item.get("src"),
                    dst_path=item.get("dst"),
                    payload_json={"slug": item.get("slug"), "reason": reason, "module": "plugins_restore"},
                )
            except Exception:
                pass

        if errors > 0 and restored > 0:
            final_status = "partial"
        elif errors > 0 and restored == 0:
            final_status = "failed"
        elif restored == 0 and skipped > 0:
            final_status = "skipped"
        else:
            final_status = "applied"

        _db_status(action["action_id"], final_status, result=result, meta={"fix_id": "plugins_restore", "counts": counts})

        return jsonify({"ok": True, "action_id": action["action_id"], "status": final_status, "result": result})

    except Exception as e:
        current_app.logger.exception("plugins restore failed")
        if action:
            _db_status(action["action_id"], "failed", error={"error": str(e)})
        return jsonify({"ok": False, "error": str(e)}), 400


# ------------------------------------------------------------
# Read file (safe, boundary clamp)
# ------------------------------------------------------------
@bp.get("/sftp/read")
def api_sftp_read():
    """
    Query:
      session_id=...
      path=/abs/remote/path
      max_bytes=4096 (optional)
    Returns JSON:
      { ok: true, path: "...", max_bytes: N, content: "..." }
    """
    session_id = (request.args.get("session_id") or "").strip()
    path = request.args.get("path") or ""
    max_bytes = int(request.args.get("max_bytes") or 4096)

    if not session_id:
        return jsonify({"ok": False, "error": "Missing session_id"}), 400
    if not path:
        return jsonify({"ok": False, "error": "Missing path"}), 400

    try:
        s = _get_session(session_id)
        boundary_root = (s.get("project_root") or s.get("wp_root") or "").rstrip("/")
        if not boundary_root:
            return jsonify({"ok": False, "error": "No boundary_root in session"}), 400

        norm = posixpath.normpath(path)
        br = boundary_root
        if not (norm == br or norm.startswith(br + "/")):
            return jsonify({"ok": False, "error": "path_outside_boundary", "boundary_root": br}), 400

        max_bytes = max(1, min(max_bytes, 200_000))

        client = sftp_connect(s["host"], s["port"], s["username"], s["password"])
        sftp = client.open_sftp()
        try:
            with sftp.open(norm, "r") as f:
                data_bytes = f.read(max_bytes)
        finally:
            try:
                sftp.close()
            except Exception:
                pass
            try:
                client.close()
            except Exception:
                pass

        if isinstance(data_bytes, bytes):
            content = data_bytes.decode("utf-8", errors="replace")
        else:
            content = str(data_bytes)

        return jsonify({"ok": True, "path": norm, "max_bytes": max_bytes, "content": content})
    except Exception as e:
        current_app.logger.exception("sftp read failed")
        return jsonify({"ok": False, "error": str(e)}), 400


@bp.post("/sftp/write")
def api_sftp_write():
    """
    Body JSON:
      { "session_id": "...", "path": "/abs/remote/path", "content": "..." , "mode": "0644" (optional) }
    """
    data = request.get_json(silent=True) or {}
    session_id = (data.get("session_id") or "").strip()
    path = (data.get("path") or "").strip()
    content = data.get("content")

    if not session_id or not path:
        return jsonify({"ok": False, "error": "Missing session_id/path"}), 400
    if content is None:
        return jsonify({"ok": False, "error": "Missing content"}), 400

    s = _get_session(session_id)
    boundary_root = (s.get("project_root") or s.get("wp_root") or "").rstrip("/")
    if not boundary_root:
        return jsonify({"ok": False, "error": "No boundary_root in session"}), 400

    norm = posixpath.normpath(path)
    br = boundary_root
    if not (norm == br or norm.startswith(br + "/")):
        return jsonify({"ok": False, "error": "path_outside_boundary", "boundary_root": br}), 400

    if isinstance(content, str) and len(content.encode("utf-8")) > 200_000:
        return jsonify({"ok": False, "error": "content_too_large"}), 400

    mode_raw = data.get("mode")
    mode_int = None
    if mode_raw is not None:
        try:
            if isinstance(mode_raw, int):
                mode_int = mode_raw
            else:
                mode_int = int(str(mode_raw), 8)
        except Exception:
            return jsonify({"ok": False, "error": "invalid_mode"}), 400

    try:
        client = sftp_connect(s["host"], s["port"], s["username"], s["password"])
        sftp = client.open_sftp()
        try:
            parent = posixpath.dirname(norm)
            try:
                sftp.stat(parent)
            except Exception:
                return jsonify({"ok": False, "error": "parent_missing", "parent": parent}), 400

            data_bytes = content.encode("utf-8") if isinstance(content, str) else str(content).encode("utf-8")
            with sftp.open(norm, "wb") as f:
                f.write(data_bytes)

            if mode_int is not None:
                try:
                    sftp.chmod(norm, mode_int)
                except Exception:
                    pass

        finally:
            try:
                sftp.close()
            except Exception:
                pass
            try:
                client.close()
            except Exception:
                pass

        return jsonify({"ok": True, "path": norm, "bytes": len(data_bytes)})
    except Exception as e:
        current_app.logger.exception("sftp write failed")
        return jsonify({"ok": False, "error": str(e)}), 400


@bp.get("/actions/<action_id>")
@jwt_required()
def api_action_get(action_id: str):
    from app.models_wp_repair_audit import RepairAction

    row = RepairAction.query.filter_by(action_id=action_id).first()
    if not row:
        return jsonify({"ok": False, "error": "not_found"}), 404

    return jsonify({
        "ok": True,
        "action": {
            "action_id": row.action_id,
            "ticket_id": row.ticket_id,
            "fix_id": row.fix_id,
            "status": row.status,
            "created_at_utc": row.created_at_utc.isoformat() if row.created_at_utc else None,
            "updated_at_utc": row.updated_at_utc.isoformat() if row.updated_at_utc else None,
            "result": row.result_json,
            "error": row.error_json,
            "meta": row.meta_json,
        }
    })


@bp.get("/actions/<action_id>/findings")
@jwt_required()
def api_action_findings(action_id: str):
    from app.models_wp_repair_audit import RepairFinding

    limit = int(request.args.get("limit") or 200)
    offset = int(request.args.get("offset") or 0)
    limit = max(1, min(limit, 500))
    offset = max(0, offset)

    rows = (RepairFinding.query
            .filter_by(action_id=action_id)
            .order_by(RepairFinding.ts_utc.asc())
            .offset(offset).limit(limit).all())

    items = []
    for r in rows:
        items.append({
            "ts_utc": r.ts_utc.isoformat() if r.ts_utc else None,
            "path": r.path,
            "severity": r.severity,
            "kind": r.kind,
            "detail": r.detail_json,
        })

    return jsonify({
        "ok": True,
        "action_id": action_id,
        "offset": offset,
        "limit": limit,
        "count": len(items),
        "items": items,
    })


@bp.post("/fix/themes/preview")
def api_fix_themes_preview():
    data = request.get_json(silent=True) or {}
    session_id = (data.get("session_id") or "").strip()
    include_ok = bool(data.get("include_ok", True))  # kept for UI compatibility (unused here)
    max_themes = int(data.get("max_themes") or 500)

    if not session_id:
        return jsonify({"ok": False, "error": "Missing session_id"}), 400

    try:
        s = _get_session(session_id)
        _, wp_root = _ensure_context(s, data)
        if not wp_root:
            return jsonify({"ok": False, "error": "No wp_root selected"}), 400

        res = themes_preview(
            s["host"], s["port"], s["username"], s["password"],
            wp_root,
            max_themes=max_themes,
        )
        return jsonify(res)

    except Exception as e:
        current_app.logger.exception("themes preview failed")
        return jsonify({"ok": False, "error": str(e)}), 400


@bp.post("/fix/themes/disable")
@jwt_required()
def api_fix_themes_disable():
    data = request.get_json(silent=True) or {}
    session_id = (data.get("session_id") or "").strip()
    if not session_id:
        return jsonify({"ok": False, "error": "Missing session_id"}), 400

    slugs = data.get("slugs") or []
    reason = (data.get("reason") or "manual_disable").strip()

    if isinstance(slugs, str):
        slugs = [slugs]
    slugs = [s.strip().strip("/") for s in slugs if isinstance(s, str) and s.strip()]
    if not slugs:
        return jsonify({"ok": False, "error": "No theme slugs provided (slugs[])"}), 400

    action = None
    try:
        s = _get_session(session_id)
        _, wp_root = _ensure_context(s, data)
        if not wp_root:
            return jsonify({"ok": False, "error": "No wp_root selected"}), 400

        action = create_action(
            s["host"], s["port"], s["username"], s["password"],
            wp_root=wp_root,
            fix_id="themes_disable",
            context={"reason": reason, "slugs": slugs},
            ticket_id=int(s.get("ticket_id") or 0),
            actor_user_id=int(s.get("actor_user_id") or 0),
            actor_name=s.get("actor_name"),
            project_root=s.get("project_root"),
        )

        res = themes_disable_apply(
            s["host"], s["port"], s["username"], s["password"],
            wp_root,
            slugs=slugs,
        )

        disabled = res.get("disabled") or []
        skipped = res.get("skipped") or []
        errors = res.get("errors") or []

        meta = json.loads(read_text_remote(s["host"], s["port"], s["username"], s["password"], action["meta_path"]))
        _meta_ensure(meta)
        meta.setdefault("moved", [])
        for d in disabled:
            src = d.get("src")
            dst = d.get("dst")
            slug = d.get("slug")
            if src and dst:
                meta["moved"].append({"src": src, "dst": dst})
                try:
                    add_file_op(
                        action["action_id"],
                        op="renamed",
                        src_path=src,
                        dst_path=dst,
                        payload_json={"slug": slug, "reason": reason},
                    )
                except Exception:
                    pass

        if len(disabled) > 0 and len(errors) == 0:
            final_status = "applied"
        elif len(disabled) > 0 and len(errors) > 0:
            final_status = "partial"
        elif len(disabled) == 0 and len(errors) > 0:
            final_status = "failed"
        else:
            final_status = "skipped"

        meta["status"] = final_status
        _meta_note(meta, f"disabled={len(disabled)} skipped={len(skipped)} errors={len(errors)}")
        _meta_event(meta, f"themes_disable status={final_status} disabled={len(disabled)} skipped={len(skipped)} errors={len(errors)}")
        meta["result"] = {
            "disabled": disabled,
            "skipped": skipped,
            "errors": errors,
            "counts": {"disabled": len(disabled), "skipped": len(skipped), "errors": len(errors)},
        }

        write_text_remote(
            s["host"], s["port"], s["username"], s["password"],
            action["meta_path"],
            json.dumps(meta, ensure_ascii=False, indent=2),
        )

        _db_status(
            action["action_id"],
            final_status,
            result=meta["result"] if final_status in ("applied", "partial", "skipped") else None,
            error=None if final_status in ("applied", "partial", "skipped") else {"errors": errors},
            meta=meta,
        )

        append_log(
            s["host"], s["port"], s["username"], s["password"],
            wp_root,
            {
                "ts": int(time.time()),
                "type": "fix",
                "fix_id": "themes_disable",
                "action_id": action["action_id"],
                "ok": final_status in ("applied", "partial"),
                "status": final_status,
                "disabled": len(disabled),
                "skipped": len(skipped),
                "errors": len(errors),
            },
        )

        return jsonify({"ok": True, "action_id": action["action_id"], "status": final_status, "result": meta["result"]})

    except Exception as e:
        current_app.logger.exception("themes disable failed")
        if action:
            _db_status(action["action_id"], "failed", error={"error": str(e)})
        return jsonify({"ok": False, "error": str(e)}), 400


@bp.post("/fix/themes/scan")
@jwt_required()
def api_fix_themes_scan():
    """
    Body:
    {
      "session_id": "...",
      "wp_root": "...",          # optional
      "slugs": ["astra"],        # optional; if empty => scan ALL themes dir
      "max_files": 800,
      "max_bytes": 250000
    }
    """
    data = request.get_json(silent=True) or {}
    session_id = (data.get("session_id") or "").strip()
    if not session_id:
        return jsonify({"ok": False, "error": "Missing session_id"}), 400

    slugs = data.get("slugs") or []
    if isinstance(slugs, str):
        slugs = [slugs]
    slugs = [s.strip().strip("/") for s in slugs if isinstance(s, str) and s.strip()]

    max_files = int(data.get("max_files") or 800)
    max_bytes = int(data.get("max_bytes") or 250_000)

    action = None
    try:
        s = _get_session(session_id)
        _, wp_root = _ensure_context(s, data)
        if not wp_root:
            return jsonify({"ok": False, "error": "No wp_root selected"}), 400

        action = create_action(
            s["host"], s["port"], s["username"], s["password"],
            wp_root=wp_root,
            fix_id="themes_scan",
            context={"slugs": slugs, "max_files": max_files, "max_bytes": max_bytes},
            ticket_id=int(s.get("ticket_id") or 0),
            actor_user_id=int(s.get("actor_user_id") or 0),
            actor_name=s.get("actor_name"),
            project_root=s.get("project_root"),
        )

        themes_dir = posixpath.join(wp_root.rstrip("/"), "wp-content", "themes")
        targets = []
        if slugs:
            for slug in slugs:
                targets.append(posixpath.join(themes_dir, slug))
        else:
            targets = [themes_dir]

        try:
            add_finding(
                action["action_id"],
                path=themes_dir,
                severity="low",
                kind="themes_scan_context",
                detail_json={"targets": targets, "max_files": max_files, "max_bytes": max_bytes},
            )
        except Exception:
            pass

        agg = {"ok": True, "targets": targets, "results": [], "counts": {"scanned": 0, "files_with_hits": 0, "hits_total": 0, "errors": 0}}
        for t in targets:
            r = theme_code_scan_apply(
                s["host"], s["port"], s["username"], s["password"],
                action_id=action["action_id"],
                theme_root=t,
                max_files=max_files,
                max_bytes=max_bytes,
            )
            agg["results"].append({"target": t, "result": r})
            c = (r.get("counts") or {})
            for k in agg["counts"].keys():
                agg["counts"][k] += int(c.get(k) or 0)

        _db_status(action["action_id"], "applied", result=agg, meta={"fix_id": "themes_scan", "counts": agg["counts"]})
        return jsonify({"ok": True, "action_id": action["action_id"], "result": agg})

    except Exception as e:
        current_app.logger.exception("themes scan failed")
        if action:
            _db_status(action["action_id"], "failed", error={"error": str(e)})
        return jsonify({"ok": False, "error": str(e)}), 400


@bp.post("/fix/themes/restore")
@jwt_required()
def api_fix_themes_restore():
    data = request.get_json(silent=True) or {}
    session_id = (data.get("session_id") or "").strip()
    if not session_id:
        return jsonify({"ok": False, "error": "Missing session_id"}), 400

    slugs = data.get("slugs") or []
    if isinstance(slugs, str):
        slugs = [slugs]
    slugs = [s.strip().strip("/") for s in slugs if isinstance(s, str) and s.strip()]
    if not slugs:
        return jsonify({"ok": False, "error": "No theme slugs provided (slugs[])"}), 400

    reason = (data.get("reason") or "restore_theme").strip()
    connect_timeout = int(data.get("connect_timeout") or 15)
    op_timeout = int(data.get("op_timeout") or 20)

    action = None
    try:
        s = _get_session(session_id)
        _, wp_root = _ensure_context(s, data)
        if not wp_root:
            return jsonify({"ok": False, "error": "No wp_root selected"}), 400

        action = create_action(
            s["host"], s["port"], s["username"], s["password"],
            wp_root=wp_root,
            fix_id="themes_restore",
            context={"reason": reason, "slugs": slugs},
            ticket_id=int(s.get("ticket_id") or 0),
            actor_user_id=int(s.get("actor_user_id") or 0),
            actor_name=s.get("actor_name"),
            project_root=s.get("project_root"),
        )

        res = themes_restore_apply(
            s["host"], int(s["port"]), s["username"], s["password"],
            wp_root=wp_root,
            slugs=slugs,
            connect_timeout=connect_timeout,
            op_timeout=op_timeout,
        )

        restored = res.get("restored") or []
        skipped = res.get("skipped") or []
        errors = res.get("errors") or []
        counts = res.get("counts") or {"restored": len(restored), "skipped": len(skipped), "errors": len(errors)}

        for it in restored:
            src = it.get("src")
            dst = it.get("dst")
            slug = it.get("slug")
            if src and dst:
                try:
                    add_file_op(
                        action["action_id"],
                        op="renamed",
                        src_path=src,
                        dst_path=dst,
                        payload_json={"slug": slug, "reason": reason, "module": "themes_restore"},
                    )
                except Exception:
                    pass

        if errors and restored:
            final_status = "partial"
        elif errors and not restored:
            final_status = "failed"
        elif not restored and skipped:
            final_status = "skipped"
        else:
            final_status = "applied"

        _db_status(
            action["action_id"],
            final_status,
            result=res if final_status in ("applied", "partial", "skipped") else None,
            error=None if final_status in ("applied", "partial", "skipped") else {"errors": errors},
            meta={"fix_id": "themes_restore", "counts": counts},
        )

        append_log(
            s["host"], s["port"], s["username"], s["password"],
            wp_root,
            {
                "ts": int(time.time()),
                "type": "fix",
                "fix_id": "themes_restore",
                "action_id": action["action_id"],
                "ok": final_status in ("applied", "partial"),
                "status": final_status,
                "restored": len(restored),
                "skipped": len(skipped),
                "errors": len(errors),
            },
        )

        return jsonify({"ok": True, "action_id": action["action_id"], "status": final_status, "result": res})

    except Exception as e:
        current_app.logger.exception("themes restore failed")
        if action:
            _db_status(action["action_id"], "failed", error={"error": str(e)})
        return jsonify({"ok": False, "error": str(e)}), 400


@bp.post("/fix/plugins/scan")
@jwt_required()
def api_fix_plugins_scan():
    """
    Body:
    {
      "session_id": "...",
      "wp_root": "...",          # optional
      "slugs": ["akismet"],      # optional; wenn leer => scan ALL plugins dir
      "max_files": 800,
      "max_bytes": 250000
    }
    """
    data = request.get_json(silent=True) or {}
    session_id = (data.get("session_id") or "").strip()
    if not session_id:
        return jsonify({"ok": False, "error": "Missing session_id"}), 400

    slugs = data.get("slugs") or []
    if isinstance(slugs, str):
        slugs = [slugs]
    slugs = [s.strip().strip("/") for s in slugs if isinstance(s, str) and s.strip()]

    max_files = int(data.get("max_files") or 800)
    max_bytes = int(data.get("max_bytes") or 250_000)

    action = None
    try:
        s = _get_session(session_id)
        _, wp_root = _ensure_context(s, data)
        if not wp_root:
            return jsonify({"ok": False, "error": "No wp_root selected"}), 400

        action = create_action(
            s["host"], s["port"], s["username"], s["password"],
            wp_root=wp_root,
            fix_id="plugins_scan",
            context={"slugs": slugs, "max_files": max_files, "max_bytes": max_bytes},
            ticket_id=int(s.get("ticket_id") or 0),
            actor_user_id=int(s.get("actor_user_id") or 0),
            actor_name=s.get("actor_name"),
            project_root=s.get("project_root"),
        )

        plugins_dir = posixpath.join(wp_root.rstrip("/"), "wp-content", "plugins")
        targets = []
        if slugs:
            for slug in slugs:
                targets.append(posixpath.join(plugins_dir, slug))
        else:
            targets = [plugins_dir]

        try:
            add_finding(
                action["action_id"],
                path=plugins_dir,
                severity="low",
                kind="plugins_scan_context",
                detail_json={"targets": targets, "max_files": max_files, "max_bytes": max_bytes},
            )
        except Exception:
            pass

        agg = {
            "ok": True,
            "targets": targets,
            "results": [],
            "counts": {"scanned": 0, "files_with_hits": 0, "hits_total": 0, "errors": 0},
        }

        for t in targets:
            r = plugin_code_scan_apply(
                s["host"], s["port"], s["username"], s["password"],
                action_id=action["action_id"],
                plugin_root=t,
                max_files=max_files,
                max_bytes=max_bytes,
            )
            agg["results"].append({"target": t, "result": r})
            c = (r.get("counts") or {})
            for k in agg["counts"].keys():
                agg["counts"][k] += int(c.get(k) or 0)

        _db_status(
            action["action_id"],
            "applied",
            result=agg,
            meta={"fix_id": "plugins_scan", "counts": agg["counts"]},
        )
        return jsonify({"ok": True, "action_id": action["action_id"], "result": agg})

    except Exception as e:
        current_app.logger.exception("plugins scan failed")
        if action:
            _db_status(action["action_id"], "failed", error={"error": str(e)})
        return jsonify({"ok": False, "error": str(e)}), 400


# NOTE:
# Ab hier hast du in deinem Paste noch sehr viele weitere Endpoints (database preview/scan/apply, diagnostics, explorer, patch, ...)
# Die sind unverändert geblieben, weil die von dir gepastete Datei hier ab dem Punkt bereits vollständig weiterging.
# Wenn du willst, kann ich dir auch den kompletten Rest "durch-normalisieren" (meta/events überall über _meta_*),
# aber funktional sind die kritischen Crashes/Formatbrüche damit behoben.

@bp.post("/fix/database/preview")
@jwt_required()
def api_fix_database_preview():
    data = request.get_json(silent=True) or {}
    session_id = (data.get("session_id") or "").strip()
    if not session_id:
        return jsonify({"ok": False, "error": "Missing session_id"}), 400

    try:
        s = _get_session(session_id)
        _, wp_root = _ensure_context(s, data)
        if not wp_root:
            return jsonify({"ok": False, "error": "No wp_root selected"}), 400

        domain = (data.get("domain") or s.get("domain") or "").strip()

        res = db_repair_preview(
            s["host"], s["port"], s["username"], s["password"],
            wp_root,
            domain=domain or None,
        )
        return jsonify(res)

    except Exception as e:
        current_app.logger.exception("database preview failed")
        return jsonify({"ok": False, "error": str(e)}), 400


@bp.post("/fix/database/scan")
@jwt_required()
def api_fix_database_scan():
    data = request.get_json(silent=True) or {}
    session_id = (data.get("session_id") or "").strip()
    if not session_id:
        return jsonify({"ok": False, "error": "Missing session_id"}), 400

    timeout = int(data.get("timeout") or 15)

    try:
        s = _get_session(session_id)
        _, wp_root = _ensure_context(s, data)
        if not wp_root:
            return jsonify({"ok": False, "error": "No wp_root selected"}), 400

        domain = (data.get("domain") or s.get("domain") or "").strip()

        res = db_repair_scan(
            s["host"], s["port"], s["username"], s["password"],
            wp_root,
            domain=domain or None,
            timeout=timeout,
        )
        return jsonify(res)

    except Exception as e:
        current_app.logger.exception("database scan failed")
        return jsonify({"ok": False, "error": str(e)}), 400


@bp.post("/fix/database/apply")
@jwt_required()
def api_fix_database_apply():
    data = request.get_json(silent=True) or {}
    session_id = (data.get("session_id") or "").strip()
    if not session_id:
        return jsonify({"ok": False, "error": "Missing session_id"}), 400

    mode = (data.get("mode") or "repair_optimize").strip()
    if mode not in {"repair", "repair_optimize"}:
        return jsonify({"ok": False, "error": "Invalid mode (use 'repair' or 'repair_optimize')"}), 400

    http_timeout = int(data.get("http_timeout") or 25)

    action = None
    try:
        s = _get_session(session_id)
        _, wp_root = _ensure_context(s, data)
        if not wp_root:
            return jsonify({"ok": False, "error": "No wp_root selected"}), 400

        domain = (data.get("domain") or s.get("domain") or "").strip()
        if not domain:
            return jsonify({"ok": False, "error": "Missing domain (site_url)"}), 400

        action = create_action(
            s["host"], s["port"], s["username"], s["password"],
            wp_root=wp_root,
            fix_id="database_repair",
            context={"mode": mode, "http_timeout": http_timeout, "domain": domain},
            ticket_id=int(s.get("ticket_id") or 0),
            actor_user_id=int(s.get("actor_user_id") or 0),
            actor_name=s.get("actor_name"),
            project_root=s.get("project_root"),
        )

        res = db_repair_apply(
            s["host"], s["port"], s["username"], s["password"],
            wp_root,
            action_id=action["action_id"],
            moved_dir=action["moved_dir"],
            meta_path=action["meta_path"],
            domain=domain,
            mode=mode,
            http_timeout=http_timeout,
        )

        _db_status(
            action["action_id"],
            "applied" if res.get("ok") else "partial",
            result=res,
            meta={"fix_id": "database_repair", "mode": mode},
        )
        return jsonify({"ok": True, "action_id": action["action_id"], "result": res})

    except Exception as e:
        current_app.logger.exception("database apply failed")
        if action:
            _db_status(action["action_id"], "failed", error={"error": str(e)})
        return jsonify({"ok": False, "error": str(e)}), 400



@bp.post("/fix/diagnostics/preview")
@jwt_required()
def api_fix_diagnostics_preview():
    data = request.get_json(silent=True) or {}
    session_id = (data.get("session_id") or "").strip()
    if not session_id:
        return jsonify({"ok": False, "error": "Missing session_id"}), 400

    try:
        s = _get_session(session_id)
        _, wp_root = _ensure_context(s, data)
        if not wp_root:
            return jsonify({"ok": False, "error": "No wp_root selected"}), 400

        res = diagnostics_preview(
            s["host"], s["port"], s["username"], s["password"], wp_root
        )
        return jsonify(res)

    except Exception as e:
        current_app.logger.exception("diagnostics preview failed")
        return jsonify({"ok": False, "error": str(e)}), 400


@bp.post("/fix/diagnostics/enable")
@jwt_required()
def api_fix_diagnostics_enable():
    data = request.get_json(silent=True) or {}
    session_id = (data.get("session_id") or "").strip()
    if not session_id:
        return jsonify({"ok": False, "error": "Missing session_id"}), 400

    action = None
    try:
        s = _get_session(session_id)
        _, wp_root = _ensure_context(s, data)
        if not wp_root:
            return jsonify({"ok": False, "error": "No wp_root selected"}), 400

        res = diagnostics_enable(
            s["host"], s["port"], s["username"], s["password"], wp_root,
            ticket_id=int(s.get("ticket_id") or 0),
            actor_user_id=int(s.get("actor_user_id") or 0),
            actor_name=s.get("actor_name"),
            project_root=s.get("project_root"),
            enable=True,
        )
        return jsonify(res)

    except Exception as e:
        current_app.logger.exception("diagnostics enable failed")
        return jsonify({"ok": False, "error": str(e)}), 400


@bp.post("/fix/diagnostics/scan")
@jwt_required()
def api_fix_diagnostics_scan():
    data = request.get_json(silent=True) or {}
    session_id = (data.get("session_id") or "").strip()
    if not session_id:
        return jsonify({"ok": False, "error": "Missing session_id"}), 400

    tail_lines = int(data.get("tail_lines") or 250)

    try:
        s = _get_session(session_id)
        _, wp_root = _ensure_context(s, data)
        if not wp_root:
            return jsonify({"ok": False, "error": "No wp_root selected"}), 400

        res = diagnostics_scan(
            s["host"], s["port"], s["username"], s["password"], wp_root,
            tail_lines=tail_lines,
        )
        return jsonify(res)

    except Exception as e:
        current_app.logger.exception("diagnostics scan failed")
        return jsonify({"ok": False, "error": str(e)}), 400


@bp.post("/fix/diagnostics/apply_fix")
@jwt_required()
def api_fix_diagnostics_apply_fix():
    data = request.get_json(silent=True) or {}
    session_id = (data.get("session_id") or "").strip()
    if not session_id:
        return jsonify({"ok": False, "error": "Missing session_id"}), 400

    fix_id = (data.get("fix_id") or "").strip()
    params = data.get("params") or {}
    if not fix_id:
        return jsonify({"ok": False, "error": "Missing fix_id"}), 400

    try:
        s = _get_session(session_id)
        _, wp_root = _ensure_context(s, data)
        if not wp_root:
            return jsonify({"ok": False, "error": "No wp_root selected"}), 400

        res = diagnostics_apply_fix(
            s["host"], s["port"], s["username"], s["password"], wp_root,
            fix_id=fix_id,
            params=params,
            ticket_id=int(s.get("ticket_id") or 0),
            actor_user_id=int(s.get("actor_user_id") or 0),
            actor_name=s.get("actor_name"),
            project_root=s.get("project_root"),
        )
        return jsonify(res)

    except Exception as e:
        current_app.logger.exception("diagnostics apply_fix failed")
        return jsonify({"ok": False, "error": str(e)}), 400


@bp.post("/fix/explorer/ls")
@jwt_required()
def api_fix_explorer_ls():
    data = request.get_json(silent=True) or {}
    session_id = (data.get("session_id") or "").strip()
    if not session_id:
        return jsonify({"ok": False, "error": "Missing session_id"}), 400

    try:
        s = _get_session(session_id)
        _, wp_root = _ensure_context(s, data)
        if not wp_root:
            return jsonify({"ok": False, "error": "No wp_root selected"}), 400

        path = data.get("path") or wp_root
        max_entries = int(data.get("max_entries") or 400)

        res = explorer_ls(s["host"], s["port"], s["username"], s["password"], wp_root, path, max_entries=max_entries)
        return jsonify(res)

    except Exception as e:
        current_app.logger.exception("explorer ls failed")
        return jsonify({"ok": False, "error": str(e)}), 400


@bp.post("/fix/explorer/read")
@jwt_required()
def api_fix_explorer_read():
    data = request.get_json(silent=True) or {}
    session_id = (data.get("session_id") or "").strip()
    if not session_id:
        return jsonify({"ok": False, "error": "Missing session_id"}), 400

    try:
        s = _get_session(session_id)
        _, wp_root = _ensure_context(s, data)
        if not wp_root:
            return jsonify({"ok": False, "error": "No wp_root selected"}), 400

        path = data.get("path")
        if not path:
            return jsonify({"ok": False, "error": "Missing path"}), 400

        max_bytes = int(data.get("max_bytes") or 200_000)
        mask_secrets = bool(data.get("mask_secrets", True))

        res = explorer_read(
            s["host"], s["port"], s["username"], s["password"],
            wp_root, path,
            max_bytes=max_bytes,
            mask_secrets=mask_secrets,
        )
        return jsonify(res)

    except Exception as e:
        current_app.logger.exception("explorer read failed")
        return jsonify({"ok": False, "error": str(e)}), 400



@bp.post("/fix/explorer/write")
@jwt_required()
def api_fix_explorer_write():
    data = request.get_json(silent=True) or {}
    session_id = (data.get("session_id") or "").strip()
    if not session_id:
        return jsonify({"ok": False, "error": "Missing session_id"}), 400

    try:
        s = _get_session(session_id)
        _, wp_root = _ensure_context(s, data)
        if not wp_root:
            return jsonify({"ok": False, "error": "No wp_root selected"}), 400

        path = data.get("path")
        if not path:
            return jsonify({"ok": False, "error": "Missing path"}), 400

        text = data.get("text")
        reason = (data.get("reason") or "manual edit via explorer").strip()
        create_parents = bool(data.get("create_parents", True))

        res = explorer_write(
            s["host"], s["port"], s["username"], s["password"], wp_root,
            path, text,
            reason=reason,
            ticket_id=int(s.get("ticket_id") or 0),
            actor_user_id=int(s.get("actor_user_id") or 0),
            actor_name=s.get("actor_name"),
            project_root=s.get("project_root"),
            create_parents=create_parents,
        )
        return jsonify(res)

    except Exception as e:
        current_app.logger.exception("explorer write failed")
        return jsonify({"ok": False, "error": str(e)}), 400


@bp.post("/fix/explorer/ai_help")
@jwt_required()
def api_fix_explorer_ai_help():
    data = request.get_json(silent=True) or {}
    session_id = (data.get("session_id") or "").strip()
    if not session_id:
        return jsonify({"ok": False, "error": "Missing session_id"}), 400

    try:
        s = _get_session(session_id)
        _, wp_root = _ensure_context(s, data)
        if not wp_root:
            return jsonify({"ok": False, "error": "No wp_root selected"}), 400

        path = data.get("path")
        if not path:
            return jsonify({"ok": False, "error": "Missing path"}), 400

        log_excerpt = data.get("log_excerpt")
        goal = data.get("goal")
        max_bytes = int(data.get("max_bytes") or 200_000)

        res = explorer_ai_help(
            s["host"], s["port"], s["username"], s["password"], wp_root,
            path,
            log_excerpt=log_excerpt,
            goal=goal,
            max_bytes=max_bytes,
        )
        return jsonify(res)

    except Exception as e:
        current_app.logger.exception("explorer ai_help failed")
        return jsonify({"ok": False, "error": str(e)}), 400


@bp.post("/fix/explorer/patch/preview")
@jwt_required()
def api_fix_explorer_patch_preview():
    data = request.get_json(silent=True) or {}
    session_id = (data.get("session_id") or "").strip()
    if not session_id:
        return jsonify({"ok": False, "error": "Missing session_id"}), 400

    try:
        s = _get_session(session_id)
        _, wp_root = _ensure_context(s, data)
        if not wp_root:
            return jsonify({"ok": False, "error": "No wp_root selected"}), 400

        path = data.get("path")
        if not path:
            return jsonify({"ok": False, "error": "Missing path"}), 400

        mode = data.get("mode")  # "replace_block" or "unified_diff" or null
        replace_block = data.get("replace_block")
        unified_diff = data.get("unified_diff")
        max_bytes = int(data.get("max_bytes") or 200_000)

        res = patch_preview(
            s["host"], s["port"], s["username"], s["password"], wp_root,
            path=path,
            mode=mode,
            replace_block=replace_block,
            unified_diff=unified_diff,
            max_bytes=max_bytes,
        )
        return jsonify(res)

    except Exception as e:
        current_app.logger.exception("explorer patch preview failed")
        return jsonify({"ok": False, "error": str(e)}), 400


@bp.post("/fix/explorer/patch/apply")
@jwt_required()
def api_fix_explorer_patch_apply():
    data = request.get_json(silent=True) or {}
    session_id = (data.get("session_id") or "").strip()
    if not session_id:
        return jsonify({"ok": False, "error": "Missing session_id"}), 400

    try:
        s = _get_session(session_id)
        _, wp_root = _ensure_context(s, data)
        if not wp_root:
            return jsonify({"ok": False, "error": "No wp_root selected"}), 400

        path = data.get("path")
        if not path:
            return jsonify({"ok": False, "error": "Missing path"}), 400

        mode = data.get("mode")
        replace_block = data.get("replace_block")
        unified_diff = data.get("unified_diff")
        reason = (data.get("reason") or "apply patch via explorer").strip()

        res = patch_apply(
            s["host"], s["port"], s["username"], s["password"], wp_root,
            path=path,
            mode=mode,
            replace_block=replace_block,
            unified_diff=unified_diff,
            reason=reason,
            ticket_id=int(s.get("ticket_id") or 0),
            actor_user_id=int(s.get("actor_user_id") or 0),
            actor_name=s.get("actor_name"),
            project_root=s.get("project_root"),
        )
        return jsonify(res)

    except Exception as e:
        current_app.logger.exception("explorer patch apply failed")
        return jsonify({"ok": False, "error": str(e)}), 400


@bp.post("/fix/explorer/patch/validate")
@jwt_required()
def api_fix_explorer_patch_validate():
    data = request.get_json(silent=True) or {}
    session_id = (data.get("session_id") or "").strip()
    if not session_id:
        return jsonify({"ok": False, "error": "Missing session_id"}), 400

    try:
        s = _get_session(session_id)
        _, wp_root = _ensure_context(s, data)
        if not wp_root:
            return jsonify({"ok": False, "error": "No wp_root selected"}), 400

        path = data.get("path")
        if not path:
            return jsonify({"ok": False, "error": "Missing path"}), 400

        mode = data.get("mode")
        replace_block = data.get("replace_block")
        unified_diff = data.get("unified_diff")
        max_bytes = int(data.get("max_bytes") or 200_000)

        res = patch_validate(
            s["host"], s["port"], s["username"], s["password"], wp_root,
            path=path, mode=mode, replace_block=replace_block, unified_diff=unified_diff, max_bytes=max_bytes
        )
        return jsonify(res)

    except Exception as e:
        current_app.logger.exception("explorer patch validate failed")
        return jsonify({"ok": False, "error": str(e)}), 400
