from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.modules.tickets.models import TicketScan


def enqueue_scan(db: Session, ticket_id: int, scan_type: str) -> int:
    existing = (
        db.query(TicketScan)
        .filter(
            and_(
                TicketScan.ticket_id == ticket_id,
                TicketScan.scan_type == scan_type,
                TicketScan.status.in_(["queued","running"]),
            )
        )
        .order_by(TicketScan.id.desc())
        .first()
    )
    if existing:
        return int(existing.id)

    s = TicketScan(ticket_id=ticket_id, scan_type=scan_type, status="queued")
    db.add(s)
    db.flush()
    return int(s.id)
