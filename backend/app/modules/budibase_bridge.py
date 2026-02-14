# /var/www/sitefixer/backend/app/modules/budibase_bridge.py
from __future__ import annotations

from flask import Blueprint, request, jsonify, abort, current_app

# WICHTIG: Import aus deiner Datei wp_bridge.py
from app.wp_bridge import get_wp_tickets_range, get_kundendetails


bp = Blueprint("budibase", __name__, url_prefix="/api/budibase")


def _require_budibase_key() -> None:
    """
    Erwartet:
      Authorization: Bearer <BUDIBASE_API_KEY>
    """
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        abort(401, description="Missing bearer token")

    token = auth.split(" ", 1)[1].strip()
    expected = (current_app.config.get("BUDIBASE_API_KEY") or "").strip()

    if not expected or token != expected:
        abort(401, description="Invalid bearer token")


@bp.get("/health")
def health():
    _require_budibase_key()
    return jsonify({"ok": True})


@bp.post("/tickets/list")
def tickets_list():
    """
    Body:
      {
        "start": "2025-01-01" (optional),
        "end":   "2026-01-31" (optional),
        "limit": 200 (optional),
        "only_mine": true/false (optional),
        "handler": "Administrator" (optional)
      }

    Hinweis:
    - Deine get_wp_tickets_range() hat intern LIMIT 1000.
    - limit hier schneidet nur das Ergebnis nachträglich ab.
    """
    _require_budibase_key()
    body = request.get_json(silent=True) or {}

    start = body.get("start")  # "YYYY-MM-DD" oder ISO
    end = body.get("end")
    limit = int(body.get("limit", 200))

    only_mine = bool(body.get("only_mine", False))
    handler = body.get("handler")  # z.B. "Administrator" oder user-email/name

    items = get_wp_tickets_range(start, end)  # list[dict] mit ticket_id, name, email, domain, status, prio, handler, created_at ...

    # Optionaler Filter: nur Tickets vom Bearbeiter (scanner_handler)
    if only_mine and handler:
        items = [t for t in items if (t.get("handler") or "").strip() == str(handler).strip()]

    # limit anwenden
    if limit > 0:
        items = items[:limit]

    return jsonify({"ok": True, "data": items, "meta": {"count": len(items)}})


@bp.get("/tickets/<int:ticket_id>")
def ticket_detail(ticket_id: int):
    _require_budibase_key()
    data = get_kundendetails(ticket_id)
    return jsonify({"ok": True, "data": data})
