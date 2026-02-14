# app/modules/wp_uploads/cleanup.py
from datetime import datetime, timezone
import os
from app.extensions import db
from app.modules.wp_uploads.models import WpUpload

def cleanup_expired_uploads(base_dir="/var/www/sitefixer/uploads/tickets"):
    now = datetime.now(timezone.utc)
    q = WpUpload.query.filter(
        WpUpload.expires_at.isnot(None),
        WpUpload.expires_at < now,
        WpUpload.deleted_at.is_(None),
    )
    for up in q.all():
        path = os.path.join(base_dir, up.stored_filename)
        try:
            if os.path.exists(path):
                os.remove(path)
        except Exception as e:
            current_app.logger.warning("cleanup error %s: %r", path, e)
        up.deleted_at = now
        db.session.add(up)
    db.session.commit()
