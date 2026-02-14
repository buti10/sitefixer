# app/modules/repair_beta/routes_wp.py
from __future__ import annotations
from flask import Blueprint, request, jsonify

from .sftp_client import SFTPConn, RepairError
from .wp_repair import wp_diagnose, fix_rotate_debug_log, fix_permissions

bp = Blueprint("repair_beta_wp", __name__, url_prefix="/api/repair-beta/wp")


def _conn_from_json(data) -> SFTPConn:
    return SFTPConn(
        host=data.get("host", ""),
        port=int(data.get("port", 22) or 22),
        user=data.get("user", ""),
        password=data.get("password", ""),
    )


@bp.post("/diagnose")
def diagnose():
    data = request.get_json(force=True, silent=True) or {}
    try:
        conn = _conn_from_json(data)
        wp_root = data.get("wp_root", "")
        if not (conn.host and conn.user and conn.password and wp_root):
            return jsonify({"ok": False, "msg": "host/user/password/wp_root fehlen"}), 400
        return jsonify(wp_diagnose(conn, wp_root))
    except RepairError as e:
        return jsonify({"ok": False, "msg": str(e)}), 400
    except Exception as e:
        return jsonify({"ok": False, "msg": f"Diagnose error: {e}"}), 500


@bp.post("/fix/rotate-debug-log")
def fix_rotate():
    data = request.get_json(force=True, silent=True) or {}
    try:
        conn = _conn_from_json(data)
        wp_root = data.get("wp_root", "")
        if not (conn.host and conn.user and conn.password and wp_root):
            return jsonify({"ok": False, "msg": "host/user/password/wp_root fehlen"}), 400
        return jsonify(fix_rotate_debug_log(conn, wp_root))
    except RepairError as e:
        return jsonify({"ok": False, "msg": str(e)}), 400
    except Exception as e:
        return jsonify({"ok": False, "msg": f"Fix error: {e}"}), 500


@bp.post("/fix/permissions")
def fix_perms():
    data = request.get_json(force=True, silent=True) or {}
    try:
        conn = _conn_from_json(data)
        wp_root = data.get("wp_root", "")
        if not (conn.host and conn.user and conn.password and wp_root):
            return jsonify({"ok": False, "msg": "host/user/password/wp_root fehlen"}), 400
        return jsonify(fix_permissions(conn, wp_root))
    except RepairError as e:
        return jsonify({"ok": False, "msg": str(e)}), 400
    except Exception as e:
        return jsonify({"ok": False, "msg": f"Fix error: {e}"}), 500
