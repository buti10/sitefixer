import time
import requests
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.modules.tickets.models import Ticket, TicketScan, TicketAccess, TicketEvent
from app.modules.tickets.service import set_ticket_status


def _wp_heuristics(text: str, final_url: str, headers: dict):
    t = (text or "").lower()
    hints = {
        "wp_content": "wp-content" in t,
        "wp_includes": "wp-includes" in t,
        "wp_json": "/wp-json" in t,
        "generator_wp": ("name=\"generator\"" in t and "wordpress" in t),
    }
    hints["is_wordpress_likely"] = any([hints["wp_content"], hints["wp_includes"], hints["wp_json"], hints["generator_wp"]])
    hints["final_url"] = final_url
    return hints


def _claim_next(db: Session) -> TicketScan | None:
    scan = (
        db.query(TicketScan)
        .filter(TicketScan.scan_type == "preflight", TicketScan.status == "queued")
        .order_by(TicketScan.id.asc())
        .first()
    )
    if not scan:
        return None

    scan.status = "running"
    scan.started_at = datetime.utcnow()
    db.flush()
    return scan


def run_forever(poll_seconds: float = 1.0):
    sess = requests.Session()
    sess.headers.update({"User-Agent": "SitefixerPreflight/1.0"})

    while True:
        db = SessionLocal()
        try:
            scan = _claim_next(db)
            if not scan:
                db.commit()
                time.sleep(poll_seconds)
                continue

            ticket = db.query(Ticket).filter(Ticket.id == scan.ticket_id).first()
            if not ticket:
                scan.status = "error"
                scan.error_message = "ticket not found"
                scan.finished_at = datetime.utcnow()
                db.commit()
                continue

            try:
                set_ticket_status(db, ticket.id, "scanning")

                start = time.time()
                r = sess.get(ticket.site_url, allow_redirects=True, timeout=(10, 20))
                elapsed_ms = int((time.time() - start) * 1000)

                result = {
                    "requested_url": ticket.site_url,
                    "final_url": str(r.url),
                    "status_code": int(r.status_code),
                    "elapsed_ms": elapsed_ms,
                    "redirect_count": len(r.history),
                    "redirect_chain": [{"status": h.status_code, "url": str(h.url)} for h in r.history] + [{"status": r.status_code, "url": str(r.url)}],
                    "headers": {
                        "server": r.headers.get("Server"),
                        "content_type": r.headers.get("Content-Type"),
                        "cache_control": r.headers.get("Cache-Control"),
                        "content_security_policy": r.headers.get("Content-Security-Policy"),
                        "strict_transport_security": r.headers.get("Strict-Transport-Security"),
                    },
                    "wp": _wp_heuristics(r.text[:200000], str(r.url), dict(r.headers)),
                }

                scan.status = "done"
                scan.result_json = result
                scan.finished_at = datetime.utcnow()

                # needs_access rule (Phase 1)
                wp_likely = (result.get("wp") or {}).get("is_wordpress_likely")
                has_access = db.query(TicketAccess).filter(TicketAccess.ticket_id == ticket.id).first() is not None

                if r.status_code >= 400:
                    ticket.status = "failed"
                else:
                    if wp_likely and not has_access:
                        ticket.status = "needs_access"
                    else:
                        ticket.status = "queued"

                db.add(TicketEvent(ticket_id=ticket.id, type="scan_done", payload_json={"scan_type":"preflight"}))
                db.commit()

            except Exception as e:
                scan.status = "error"
                scan.error_message = str(e)
                scan.finished_at = datetime.utcnow()
                ticket.status = "failed"
                db.add(TicketEvent(ticket_id=ticket.id, type="scan_error", payload_json={"scan_type":"preflight","error":str(e)}))
                db.commit()

        finally:
            db.close()
