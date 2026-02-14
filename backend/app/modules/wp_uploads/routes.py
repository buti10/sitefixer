# app/modules/wp_uploads/routes.py
import os
from datetime import datetime
from pathlib import Path

from flask import (
    Blueprint,
    current_app,
    jsonify,
    request,
    send_from_directory,
    abort,
)
from werkzeug.utils import secure_filename

from app import db
from .models import TicketUpload

bp_wp_uploads = Blueprint(
    "wp_uploads",
    __name__,
    url_prefix="/api/wp/tickets",
)


# ---- Hilfen ----

def _uploads_base_dir() -> Path:
    base = current_app.config.get("UPLOAD_TICKETS_DIR")
    if not base:
        base = "/var/www/sitefixer/uploads/tickets"
    return Path(base)


def _ticket_dir(ticket_id: int) -> Path:
    base = _uploads_base_dir()
    return base / str(ticket_id)


def _allowed_file(filename: str) -> bool:
    # einfache Whitelist, bei Bedarf erweitern
    allowed_ext = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".pdf", ".zip"}
    ext = os.path.splitext(filename)[1].lower()
    return ext in allowed_ext


# ---- Endpoints ----

@bp_wp_uploads.route("/<int:ticket_id>/uploads", methods=["GET"])
def list_uploads(ticket_id: int):
    """
    Liste aller Uploads für ein Ticket.
    Wird vom WordPress-Explorer (Frontend) und vom Scanner-UI genutzt.
    """
    # TODO: Auth / Ticket-Berechtigung prüfen
    q = (
        TicketUpload.query.filter_by(ticket_id=ticket_id, deleted_at=None)
        .order_by(TicketUpload.created_at.asc())
    )
    items = [u.to_dict() for u in q.all()]
    return jsonify({"ok": True, "items": items})


@bp_wp_uploads.route("/<int:ticket_id>/uploads", methods=["POST"])
def create_upload(ticket_id: int):
    """
    Neuen Upload anlegen (Datei + Metadaten).
    Erwartet multipart/form-data.
    """
    # TODO: Auth / Ticket-Berechtigung prüfen

    if "file" not in request.files:
        return jsonify({"ok": False, "error": "file missing"}), 400

    file = request.files["file"]
    if file.filename == "":
        return jsonify({"ok": False, "error": "empty filename"}), 400

    filename = secure_filename(file.filename)
    if not _allowed_file(filename):
        return jsonify({"ok": False, "error": "file type not allowed"}), 400

    # Metadaten aus form-data
    description = request.form.get("description") or ""
    target_page = request.form.get("target_page") or ""
    target_section = request.form.get("target_section") or ""
    color = request.form.get("color") or ""
    size = request.form.get("size") or ""
    wp_user_id = request.form.get("wp_user_id")
    customer_email = request.form.get("customer_email")

    # style_json bauen
    style_json = {}
    if color:
        style_json["color"] = color
    if size:
        style_json["size"] = size

    # Upload-Ordner vorbereiten
    ticket_path = _ticket_dir(ticket_id)
    ticket_path.mkdir(parents=True, exist_ok=True)

    # eindeutiger Dateiname
    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%S%f")
    stored_filename = f"{ticket_id}_{ts}_{filename}"
    full_path = ticket_path / stored_filename

    file.save(full_path)
    file_size = full_path.stat().st_size
    mime_type = file.mimetype

    upload = TicketUpload(
        ticket_id=ticket_id,
        wp_user_id=int(wp_user_id) if wp_user_id else None,
        customer_email=customer_email or None,
        original_filename=filename,
        stored_filename=stored_filename,
        mime_type=mime_type,
        file_size=file_size,
        description=description or None,
        target_page=target_page or None,
        target_section=target_section or None,
        style_json=style_json or None,
        # expires_at wird später beim Ticket-Schließen gesetzt
    )

    db.session.add(upload)
    db.session.commit()

    return jsonify({"ok": True, "item": upload.to_dict()}), 201


@bp_wp_uploads.route(
    "/<int:ticket_id>/uploads/<int:upload_id>", methods=["PATCH", "PUT"]
)
def update_upload(ticket_id: int, upload_id: int):
    """
    Metadaten bearbeiten (Beschreibung, Zielseite, Bereich, Style).
    Wird vom Explorer-UI genutzt.
    """
    # TODO: Auth / Ticket-Berechtigung prüfen

    upload = TicketUpload.query.filter_by(
        id=upload_id, ticket_id=ticket_id, deleted_at=None
    ).first()

    if not upload:
        return jsonify({"ok": False, "error": "not found"}), 404

    data = request.get_json(silent=True) or {}

    if "description" in data:
        upload.description = data["description"] or None
    if "target_page" in data:
        upload.target_page = data["target_page"] or None
    if "target_section" in data:
        upload.target_section = data["target_section"] or None

    # Style-Feld
    style = upload.style_json or {}
    if "color" in data:
        if data["color"]:
            style["color"] = data["color"]
        else:
            style.pop("color", None)
    if "size" in data:
        if data["size"]:
            style["size"] = data["size"]
        else:
            style.pop("size", None)

    upload.style_json = style or None

    db.session.commit()
    return jsonify({"ok": True, "item": upload.to_dict()})


@bp_wp_uploads.route(
    "/<int:ticket_id>/uploads/<int:upload_id>", methods=["DELETE"]
)
def delete_upload(ticket_id: int, upload_id: int):
    """
    Upload manuell löschen (Datei + DB-Markierung).
    Optional für Kunden oder nur intern.
    """
    # TODO: Auth / Ticket-Berechtigung prüfen

    upload = TicketUpload.query.filter_by(
        id=upload_id, ticket_id=ticket_id, deleted_at=None
    ).first()

    if not upload:
        return jsonify({"ok": False, "error": "not found"}), 404

    # Datei löschen, falls vorhanden
    ticket_path = _ticket_dir(ticket_id)
    full_path = ticket_path / upload.stored_filename
    if full_path.exists():
        try:
            full_path.unlink()
        except Exception:
            # nicht kritisch – DB-Markierung trotzdem setzen
            pass

    upload.deleted_at = datetime.utcnow()
    db.session.commit()
    return jsonify({"ok": True})


@bp_wp_uploads.route(
    "/<int:ticket_id>/uploads/<int:upload_id>/download", methods=["GET"]
)
def download_upload(ticket_id: int, upload_id: int):
    """
    Geschützter Download-Endpoint.
    Wird vom Scanner-UI und ggf. vom WP-Kundenbereich genutzt.
    """
    # TODO: Auth / Ticket-Berechtigung prüfen

    upload = TicketUpload.query.filter_by(
        id=upload_id, ticket_id=ticket_id, deleted_at=None
    ).first()

    if not upload:
        abort(404)

    ticket_path = _ticket_dir(ticket_id)
    full_path = ticket_path / upload.stored_filename
    if not full_path.exists():
        abort(404)

    return send_from_directory(
        ticket_path,
        upload.stored_filename,
        as_attachment=True,
        download_name=upload.original_filename,
    )
