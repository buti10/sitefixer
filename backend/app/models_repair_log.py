from app.extensions import db
from sqlalchemy.dialects.postgresql import JSONB  # oder JSON für MySQL/SQLite

class RepairActionLog(db.Model):
    __tablename__ = "repair_action_log"
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, index=True, nullable=False)
    actor = db.Column(db.String(64), default="system", nullable=False)
    action = db.Column(db.String(64), nullable=False)
    payload = db.Column(JSONB, nullable=False)
    status = db.Column(db.String(16), default="ok")
    duration_ms = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

class RepairFinding(db.Model):
    __tablename__ = "repair_findings"
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, index=True, nullable=False)
    code = db.Column(db.String(64), nullable=False)
    path = db.Column(db.Text)
    severity = db.Column(db.String(16), default="info")
    data = db.Column(JSONB)
    created_at = db.Column(db.DateTime, server_default=db.func.now())

class RepairArtifact(db.Model):
    __tablename__ = "repair_artifacts"
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, index=True, nullable=False)
    kind = db.Column(db.String(32), nullable=False)  # "backup"|"diff"|"report"
    path = db.Column(db.Text, nullable=False)
    sha256 = db.Column(db.String(64))
    bytes = db.Column(db.BigInteger)
    created_at = db.Column(db.DateTime, server_default=db.func.now())
