from .extensions import db
from sqlalchemy.dialects.mysql import JSON
from datetime import datetime

class RepairSession(db.Model):
    __tablename__ = "repair_sessions"
    id = db.Column(db.Integer, primary_key=True)
    ticket_id = db.Column(db.Integer, index=True, nullable=False)
    sid = db.Column(db.String(64), nullable=False)
    root = db.Column(db.String(1024), nullable=False)
    cms = db.Column(db.String(32))
    cms_version = db.Column(db.String(32))
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    closed_at = db.Column(db.DateTime)

class RepairAction(db.Model):
    __tablename__ = "repair_actions"
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("repair_sessions.id"), index=True, nullable=False)
    kind = db.Column(db.String(40), nullable=False)
    src = db.Column(db.String(2048))
    dst = db.Column(db.String(2048))
    meta = db.Column(JSON)
    success = db.Column(db.Boolean, default=False, nullable=False)
    error_msg = db.Column(db.Text)
    executed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class RepairCheckpoint(db.Model):
    __tablename__ = "repair_checkpoints"
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("repair_sessions.id"), index=True, nullable=False)
    label = db.Column(db.String(80), nullable=False)
    snapshot_dir = db.Column(db.String(2048), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

class RepairLog(db.Model):
    __tablename__ = "repair_logs"
    id = db.Column(db.BigInteger, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey("repair_sessions.id"), index=True, nullable=False)
    level = db.Column(db.Enum("DEBUG","INFO","WARN","ERROR"), default="INFO", nullable=False)
    message = db.Column(db.Text, nullable=False)
    context = db.Column(JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
