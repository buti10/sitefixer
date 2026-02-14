# app/modules/cooms_visitors/models.py

from app.extensions import db
from datetime import datetime


class LiveVisitor(db.Model):
    __tablename__ = "live_visitors"

    id = db.Column(db.BigInteger, primary_key=True)
    site = db.Column(db.String(50), nullable=False)
    session_id = db.Column(db.String(64), nullable=False)

    first_seen = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    last_seen = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    url = db.Column(db.Text, nullable=False)
    referrer = db.Column(db.Text)
    user_agent = db.Column(db.Text)

    ip = db.Column(db.String(45))
    country_code = db.Column(db.String(2))
    city = db.Column(db.String(100))

    # desktop / mobile / tablet / bot / other
    device_type = db.Column(db.String(16))

    extra = db.Column(db.Text)

    def as_dict(self):
        return {
            "session_id": self.session_id,
            "site": self.site,
            "url": self.url,
            "referrer": self.referrer,
            "user_agent": self.user_agent,
            "ip": self.ip,
            "country_code": self.country_code,
            "city": self.city,
            "device_type": self.device_type,
            "first_seen": self.first_seen.isoformat() if self.first_seen else None,
            "last_seen": self.last_seen.isoformat() if self.last_seen else None,
        }
