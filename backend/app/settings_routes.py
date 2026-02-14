# app/settings_routes.py
from flask import Blueprint, jsonify, request
from app.extensions import db
from app.models_extra import Setting

# Eindeutiger Name, damit es keine Kollisionen mit alten Blueprints gibt
bp = Blueprint("sf_settings", __name__)


def _get_setting(name: str, default: str = "") -> str:
    obj = Setting.query.get(name)
    return obj.value if obj else default


def _set_setting(name: str, value: str) -> None:
    obj = Setting.query.get(name)
    if not obj:
        obj = Setting(name=name)
        db.session.add(obj)
    obj.value = value


@bp.get("/api/settings")
def get_settings():
    """
    Liefert alle relevanten Settings fürs Frontend:
    SITE_NAME, SUPPORT_EMAIL, OFFER_MAIL_SUBJECT, OFFER_MAIL_BODY, OFFER_MAIL_SIGNATURE
    """
    data = {
        "SITE_NAME": _get_setting("SITE_NAME", "Sitefixer Scanner"),
        "SUPPORT_EMAIL": _get_setting("SUPPORT_EMAIL", "support@sitefixer.de"),
        "OFFER_MAIL_SUBJECT": _get_setting(
            "OFFER_MAIL_SUBJECT",
            "Ihr Sitefixer-Angebot zu Ticket #{ticket_id}",
        ),
        "OFFER_MAIL_BODY": _get_setting(
            "OFFER_MAIL_BODY",
            (
                "Hallo {customer_name},\n\n"
                "vielen Dank für Ihre Anfrage.\n"
                "hier ist der Zahlungslink zu Ihrem Angebot über {amount} €:\n"
                "{payment_link}\n\n"
                "Mit freundlichen Grüßen,\n"
                "{signature}"
            ),
        ),
        "OFFER_MAIL_SIGNATURE": _get_setting(
            "OFFER_MAIL_SIGNATURE",
            "Sitefixer Support-Team\nsupport@sitefixer.de",
        ),
    }
    return jsonify(data)


@bp.post("/api/settings")
def save_settings():
    """
    Speichert Settings, die vom Frontend gesendet werden.
    Erwartet JSON mit beliebiger Kombination aus:
    SITE_NAME, SUPPORT_EMAIL, OFFER_MAIL_SUBJECT, OFFER_MAIL_BODY, OFFER_MAIL_SIGNATURE
    """
    data = request.get_json() or {}
    allowed_keys = [
        "SITE_NAME",
        "SUPPORT_EMAIL",
        "OFFER_MAIL_SUBJECT",
        "OFFER_MAIL_BODY",
        "OFFER_MAIL_SIGNATURE",
    ]

    for key in allowed_keys:
        if key in data:
            value = data.get(key) or ""
            _set_setting(key, str(value))

    db.session.commit()
    return jsonify({"ok": True})
