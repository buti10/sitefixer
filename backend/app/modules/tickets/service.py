import uuid
from sqlalchemy.orm import Session

from app.modules.tickets.models import Ticket, TicketAccess, TicketEvent
from app.core.crypto import encrypt_to_b64


def create_public_ticket(db: Session, payload) -> Ticket:
    if payload.consent is not True:
        raise ValueError("consent must be true")

    t = Ticket(
        public_id=str(uuid.uuid4()),
        status="queued",
        source="widget",
        customer_email=payload.email,
        customer_name=payload.name,
        customer_phone=payload.phone,
        site_url=str(payload.site_url),
    )
    db.add(t)
    db.flush()  # t.id

    if payload.access:
        acc = TicketAccess(
            ticket_id=t.id,
            sftp_host=payload.access.sftp_host,
            sftp_port=payload.access.sftp_port,
            sftp_user=payload.access.sftp_user,
            sftp_pass_enc=encrypt_to_b64(payload.access.sftp_pass),
            wp_admin_user=payload.access.wp_admin_user,
            wp_admin_pass_enc=encrypt_to_b64(payload.access.wp_admin_pass),
            notes=payload.access.notes,
            verified=False,
        )
        db.add(acc)

    db.add(TicketEvent(ticket_id=t.id, type="ticket_created", payload_json={"source":"widget"}))
    return t


def set_ticket_status(db: Session, ticket_id: int, status: str) -> None:
    db.query(Ticket).filter(Ticket.id == ticket_id).update({"status": status})
