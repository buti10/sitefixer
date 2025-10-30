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

class Setting(db.Model):
    __tablename__ = 'settings'
    key = db.Column(db.String(100), primary_key=True)
    value = db.Column(db.Text, nullable=True)

class RefreshBlocklist(db.Model):
    __tablename__ = 'refresh_blocklist'
    id = db.Column(db.Integer, primary_key=True)
    jti = db.Column(db.String(36), unique=True, index=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

# app/models.py (Ergänzung)


class LhcAccount(db.Model):
    __tablename__ = "lhc_accounts"
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True)
    lhc_operator_id = db.Column(db.Integer, nullable=True)   # falls du Operator-IDs pflegen willst
    lhc_username = db.Column(db.String(120), nullable=True)  # REST- oder LHC-User
    dept_filter = db.Column(db.String(255), nullable=True)   # CSV der LHC-Department-IDs, optional

    user = db.relationship("User", backref=db.backref("lhc_account", uselist=False))
