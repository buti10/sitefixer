# create_wp_uploads_table.py
from app import create_app, db

app = create_app()

with app.app_context():
    from app.modules.wp_uploads.models import TicketUpload
    print("Creating tables (only missing ones)…")
    db.create_all()
    print("Done.")
