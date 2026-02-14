from sqlalchemy import (
    Column, BigInteger, String, Text, Boolean, Integer, DateTime, ForeignKey
)
from sqlalchemy.dialects.mysql import JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.core.database import Base


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    public_id = Column(String(36), unique=True, nullable=False)

    status = Column(String(32), nullable=False, default="new")
    source = Column(String(32), nullable=False, default="widget")

    customer_email = Column(String(255), nullable=True)
    customer_name = Column(String(255), nullable=True)
    customer_phone = Column(String(64), nullable=True)

    site_url = Column(Text, nullable=False)
    cms_hint = Column(String(64), nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    access = relationship("TicketAccess", uselist=False, back_populates="ticket", cascade="all, delete-orphan")
    scans = relationship("TicketScan", back_populates="ticket", cascade="all, delete-orphan")
    events = relationship("TicketEvent", back_populates="ticket", cascade="all, delete-orphan")


class TicketAccess(Base):
    __tablename__ = "ticket_access"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ticket_id = Column(BigInteger, ForeignKey("tickets.id", ondelete="CASCADE"), unique=True, nullable=False)

    sftp_host = Column(String(255), nullable=True)
    sftp_port = Column(Integer, nullable=True)
    sftp_user = Column(String(255), nullable=True)
    sftp_pass_enc = Column(String(4096), nullable=True)

    wp_admin_user = Column(String(255), nullable=True)
    wp_admin_pass_enc = Column(String(4096), nullable=True)

    notes = Column(Text, nullable=True)
    verified = Column(Boolean, nullable=False, default=False)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    ticket = relationship("Ticket", back_populates="access")


class TicketScan(Base):
    __tablename__ = "ticket_scans"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ticket_id = Column(BigInteger, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False)

    scan_type = Column(String(32), nullable=False)
    status = Column(String(32), nullable=False, default="queued")

    result_json = Column(JSON, nullable=True)
    error_message = Column(Text, nullable=True)

    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    ticket = relationship("Ticket", back_populates="scans")


class TicketEvent(Base):
    __tablename__ = "ticket_events"

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    ticket_id = Column(BigInteger, ForeignKey("tickets.id", ondelete="CASCADE"), nullable=False)

    type = Column(String(64), nullable=False)
    payload_json = Column(JSON, nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    ticket = relationship("Ticket", back_populates="events")
