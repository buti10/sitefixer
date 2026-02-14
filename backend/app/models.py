#backend/app/models.py
from datetime import datetime
from sqlalchemy import func
from .extensions import db

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(190), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.Enum('admin','agent','viewer', name='role_enum'), default='agent', nullable=False)
    active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, server_default=func.now(), nullable=False)
    woot_user_id = db.Column(db.Integer, nullable=True)


class RefreshBlocklist(db.Model):
    __tablename__ = 'refresh_blocklist'
    id = db.Column(db.Integer, primary_key=True)
    jti = db.Column(db.String(36), unique=True, index=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Setting(db.Model):
    __tablename__ = "settings"

    # Datenbankspalte heißt 'key', im Python-Code nennen wir sie 'name'
    name = db.Column("key", db.String(100), primary_key=True)
    value = db.Column(db.Text)    