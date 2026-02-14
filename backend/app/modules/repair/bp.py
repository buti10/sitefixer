# app/modules/repair/bp.py
from __future__ import annotations

from flask import Blueprint, request, jsonify, current_app
from app.extensions import db
from app.models_repair import RepairSession, RepairCheckpoint, RepairLog

from .sftp_ops import (
    list_dir as _list_dir,
    read_file as _read_file,
    rename_path as _rename_path,
    mkdir_path as _mkdir_path,
    delete_file as _delete_file,
    rmdir_path as _rmdir_path,
    chmod_path as _chmod_path,
    write_file as _write_file,
    SFTPUnavailable,
)

bp = Blueprint("repair", __name__, url_prefix="/api/repair")


# ----------------------------
# Helpers
# ----------------------------

def _resolve_session_id_from_payload(d: dict) -> int:
    """
    Accepts:
      - session_id as int (RepairSession.id)
      - session_id as numeric string
      - sid as uuid string (SFTP-SID), via keys: sid / session_sid / sftp_sid / session_id
    Returns:
      - RepairSession.id (int) or 0 if not found
    """
    v = d.get("session_id")
    if v is None:
        v = d.get("sid") or d.get("session_sid") or d.get("sftp_sid")

    if v is None:
        return 0

    if isinstance(v, int):
        return int(v)

    s = str(v).strip()
    if not s:
        return 0

    if s.isdigit():
        return int(s)

    rs = (
        RepairSession.query.filter_by(sid=s)
        .order_by(RepairSession.id.desc())
        .first()
    )
    return int(rs.id) if rs else 0


def _require_session_id(d: dict) -> int:
    sid = _resolve_session_id_from_payload(d)
    if not sid:
        raise ValueError("session not found (session_id/sid)")
    return sid


def _validate_active_sftp_sid(sid: str) -> bool:
    """
    Validates SID exists in current SFTP session pool.
    Note: if gunicorn has multiple workers and pool is in-memory, this can fail
    depending on which worker handles the request.
    """
    try:
        from app.scanner.sftp_adapter import get_client_by_sid
        return bool(get_client_by_sid(sid))
    except Exception:
        current_app.logger.exception("SID validation failed")
        return False


# ----------------------------
# Session
# ----------------------------

@bp.post("/session")
def create_session():
    d = request.get_json(force=True) or {}
    ticket_id = int(d.get("ticket_id") or 0)

    # accept multiple key names for compatibility
    sid = (d.get("sid") or d.get("sftp_sid") or d.get("session_sid") or "").strip()
    root = (d.get("root") or "/").strip()

    if not (ticket_id and sid and root):
        return jsonify({"error": "ticket_id, sid, root required"}), 400

    if not _validate_active_sftp_sid(sid):
        return jsonify({"error": f"invalid sid (no active sftp session): {sid}"}), 400

    s = RepairSession(
        ticket_id=ticket_id,
        sid=sid,
        root=root,
        cms=d.get("cms"),
        cms_version=d.get("cms_version"),
    )
    db.session.add(s)
    db.session.commit()
    return jsonify({"session_id": s.id})


# ----------------------------
# SFTP Listing
# ----------------------------

@bp.get("/sftp/list")
def sftp_list():
    session_id = int(request.args.get("session_id") or 0)
    path = request.args.get("path")
    if not session_id:
        return jsonify({"error": "session_id required"}), 400
    try:
        body, code = _list_dir(session_id, path)
        return jsonify(body), code
    except SFTPUnavailable as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        current_app.logger.exception("sftp_list failed")
        return jsonify({"error": str(e)}), 500


# ----------------------------
# Action log (store as RepairLog to avoid missing RepairAction model)
# ----------------------------

@bp.post("/action")
def log_action():
    """
    Old frontend posts actions here. We store them as RepairLog entries.
    This avoids dependency on a RepairAction model that doesn't exist.
    """
    d = request.get_json(force=True) or {}
    session_id = int(d.get("session_id") or 0)
    kind = (d.get("kind") or "").strip()
    if not (session_id and kind):
        return jsonify({"error": "session_id and kind required"}), 400

    lg = RepairLog(
        session_id=session_id,
        level="ACTION",
        message=kind,
        context={
            "src": d.get("src"),
            "dst": d.get("dst"),
            "meta": d.get("meta") or {},
            "success": bool(d.get("success")),
            "error_msg": d.get("error_msg"),
        },
    )
    db.session.add(lg)
    db.session.commit()
    return jsonify({"ok": True})


@bp.post("/log")
def write_log():
    d = request.get_json(force=True) or {}
    session_id = int(d.get("session_id") or 0)
    message = d.get("message") or ""
    if not (session_id and message):
        return jsonify({"error": "session_id and message required"}), 400

    lg = RepairLog(
        session_id=session_id,
        level=(d.get("level") or "INFO").upper()[:10],
        message=message,
        context=d.get("context") or {},
    )
    db.session.add(lg)
    db.session.commit()
    return jsonify({"ok": True})


# ----------------------------
# FS Routes (compat)
# ----------------------------

@bp.post("/fs/rename")
def fs_rename():
    d = request.get_json(force=True) or {}

    # session resolve (int session_id or sid)
    try:
        session_id = _require_session_id(d)
    except ValueError as e:
        return jsonify({"error": str(e)}), 404

    # akzeptiere viele Feldnamen
    src = (
        d.get("src")
        or d.get("from")
        or d.get("oldPath")
        or d.get("old_path")
        or d.get("path")
    )

    dst = (
        d.get("dst")
        or d.get("to")
        or d.get("newPath")
        or d.get("new_path")
    )

    # Sonderfall: UI sendet path + new_name
    new_name = d.get("new_name") or d.get("name") or d.get("newName")
    if src and not dst and new_name:
        import posixpath
        parent = posixpath.dirname(src.rstrip("/")) or "/"
        dst = posixpath.join(parent, str(new_name).strip())

    if not (src and dst):
        return jsonify({
            "error": "rename payload invalid (need src+dst or path+new_name)",
            "received_keys": sorted(list(d.keys()))
        }), 400

    try:
        body, code = _rename_path(session_id, src, dst)
        return jsonify(body), code
    except SFTPUnavailable as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        current_app.logger.exception("fs_rename failed")
        return jsonify({"error": str(e)}), 500



@bp.post("/fs/mkdir")
def fs_mkdir():
    d = request.get_json(force=True) or {}
    path = d.get("path")
    if not path:
        return jsonify({"error": "path required"}), 400

    try:
        session_id = _require_session_id(d)
        body, code = _mkdir_path(session_id, path)
        return jsonify(body), code
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except SFTPUnavailable as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        current_app.logger.exception("fs_mkdir failed")
        return jsonify({"error": str(e)}), 500


@bp.post("/fs/delete")
def fs_delete():
    d = request.get_json(force=True) or {}
    path = d.get("path")
    kind = (d.get("kind") or "file").lower()
    if not path:
        return jsonify({"error": "path required"}), 400

    try:
        session_id = _require_session_id(d)
        if kind == "dir":
            body, code = _rmdir_path(session_id, path)
        else:
            body, code = _delete_file(session_id, path)
        return jsonify(body), code
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except SFTPUnavailable as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        current_app.logger.exception("fs_delete failed")
        return jsonify({"error": str(e)}), 500


@bp.post("/fs/chmod")
def fs_chmod():
    d = request.get_json(force=True) or {}
    path = d.get("path")
    mode = d.get("mode")
    if not path or mode is None:
        return jsonify({"error": "path, mode required"}), 400

    try:
        session_id = _require_session_id(d)
        if isinstance(mode, str):
            mode_int = int(mode.strip(), 8)
        else:
            mode_int = int(mode)
        body, code = _chmod_path(session_id, path, mode_int)
        return jsonify(body), code
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except SFTPUnavailable as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        current_app.logger.exception("fs_chmod failed")
        return jsonify({"error": str(e)}), 500


@bp.get("/fs/read")
def fs_read():
    q = request.args
    d = {
        "session_id": q.get("session_id"),
        "sid": q.get("sid") or q.get("sftp_sid") or q.get("session_sid"),
    }
    path = q.get("path")
    if not path:
        return jsonify({"error": "path required"}), 400

    try:
        session_id = _require_session_id(d)
        body, code = _read_file(session_id, path)
        return jsonify(body), code
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except SFTPUnavailable as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        current_app.logger.exception("fs_read failed")
        return jsonify({"error": str(e)}), 500


@bp.post("/fs/write")
def fs_write():
    d = request.get_json(force=True) or {}
    path = d.get("path")
    text = d.get("text")
    b64 = d.get("base64")
    if not path:
        return jsonify({"error": "path required"}), 400

    try:
        session_id = _require_session_id(d)
        body, code = _write_file(session_id, path, text=text, b64=b64)
        return jsonify(body), code
    except ValueError as e:
        return jsonify({"error": str(e)}), 404
    except SFTPUnavailable as e:
        return jsonify({"error": str(e)}), 500
    except Exception as e:
        current_app.logger.exception("fs_write failed")
        return jsonify({"error": str(e)}), 500
