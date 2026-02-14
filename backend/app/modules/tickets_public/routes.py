from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from flask import Blueprint, request, jsonify, current_app
from sqlalchemy import desc

from app.extensions import db
from app.core.crypto import encrypt_to_b64

from app.modules.tickets_public.models import Ticket, TicketAccess, TicketScan, TicketEvent


bp_public_tickets = Blueprint("public_tickets", __name__, url_prefix="/api/public")


# ----------------------------
# Helpers
# ----------------------------

def _clean_str(v: Any) -> str:
    return str(v).strip() if v is not None else ""


def _as_int(v: Any, default: int) -> int:
    try:
        return int(v)
    except Exception:
        return default


def _json() -> Dict[str, Any]:
    return request.get_json(silent=True) or {}


def _normalize_site_url(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return ""
    # Wenn kein Schema, default https
    if not (u.startswith("http://") or u.startswith("https://")):
        u = "https://" + u
    return u


def _enqueue_scan(ticket_id: int, scan_type: str = "preflight") -> None:
    db.session.add(TicketScan(ticket_id=ticket_id, scan_type=scan_type, status="queued"))


def _ticket_to_public_response(t: Ticket) -> Dict[str, Any]:
    return {
        "public_id": t.public_id,
        "status": t.status,
    }


# ----------------------------
# Public API
# ----------------------------

@bp_public_tickets.post("/tickets")
def create_ticket():
    """
    Widget: Ticket anlegen + optional Access speichern + Preflight enqueuen.
    Erwartet:
    {
      "site_url": "https://example.com",
      "consent": true,
      "email": "...", "name": "...", "phone": "...",
      "access": {
         "sftp_host": "...", "sftp_port": 22, "sftp_user": "...", "sftp_pass": "...",
         "wp_admin_user": "...", "wp_admin_pass": "...",
         "notes": "..."
      }
    }
    """
    data = _json()

    site_url = _normalize_site_url(_clean_str(data.get("site_url")))
    if not site_url:
        return jsonify({"error": "site_url missing"}), 400

    if data.get("consent") is not True:
        return jsonify({"error": "consent must be true"}), 400

    t = Ticket(
        public_id=str(uuid.uuid4()),
        status="queued",         # dein Worker/Scan-Service kann später auf scanning/done/needs_access/failed setzen
        source="widget",
        customer_email=_clean_str(data.get("email")) or None,
        customer_name=_clean_str(data.get("name")) or None,
        customer_phone=_clean_str(data.get("phone")) or None,
        site_url=site_url,
    )
    db.session.add(t)
    db.session.flush()  # t.id

    # Optional: Access speichern (verschlüsselt)
    access = data.get("access") or None
    if isinstance(access, dict) and access:
        sftp_port = _as_int(access.get("sftp_port"), 22)

        acc = TicketAccess(
            ticket_id=t.id,
            sftp_host=_clean_str(access.get("sftp_host")) or None,
            sftp_port=sftp_port,
            sftp_user=_clean_str(access.get("sftp_user")) or None,
            sftp_pass_enc=encrypt_to_b64(_clean_str(access.get("sftp_pass"))) if _clean_str(access.get("sftp_pass")) else None,
            wp_admin_user=_clean_str(access.get("wp_admin_user")) or None,
            wp_admin_pass_enc=encrypt_to_b64(_clean_str(access.get("wp_admin_pass"))) if _clean_str(access.get("wp_admin_pass")) else None,
            notes=_clean_str(access.get("notes")) or None,
            verified=False,
        )
        db.session.add(acc)

    db.session.add(
        TicketEvent(
            ticket_id=t.id,
            type="ticket_created",
            payload_json={"source": "widget"},
        )
    )

    # Phase 1: Preflight Scan in Queue
    _enqueue_scan(ticket_id=t.id, scan_type="preflight")

    db.session.commit()

    return jsonify(_ticket_to_public_response(t)), 200


@bp_public_tickets.post("/tickets/<public_id>/access")
def update_access(public_id: str):
    """
    Widget: Zugangsdaten nachreichen (wenn Preflight 'needs_access' ergibt).
    Erwartet:
    {
      "access": { ... wie oben ... }
    }
    """
    data = _json()
    access = data.get("access") or None
    if not isinstance(access, dict) or not access:
        return jsonify({"error": "access missing"}), 400

    t = Ticket.query.filter_by(public_id=public_id).first()
    if not t:
        return jsonify({"error": "ticket not found"}), 404

    sftp_port = _as_int(access.get("sftp_port"), 22)

    acc = (TicketAccess.query
       .filter_by(ticket_id=t.id)
       .order_by(desc(TicketAccess.id))
       .first())
    if not acc:
        acc = TicketAccess(ticket_id=t.id)
        db.session.add(acc)

    # Update Felder (nur wenn geliefert)
    if "sftp_host" in access:
        acc.sftp_host = _clean_str(access.get("sftp_host")) or None
    if "sftp_port" in access:
        acc.sftp_port = sftp_port
    if "sftp_user" in access:
        acc.sftp_user = _clean_str(access.get("sftp_user")) or None
    if "sftp_pass" in access:
        pw = _clean_str(access.get("sftp_pass"))
        acc.sftp_pass_enc = encrypt_to_b64(pw) if pw else None

    if "wp_admin_user" in access:
        acc.wp_admin_user = _clean_str(access.get("wp_admin_user")) or None
    if "wp_admin_pass" in access:
        pw = _clean_str(access.get("wp_admin_pass"))
        acc.wp_admin_pass_enc = encrypt_to_b64(pw) if pw else None

    if "notes" in access:
        acc.notes = _clean_str(access.get("notes")) or None

    acc.verified = False

    db.session.add(
        TicketEvent(
            ticket_id=t.id,
            type="access_submitted",
            payload_json={"source": "widget"},
        )
    )

    # Optional: direkt neuen Preflight enqueuen, falls du willst
    # (macht UX gut: Kunde trägt Zugang ein -> Scan startet sofort wieder)
    _enqueue_scan(ticket_id=t.id, scan_type="access_verify")

    # Ticket-Status zurück auf queued (damit UI nicht "needs_access" festhängt)
    t.status = "scanning"

    db.session.commit()
    return jsonify({"ok": True, "public_id": t.public_id, "status": t.status}), 200


@bp_public_tickets.get("/tickets/<public_id>/status")
def ticket_status(public_id: str):
    """
    Widget: Polling Status + letzte Scan-Zusammenfassung.
    """
    t = Ticket.query.filter_by(public_id=public_id).first()
    if not t:
        return jsonify({"error": "ticket not found"}), 404

    s = (
        TicketScan.query.filter_by(ticket_id=t.id)
        .order_by(desc(TicketScan.id))
        .first()
    )

    last_scan_status: Optional[str] = None
    last_summary: Optional[Dict[str, Any]] = None

    if s:
        last_scan_status = s.status
        if s.result_json:
            r = s.result_json or {}
            wp = (r.get("wp") or {}) if isinstance(r.get("wp"), dict) else {}
            last_summary = {
                "scan_type": s.scan_type,
                "status_code": r.get("status_code"),
                "final_url": r.get("final_url"),
                "elapsed_ms": r.get("elapsed_ms"),
                "wp_likely": wp.get("is_wordpress_likely"),
                "notes": r.get("notes") or None,
            }

    # next_action ableiten (Widget-Text)
    next_action = None
    if s:
        if s.status in ("queued", "running"):
            next_action = "Scan läuft / wird verarbeitet."
        elif s.status in ("error", "failed"):
            next_action = "Scan-Fehler. Bitte URL prüfen oder später erneut versuchen."
        elif s.status == "done":
            if t.status == "needs_access":
                next_action = "Bitte Zugangsdaten nachreichen (SFTP oder WP-Admin)."
            elif t.status == "failed":
                next_action = "Ticket prüfen: URL/Erreichbarkeit fehlerhaft."
            else:
                next_action = "Scan abgeschlossen."
    else:
        if t.status in ("queued", "scanning"):
            next_action = "Scan läuft / wird verarbeitet."
        elif t.status == "needs_access":
            next_action = "Bitte Zugangsdaten nachreichen (SFTP oder WP-Admin)."
        elif t.status == "failed":
            next_action = "Ticket prüfen: URL/Erreichbarkeit fehlerhaft."

    return jsonify(
        {
            "public_id": t.public_id,
            "status": t.status,
            "last_scan_status": last_scan_status,
            "last_scan_summary": last_summary,
            "next_action": next_action,
        }
    ), 200
