# app/modules/wp_uploads/models.py
from datetime import datetime
from typing import Optional

from app import db  # falls du db anders importierst, anpassen


class TicketUpload(db.Model):
    __tablename__ = "ticket_uploads"

    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, index=True, nullable=False)

    # Zuordnung zum WP-User / Kunden
    wp_user_id = db.Column(db.Integer, index=True, nullable=True)
    customer_email = db.Column(db.String(255), index=True, nullable=True)

    original_filename = db.Column(db.String(255), nullable=False)
    stored_filename = db.Column(db.String(255), nullable=False)
    mime_type = db.Column(db.String(100), nullable=True)
    file_size = db.Column(db.Integer, nullable=True)

    description = db.Column(db.Text, nullable=True)
    target_page = db.Column(db.String(255), nullable=True)       # z.B. "Startseite", "/leistungen"
    target_section = db.Column(db.String(255), nullable=True)    # z.B. "Hero", "Team", "Footer"
    style_json = db.Column(db.JSON, nullable=True)               # {"color": "#ff6600", "size": "large"}

    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(
        db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False
    )

    # Automatische Löschung (z. B. 7 Tage nach Ticket-Schließung)
    expires_at = db.Column(db.DateTime, nullable=True)
    deleted_at = db.Column(db.DateTime, nullable=True)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "ticket_id": self.ticket_id,
            "wp_user_id": self.wp_user_id,
            "customer_email": self.customer_email,
            "original_filename": self.original_filename,
            "stored_filename": self.stored_filename,
            "mime_type": self.mime_type,
            "file_size": self.file_size,
            "description": self.description,
            "target_page": self.target_page,
            "target_section": self.target_section,
            "style": self.style_json or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "deleted_at": self.deleted_at.isoformat() if self.deleted_at else None,
        }
