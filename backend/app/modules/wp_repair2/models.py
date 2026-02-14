from app.extensions import db

class RepairRun(db.Model):
    __tablename__ = "repair_runs"
    id = db.Column(db.BigInteger, primary_key=True)
    ticket_id = db.Column(db.Integer, nullable=False, index=True)
    actor_user_id = db.Column(db.Integer, nullable=True)
    status = db.Column(db.String(32), nullable=False, default="running")
    kind = db.Column(db.String(32), nullable=False, default="repair")
    root_path = db.Column(db.Text, nullable=True)
    started_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
    finished_at = db.Column(db.DateTime, nullable=True)
    summary_json = db.Column(db.JSON, nullable=True)

class RepairActionLog(db.Model):
    __tablename__ = "repair_action_logs"
    id = db.Column(db.BigInteger, primary_key=True)
    run_id = db.Column(db.BigInteger, db.ForeignKey("repair_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    ticket_id = db.Column(db.Integer, nullable=False, index=True)
    action_key = db.Column(db.String(64), nullable=False)
    status = db.Column(db.String(16), nullable=False)
    message = db.Column(db.Text, nullable=True)
    details_json = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())

class RepairArtifact(db.Model):
    __tablename__ = "repair_artifacts"
    id = db.Column(db.BigInteger, primary_key=True)
    run_id = db.Column(db.BigInteger, db.ForeignKey("repair_runs.id", ondelete="CASCADE"), nullable=False, index=True)
    ticket_id = db.Column(db.Integer, nullable=False, index=True)
    type = db.Column(db.String(32), nullable=False)   # backup, diff, report, log, quarantine
    path = db.Column(db.Text, nullable=False)
    sha256 = db.Column(db.String(64), nullable=True)
    size = db.Column(db.BigInteger, nullable=True)
    meta_json = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, server_default=db.func.now())
