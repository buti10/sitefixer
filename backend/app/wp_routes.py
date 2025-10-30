# app/wp_routes.py
from flask import Blueprint, jsonify, request, current_app
from .decorators import jwt_required          # dein existierender JWT-Decorator
from .wp_bridge import get_wp_tickets_range, get_kundendetails

bp = Blueprint("wp", __name__, url_prefix="/api/wp")

@bp.get("/tickets")
@jwt_required
def tickets_list():
    try:
        start = request.args.get("start") or None
        end   = request.args.get("end") or None
        return jsonify(get_wp_tickets_range(start, end))
    except Exception as e:
        current_app.logger.exception("WP tickets failed")
        return jsonify({"msg": f"WP tickets failed: {e}"}), 500

@bp.get("/tickets/<int:ticket_id>")
@jwt_required
def ticket_detail(ticket_id: int):
    try:
        return jsonify(get_kundendetails(ticket_id))
    except Exception as e:
        current_app.logger.exception("WP ticket detail failed")
        return jsonify({"msg": f"WP ticket detail failed: {e}"}), 500
