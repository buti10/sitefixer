from datetime import datetime
from .extensions import db

class Scan(db.Model):
    __tablename__ = "scans"
    id         = db.Column(db.String(36), primary_key=True)  # UUID
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=True, onupdate=datetime.utcnow)

    user_id    = db.Column(db.Integer)
    sid        = db.Column(db.String(128))
    root       = db.Column(db.String(1024))
    patterns   = db.Column(db.Text)          # JSON-String
    status     = db.Column(db.String(16), default="queued")
    progress   = db.Column(db.Integer, default=0)
    max_score  = db.Column(db.Integer)
    ticket_id  = db.Column(db.Integer)

class Finding(db.Model):
    __tablename__ = "findings"
    id        = db.Column(db.Integer, primary_key=True)
    scan_id   = db.Column(db.String(36), db.ForeignKey("scans.id"), index=True, nullable=False)
    path      = db.Column(db.Text)
    rule      = db.Column(db.String(255))
    severity  = db.Column(db.String(16))     # malicious|suspicious|clean
    line      = db.Column(db.Integer)
    snippet   = db.Column(db.Text)
    created_at= db.Column(db.DateTime, default=datetime.utcnow)
