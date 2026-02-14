from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.modules.tickets.schemas import PublicTicketCreateIn, PublicTicketCreateOut, PublicTicketStatusOut
from app.modules.tickets.models import Ticket, TicketScan, TicketAccess
from app.modules.tickets.service import create_public_ticket
from app.modules.scans.service import enqueue_scan

router = APIRouter(prefix="/api/public", tags=["public-tickets"])


@router.post("/tickets", response_model=PublicTicketCreateOut)
def public_create_ticket(payload: PublicTicketCreateIn, db: Session = Depends(get_db)):
    try:
        t = create_public_ticket(db, payload)
        enqueue_scan(db, t.id, "preflight")
        db.commit()
        return PublicTicketCreateOut(public_id=t.public_id, status=t.status)
    except ValueError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        db.rollback()
        raise


@router.get("/tickets/{public_id}/status", response_model=PublicTicketStatusOut)
def public_ticket_status(public_id: str, db: Session = Depends(get_db)):
    t = db.query(Ticket).filter(Ticket.public_id == public_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="ticket not found")

    s = (
        db.query(TicketScan)
        .filter(TicketScan.ticket_id == t.id)
        .order_by(TicketScan.id.desc())
        .first()
    )

    last_summary = None
    if s and s.result_json:
        r = s.result_json
        last_summary = {
            "scan_type": s.scan_type,
            "status_code": r.get("status_code"),
            "final_url": r.get("final_url"),
            "elapsed_ms": r.get("elapsed_ms"),
            "wp_likely": (r.get("wp") or {}).get("is_wordpress_likely"),
        }

    next_action = None
    if t.status == "needs_access":
        next_action = "Bitte Zugangsdaten nachreichen (SFTP oder WP-Admin)."
    elif t.status in ("queued", "scanning"):
        next_action = "Scan läuft / wird verarbeitet."
    elif t.status == "failed":
        next_action = "Ticket prüfen, URL/Erreichbarkeit fehlerhaft."

    return PublicTicketStatusOut(
        public_id=t.public_id,
        status=t.status,
        last_scan_summary=last_summary,
        next_action=next_action,
    )
