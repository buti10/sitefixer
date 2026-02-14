# app/models_extra.py
from datetime import datetime
from app.extensions import db
from app.models import User
from sqlalchemy import func

class CustomerPSA(db.Model):
    __tablename__ = "customer_psa"

    id          = db.Column(db.Integer, primary_key=True)
    email       = db.Column(db.String(255), unique=True, nullable=False)
    psa_user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    created_at  = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at  = db.Column(db.DateTime, default=datetime.utcnow,
                            onupdate=datetime.utcnow, nullable=False)


class TicketNote(db.Model):
    __tablename__ = "ticket_notes"

    id         = db.Column(db.Integer, primary_key=True)
    ticket_id  = db.Column(db.Integer, nullable=False)
    author_id  = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    text       = db.Column(db.Text, nullable=False)
    remind_at  = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class TicketMeta(db.Model):
    __tablename__ = "ticket_meta"

    id              = db.Column(db.Integer, primary_key=True)
    ticket_id       = db.Column(db.Integer, unique=True, nullable=False)
    offer_amount    = db.Column(db.Numeric(10, 2))
    payment_link    = db.Column(db.Text)
    status_override = db.Column(db.String(32))
    last_admin      = db.Column(db.String(64))
    product_id      = db.Column(db.Integer)
    updated_at      = db.Column(db.DateTime, default=datetime.utcnow,
                                onupdate=datetime.utcnow, nullable=False)


class WootConversationLog(db.Model):
    __tablename__ = "woot_conversation_log"

    id = db.Column(db.Integer, primary_key=True)
    cw_conversation_id = db.Column(db.Integer, nullable=False, unique=True)
    cw_contact_id = db.Column(db.Integer)
    email = db.Column(db.String(255))
    referer = db.Column(db.Text)
    initiated_at = db.Column(db.DateTime)
    psa_user_id = db.Column(db.Integer)
    assigned_user_id = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, server_default=func.now(), nullable=False)
    updated_at = db.Column(
        db.DateTime, server_default=func.now(), onupdate=func.now(), nullable=False
    )
    browser_name = db.Column(db.String(64))
    platform_name = db.Column(db.String(64))
    browser_version = db.Column(db.String(32))
    platform_version = db.Column(db.String(32))
    browser_language = db.Column(db.String(16))
    channel = db.Column(db.String(64))

class WootConversationOrigin(db.Model):
    __tablename__ = "woot_conversation_origins"

    id = db.Column(db.Integer, primary_key=True)
    cw_conversation_id = db.Column(db.Integer, nullable=True)
    page = db.Column(db.String(512), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)



class Setting(db.Model):
    __tablename__ = "settings"
    __table_args__ = {"extend_existing": True}  # wichtig, falls es bereits ein Table-Objekt gibt

    # In der DB heißt die Spalte 'key', im ORM nennen wir sie 'name'
    name = db.Column("key", db.String(100), primary_key=True)
    value = db.Column(db.Text)


