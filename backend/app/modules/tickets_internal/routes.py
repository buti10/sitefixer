from __future__ import annotations

from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt

from app.extensions import db
from app.modules.tickets_public.models import Ticket, TicketAccess, TicketScan, TicketEvent

bp_tickets_internal = Blueprint("tickets_internal", __name__, url_prefix="/api/tickets")


def _require_role(allowed: set[str]) -> tuple[bool, tuple[dict, int] | None]:
    claims = get_jwt() or {}
    role = (claims.get("role") or "viewer").lower()
    if role not in allowed:
        return False, ({"error": "forbidden"}, 403)
    return True, None


def _ticket_to_dict(t: Ticket) -> dict:
    return {
        "id": t.id,
        "public_id": t.public_id,
        "status": t.status,
        "source": t.source,
        "customer_name": t.customer_name,
        "customer_email": t.customer_email,
        "customer_phone": t.customer_phone,
        "site_url": t.site_url,
        "created_at": t.created_at.isoformat() if getattr(t, "created_at", None) else None,
    }


@bp_tickets_internal.get("")
@jwt_required()
def list_tickets():
    ok, err = _require_role({"admin", "agent", "viewer"})
    if not ok:
        return jsonify(err[0]), err[1]

    status = (request.args.get("status") or "").strip()
    q = (request.args.get("q") or "").strip()

    limit = int(request.args.get("limit") or 50)
    limit = max(1, min(limit, 200))

    query = Ticket.query

    if status:
        query = query.filter(Ticket.status == status)

    if q:
        like = f"%{q}%"
        query = query.filter(
            (Ticket.site_url.like(like)) |
            (Ticket.customer_email.like(like)) |
            (Ticket.customer_name.like(like)) |
            (Ticket.public_id.like(like))
        )

    items = query.order_by(Ticket.id.desc()).limit(limit).all()
    return jsonify({"items": [_ticket_to_dict(t) for t in items]}), 200


@bp_tickets_internal.get("/<int:ticket_id>")
@jwt_required()
def get_ticket(ticket_id: int):
    ok, err = _require_role({"admin", "agent", "viewer"})
    if not ok:
        return jsonify(err[0]), err[1]

    t = db.session.get(Ticket, ticket_id)
    if not t:
        return jsonify({"error": "ticket not found"}), 404

    data = _ticket_to_dict(t)

    # Access: nur für admin/agent anzeigen (keine Passwörter!)
    claims = get_jwt() or {}
    role = (claims.get("role") or "viewer").lower()

    acc = TicketAccess.query.filter_by(ticket_id=t.id).first()
    if role in {"admin", "agent"} and acc:
        data["access"] = {
            "id": acc.id,
            "verified": getattr(acc, "verified", False),
            "sftp_host": acc.sftp_host,
            "sftp_port": acc.sftp_port,
            "sftp_user": acc.sftp_user,
            "wp_admin_user": acc.wp_admin_user,
            "notes": acc.notes,
            "created_at": acc.created_at.isoformat() if getattr(acc, "created_at", None) else None,
        }
    else:
        data["access"] = None

    return jsonify(data), 200


@bp_tickets_internal.get("/<int:ticket_id>/scans")
@jwt_required()
def list_scans(ticket_id: int):
    ok, err = _require_role({"admin", "agent", "viewer"})
    if not ok:
        return jsonify(err[0]), err[1]

    t = db.session.get(Ticket, ticket_id)
    if not t:
        return jsonify({"error": "ticket not found"}), 404

    scans = (
        TicketScan.query
        .filter_by(ticket_id=t.id)
        .order_by(TicketScan.id.desc())
        .limit(100)
        .all()
    )

    items = []
    for s in scans:
        items.append({
            "id": s.id,
            "scan_type": s.scan_type,
            "status": s.status,
            "error_message": s.error_message,
            "created_at": s.created_at.isoformat() if getattr(s, "created_at", None) else None,
            "started_at": s.started_at.isoformat() if getattr(s, "started_at", None) else None,
            "finished_at": s.finished_at.isoformat() if getattr(s, "finished_at", None) else None,
            "result": s.result_json if getattr(s, "result_json", None) else None,
        })

    return jsonify({"ticket_id": t.id, "items": items}), 200


@bp_tickets_internal.get("/<int:ticket_id>/events")
@jwt_required()
def list_events(ticket_id: int):
    ok, err = _require_role({"admin", "agent", "viewer"})
    if not ok:
        return jsonify(err[0]), err[1]

    t = db.session.get(Ticket, ticket_id)
    if not t:
        return jsonify({"error": "ticket not found"}), 404

    evs = (
        TicketEvent.query
        .filter_by(ticket_id=t.id)
        .order_by(TicketEvent.id.desc())
        .limit(200)
        .all()
    )

    items = []
    for e in evs:
        items.append({
            "id": e.id,
            "type": e.type,
            "payload": e.payload_json if getattr(e, "payload_json", None) else None,
            "created_at": e.created_at.isoformat() if getattr(e, "created_at", None) else None,
        })

    return jsonify({"ticket_id": t.id, "items": items}), 200
