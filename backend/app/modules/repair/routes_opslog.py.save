# app/modules/repair/routes_opslog.py
import os, json
from flask import Blueprint, jsonify, request, current_app
from app.decorators import jwt_required

bp_opslog = Blueprint("repair_opslog", __name__, url_prefix="/api/repair")


def _log_dir() -> str:
    d = current_app.config.get("OPS_LOG_DIR", "/var/www/sitefixer/ops-logs")
    os.makedirs(d, exist_ok=True)
    return d


@bp_opslog.get("/opslog")
@jwt_required
def get_opslog():
    # Frontend kann session_id als Query senden
    session_id = request.args.get("session_id", type=int)
    limit = request.args.get("limit", default=200, type=int)

    if not session_id:
        # Für UI: lieber leere Liste als 400 (damit nichts crasht)
        return jsonify([])

    path = os.path.join(_log_dir(), f"session-{session_id}.jsonl")
    if not os.path.exists(path):
        return jsonify([])

    # letzte N Zeilen lesen
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.read().splitlines()
        lines = lines[-max(1, min(limit, 2000)):]
        out = []
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except Exception:
                # kaputte Zeile ignorieren
                continue
        return jsonify(out)
    except Exception as e:
        current_app.logger.exception("opslog read failed")
        return jsonify({"msg": f"opslog read failed: {e}"}), 500
