from __future__ import annotations
from sqlalchemy.sql import func
from sqlalchemy.dialects.mysql import JSON

from app.extensions import db


class Ticket(db.Model):
    __tablename__ = "tickets"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    public_id = db.Column(db.String(36), unique=True, nullable=False)

    status = db.Column(db.String(32), nullable=False, default="new")
    source = db.Column(db.String(32), nullable=False, default="widget")

    customer_email = db.Column(db.String(255), nullable=True)
    customer_name = db.Column(db.String(255), nullable=True)
    customer_phone = db.Column(db.String(64), nullable=True)

    site_url = db.Column(db.Text, nullable=False)
    cms_hint = db.Column(db.String(64), nullable=True)

    created_at = db.Column(db.DateTime, server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class TicketAccess(db.Model):
    __tablename__ = "ticket_access"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    ticket_id = db.Column(db.BigInteger, db.ForeignKey("tickets.id", ondelete="CASCADE"), unique=True, nullable=False)

    sftp_host = db.Column(db.String(255), nullable=True)
    sftp_port = db.Column(db.Integer, nullable=True)
    sftp_user = db.Column(db.String(255), nullable=True)
    sftp_pass_enc = db.Column(db.String(4096), nullable=True)

    wp_admin_user = db.Column(db.String(255), nullable=True)
    wp_admin_pass_enc = db.Column(db.String(4096), nullable=True)

    notes = db.Column(db.Text, nullable=True)
    verified = db.Column(db.Boolean, nullable=False, default=False)

    created_at = db.Column(db.DateTime, server_default=func.now(), nullable=False)
    updated_at = db.Column(db.DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)


class TicketScan(db.Model):
    __tablename__ = "ticket_scans"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    ticket_id = db.Column(db.BigInteger, db.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False)

    scan_type = db.Column(db.String(32), nullable=False)
    status = db.Column(db.String(32), nullable=False, default="queued")

    result_json = db.Column(JSON, nullable=True)
    error_message = db.Column(db.Text, nullable=True)

    started_at = db.Column(db.DateTime, nullable=True)
    finished_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, server_default=func.now(), nullable=False)


class TicketEvent(db.Model):
    __tablename__ = "ticket_events"

    id = db.Column(db.BigInteger, primary_key=True, autoincrement=True)
    ticket_id = db.Column(db.BigInteger, db.ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False)

    type = db.Column(db.String(64), nullable=False)
    payload_json = db.Column(JSON, nullable=True)

    created_at = db.Column(db.DateTime, server_default=func.now(), nullable=False)
