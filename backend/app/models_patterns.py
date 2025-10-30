from app.extensions import db

class ScanPattern(db.Model):
    __tablename__ = "scan_patterns"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    engine = db.Column(db.Enum('regex','filename'), nullable=False)
    pattern = db.Column(db.Text, nullable=False)
    enabled = db.Column(db.Boolean, default=True)
    meta = db.Column(db.JSON, nullable=True)
    source = db.Column(db.String(128), nullable=True)
