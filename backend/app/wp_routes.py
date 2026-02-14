# app/wp_routes.py
import smtplib
from email.message import EmailMessage
from flask import Blueprint, jsonify, request, current_app, g
from sqlalchemy import func
from flask_jwt_extended import get_jwt_identity
from app.models_extra import CustomerPSA, TicketMeta, TicketNote, Setting
from email.mime.text import MIMEText


from .decorators import jwt_required
from .wp_bridge import (
    get_wp_tickets_range,
    get_kundendetails,
    get_wp_products,
    _cfg,
    _conn,
    set_wp_status,          
    _normalize_status,
)

from app.extensions import db
from app.models import User
from app.models_extra import CustomerPSA, TicketMeta, TicketNote

bp = Blueprint("wp", __name__, url_prefix="/api/wp")


# ---------------------------------------------------------------------------
# Helper: aktuelle User-ID aus g
# ---------------------------------------------------------------------------

def _current_user_id():
    """
    Ermittelt die aktuelle User-ID.
    Reihenfolge:
      - g.current_user.id
      - g.user.id
      - g.user_id
      - JWT-Identity (flask_jwt_extended)
    """
    u = getattr(g, "current_user", None)
    if getattr(u, "id", None):
        return int(u.id)

    u2 = getattr(g, "user", None)
    if getattr(u2, "id", None):
        return int(u2.id)

    if getattr(g, "user_id", None):
        return int(g.user_id)

    try:
        ident = get_jwt_identity()
        if ident is None:
            return None
        # Identity kann int, str oder dict sein
        if isinstance(ident, dict):
            if "id" in ident:
                return int(ident["id"])
        else:
            return int(ident)
    except Exception:
        pass

    current_app.logger.warning("wp_routes._current_user_id: keine User-ID gefunden")
    return None



# ---------------------------------------------------------------------------
# Tickets-Liste
# ---------------------------------------------------------------------------

@bp.get("/tickets")
@jwt_required
def tickets_list():
    try:
        start = request.args.get("start") or None
        end = request.args.get("end") or None
        return jsonify(get_wp_tickets_range(start, end))
    except Exception as e:
        current_app.logger.exception("WP tickets failed")
        return jsonify({"msg": f"WP tickets failed: {e}"}), 500


# ---------------------------------------------------------------------------
# Ticket-Details: WP-Basisdaten + PSA + TicketMeta
# ---------------------------------------------------------------------------

@bp.get("/tickets/<int:ticket_id>")
@jwt_required
def ticket_detail(ticket_id: int):
    try:
        base = get_kundendetails(ticket_id) or {}
        if not base:
            return jsonify({"msg": "Ticket nicht gefunden"}), 404

        # E-Mail aus Ticket normalisieren
        raw_email = base.get("email") or ""
        email = raw_email.strip().lower()

        # Debug-Struktur vorbereiten
        psa_debug = {
            "email_from_ticket": raw_email,
            "email_normalized": email,
            "found": False,
            "psa_user_id": None,
            "psa_user_name": None,
        }

        # TicketMeta (Angebot/Zahlungslink/Status-Override)
        meta = TicketMeta.query.filter_by(ticket_id=ticket_id).first()
        if meta:
            if meta.offer_amount is not None:
                base["angebot"] = float(meta.offer_amount)
            if meta.payment_link:
                base["payment_link"] = meta.payment_link
                base["stripe"] = meta.payment_link
            if meta.status_override:
                base["status"] = meta.status_override

        # PSA (aus customer_psa per E-Mail)
        if email:
            psa = CustomerPSA.query.filter_by(email=email).first()
            if psa:
                psa_debug["found"] = True
                psa_debug["psa_user_id"] = psa.psa_user_id

                u = User.query.get(psa.psa_user_id)
                if u:
                    name = u.name or u.email
                    psa_debug["psa_user_name"] = name
                    base["psa_id"] = psa.psa_user_id
                    base["psa_name"] = name

        # Debug-Daten mit ausgeben (kannst du später wieder entfernen)
        base["psa_debug"] = psa_debug

        return jsonify(base)
    except Exception as e:
        current_app.logger.exception("WP ticket detail failed")
        return jsonify({"msg": f"WP ticket detail failed: {e}"}), 500




# ---------------------------------------------------------------------------
# Supporter-Liste (für PSA-Dropdown)
# ---------------------------------------------------------------------------

@bp.get("/supporters")
@jwt_required
def supporters_list():
    q = User.query.order_by(User.id)
    supporters = q.all()

    out = []
    for u in supporters:
        out.append(
            {
                "id": u.id,
                "name": u.name or u.email,   # <--- hier
                "email": u.email,
            }
        )
    return jsonify(out)



# ---------------------------------------------------------------------------
# PSA-Zuordnung speichern (E-Mail -> PSA-User im Scanner)
# ---------------------------------------------------------------------------

@bp.post("/tickets/<int:ticket_id>/psa")
@jwt_required
def save_ticket_psa(ticket_id: int):
    try:
        data = request.get_json() or {}
        psa_id = data.get("psa_id")
        if not psa_id:
            return jsonify({"msg": "psa_id fehlt"}), 400

        ticket = get_kundendetails(ticket_id)
        if not ticket or not ticket.get("email"):
            return jsonify({"msg": "Ticket oder E-Mail nicht gefunden"}), 400

        email = (ticket["email"] or "").strip().lower()

        user = User.query.get(psa_id)
        if not user:
            return jsonify({"msg": "PSA-User nicht gefunden"}), 400

        obj = CustomerPSA.query.filter_by(email=email).first()
        if obj:
            obj.psa_user_id = psa_id
        else:
            obj = CustomerPSA(email=email, psa_user_id=psa_id)
            db.session.add(obj)

        db.session.commit()

        psa_name = (
            getattr(user, "display_name", None)
            or getattr(user, "username", None)
            or user.email
        )

        return jsonify({"success": True, "psa_name": psa_name})
    except Exception as e:
        current_app.logger.exception("save_ticket_psa failed")
        return jsonify({"msg": f"PSA speichern fehlgeschlagen: {e}"}), 500



# ---------------------------------------------------------------------------
# Woo-Produkte (für Angebot/Zahlungslink)
# ---------------------------------------------------------------------------

@bp.get("/products")
@jwt_required
def products_list():
    try:
        return jsonify(get_wp_products())
    except Exception as e:
        current_app.logger.exception("WP products failed")
        return jsonify({"msg": f"WP products failed: {e}"}), 500


# ---------------------------------------------------------------------------
# Zahlungslink senden (Woo + ticket_meta + Mail-Stub)
# ---------------------------------------------------------------------------

def send_payment_mail(email: str, name: str, ticket_id: int, url: str, amount: float):
    """
    E-Mail mit Zahlungslink per SMTP versenden.
    Text & Betreff kommen aus der settings-Tabelle:
      - OFFER_MAIL_SUBJECT
      - OFFER_MAIL_BODY
      - OFFER_MAIL_SIGNATURE
    Platzhalter:
      {customer_name}, {ticket_id}, {amount}, {payment_link}, {signature}
    """
    cfg = current_app.config

    # Templates aus Settings
    subject_tpl = _get_setting(
        "OFFER_MAIL_SUBJECT",
        "Ihr Sitefixer-Angebot zu Ticket #{ticket_id}",
    )
    body_tpl = _get_setting(
        "OFFER_MAIL_BODY",
        (
            "Hallo {customer_name},\n\n"
            "vielen Dank für Ihre Anfrage.\n"
            "hier ist der Zahlungslink zu Ihrem Angebot über {amount} €:\n"
            "{payment_link}\n\n"
            "Mit freundlichen Grüßen,\n"
            "{signature}"
        ),
    )
    signature = _get_setting(
        "OFFER_MAIL_SIGNATURE",
        "Sitefixer Support-Team\nsupport@sitefixer.de",
    )

    ctx = {
        "customer_name": name or "",
        "ticket_id": ticket_id,
        "amount": f"{amount:.2f}",
        "payment_link": url,
        "signature": signature,
    }

    subject = subject_tpl.format(**ctx)
    body = body_tpl.format(**ctx)

    mail_from = cfg.get("MAIL_FROM", "support@sitefixer.de")

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = mail_from
    msg["To"] = email

    host = cfg.get("SMTP_HOST")
    port = cfg.get("SMTP_PORT", 587)
    user = cfg.get("SMTP_USER")
    password = cfg.get("SMTP_PASSWORD")
    use_tls = cfg.get("SMTP_USE_TLS", True)

    current_app.logger.info(
        "[Zahlungslink] SMTP try to=%s ticket=%s url=%s amount=%.2f",
        email,
        ticket_id,
        url,
        amount,
    )

    try:
        with smtplib.SMTP(host, port, timeout=20) as smtp:
            smtp.ehlo()
            if use_tls:
                smtp.starttls()
                smtp.ehlo()
            if user:
                smtp.login(user, password)
            smtp.send_message(msg)

        current_app.logger.info(
            "[Zahlungslink] SMTP sent to=%s ticket=%s", email, ticket_id
        )
    except Exception:
        current_app.logger.exception("send_payment_mail SMTP failed")
        # Fehler weitergeben -> /send_payment-Endpoint antwortet mit 500
        raise



def _build_checkout_url(db_wp, prefix: str, product_id: int, ticket_id: int) -> str:
    cur = db_wp.cursor()
    cur.execute(
        f"SELECT option_name, option_value FROM {prefix}options "
        "WHERE option_name IN ('home','woocommerce_checkout_page_id')"
    )
    opts = {row[0]: row[1] for row in cur.fetchall()}
    cur.close()

    home_url = (opts.get("home") or "").rstrip("/")
    checkout_base = f"{home_url}/checkout"

    checkout_page_id = opts.get("woocommerce_checkout_page_id")
    if checkout_page_id:
        cur2 = db_wp.cursor()
        cur2.execute(
            f"SELECT post_name FROM {prefix}posts WHERE ID=%s LIMIT 1",
            (int(checkout_page_id),),
        )
        row = cur2.fetchone()
        cur2.close()
        if row and row[0]:
            checkout_base = f"{home_url}/{row[0]}"

    return f"{checkout_base}/?add-to-cart={product_id}&fs_ticket_id={ticket_id}"


@bp.post("/tickets/<int:ticket_id>/send_payment")
@jwt_required
def send_payment(ticket_id: int):
    try:
        data = request.get_json() or {}
        product_id = data.get("product_id")
        if not product_id:
            return jsonify({"msg": "product_id fehlt"}), 400

        ticket = get_kundendetails(ticket_id)
        if not ticket or not ticket.get("email"):
            return jsonify({"msg": "Ticket oder E-Mail nicht gefunden"}), 400

        email = ticket["email"].strip()
        name = ticket.get("name") or ""

        cfg = _cfg()
        prefix = cfg["prefix"]
        db_wp = _conn()
        try:
            cur = db_wp.cursor()
            cur.execute(
                f"SELECT meta_value FROM {prefix}postmeta "
                "WHERE post_id=%s AND meta_key='_price' LIMIT 1",
                (product_id,),
            )
            row = cur.fetchone()
            cur.close()
            amount = float(row[0]) if row and row[0] is not None else 0.0

            checkout_url = _build_checkout_url(
                db_wp, prefix, int(product_id), ticket_id
            )
        finally:
            db_wp.close()

        # ticket_meta upsert (nur noch Angebot / Link / Produkt)
        meta = TicketMeta.query.filter_by(ticket_id=ticket_id).first()
        if not meta:
            meta = TicketMeta(ticket_id=ticket_id)
            db.session.add(meta)

        meta.offer_amount = amount
        meta.payment_link = checkout_url
        meta.product_id = int(product_id)

        # Bearbeiter ermitteln (aktueller Sitefixer-User)
        handler = "scanner"
        try:
            uid = _current_user_id()
            if uid:
                u = User.query.get(uid)
                if u:
                    handler = u.name or u.email or handler
        except Exception:
            current_app.logger.warning(
                "send_payment: _current_user_id fehlgeschlagen",
                exc_info=True,
            )

        meta.last_admin = handler
        db.session.commit()

        # Status + Bearbeiter in der WordPress-DB setzen
        set_wp_status(ticket_id, "Warte auf Zahlung", handler)

        # Mail mit Zahlungslink senden
        send_payment_mail(
            email=email,
            name=name,
            ticket_id=ticket_id,
            url=checkout_url,
            amount=amount,
        )

        return jsonify(
            {
                "success": True,
                "payment_link": checkout_url,
                "amount": amount,
                "status": "Angebot gesendet",
                "handler": handler,
            }
        )
    except Exception as e:
        current_app.logger.exception("send_payment failed")
        return jsonify({"msg": f"Zahlungslink senden fehlgeschlagen: {e}"}), 500


# ---------------------------------------------------------------------------
# Interne Notizen / Wiedervorlage
# ---------------------------------------------------------------------------

@bp.get("/tickets/<int:ticket_id>/notes")
@jwt_required
def get_notes(ticket_id: int):
    try:
        notes = (
            TicketNote.query.filter_by(ticket_id=ticket_id)
            .order_by(TicketNote.created_at.desc())
            .all()
        )
        user_ids = {n.author_id for n in notes if n.author_id}
        users = {
            u.id: u
            for u in User.query.filter(User.id.in_(user_ids)).all()
        }

        out = []
        for n in notes:
            u = users.get(n.author_id)
            author_name = (
                getattr(u, "display_name", None)
                or getattr(u, "username", None)
                or (u.email if u else "Unbekannt")
            )
            out.append(
                {
                    "id": n.id,
                    "ticket_id": n.ticket_id,
                    "author_id": n.author_id,
                    "author_name": author_name,
                    "text": n.text,
                    "remind_at": n.remind_at.isoformat()
                    if n.remind_at
                    else None,
                    "created_at": n.created_at.isoformat()
                    if n.created_at
                    else None,
                }
            )
        return jsonify(out)
    except Exception as e:
        current_app.logger.exception("get_notes failed")
        return jsonify({"msg": f"Notiz speichern fehlgeschlagen: {e}"}), 500


@bp.post("/tickets/<int:ticket_id>/notes")
@jwt_required
def add_note(ticket_id: int):
    try:
        data = request.get_json() or {}
        text = (data.get("text") or "").strip()
        remind_at_str = data.get("remind_at")

        if not text:
            return jsonify({"msg": "text fehlt"}), 400

        author_id = _current_user_id()
        # Wenn keine ID gefunden wird, Notiz anonym speichern
        if not author_id:
            current_app.logger.warning(
                "add_note: keine author_id, speichere Notiz anonym"
            )
            author_id = None

        remind_at = None
        if remind_at_str:
            from datetime import datetime

            try:
                remind_at = datetime.fromisoformat(remind_at_str)
            except ValueError:
                remind_at = None

        note = TicketNote(
            ticket_id=ticket_id,
            author_id=author_id,
            text=text,
            remind_at=remind_at,
        )
        db.session.add(note)
        db.session.commit()

        return jsonify({"success": True, "id": note.id})
    except Exception as e:
        current_app.logger.exception("add_note failed")
        return jsonify({"msg": f"Notiz speichern fehlgeschlagen: {e}"}), 500
 

def _get_setting(name: str, default: str | None = None) -> str | None:
    s = Setting.query.get(name)
    if s is None or s.value is None:
        return default
    return s.value

def _get_settings_dict() -> dict[str, str]:
    out: dict[str, str] = {}
    for s in Setting.query.all():
        out[s.name] = s.value or ""
    return out

def _smtp_send(to_email: str, subject: str, body: str):
    """
    Einfacher SMTP-Versand über Umgebungsvariablen/Config.
    Erwartet folgende Config-Werte:
      SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASSWORD, SMTP_USE_TLS, MAIL_FROM
    """
    cfg = current_app.config

    host = cfg.get("SMTP_HOST")
    port = int(cfg.get("SMTP_PORT", 587))
    user = cfg.get("SMTP_USER")
    password = cfg.get("SMTP_PASSWORD")
    use_tls = bool(cfg.get("SMTP_USE_TLS", True))

    # From-Adresse hart auf support@sitefixer.de setzen
    from_email = cfg.get("MAIL_FROM", "support@sitefixer.de")

    if not host:
        current_app.logger.error("SMTP_HOST nicht gesetzt – Mail wird nicht gesendet")
        return

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = from_email
    msg["To"] = to_email
    msg.set_content(body)

    current_app.logger.info("Sende Mail an %s via %s:%s", to_email, host, port)

    with smtplib.SMTP(host, port) as server:
        if use_tls:
            server.starttls()
        if user and password:
            server.login(user, password)
        server.send_message(msg)


@bp.post("/tickets/<int:ticket_id>/status")
@jwt_required
def update_ticket_status(ticket_id: int):
    try:
        data = request.get_json() or {}
        new_status = (data.get("status") or "").strip()
        if not new_status:
            return jsonify({"ok": False, "msg": "status missing"}), 400

        # Aktuellen Sitefixer-User als Bearbeiter ermitteln
        handler = None
        try:
            uid = _current_user_id()
            if uid:
                u = User.query.get(uid)
                if u:
                    handler = u.name or u.email
        except Exception:
            current_app.logger.warning(
                "update_ticket_status: _current_user_id fehlgeschlagen",
                exc_info=True,
            )

        set_wp_status(ticket_id, new_status, handler)

        return jsonify(
            {
                "ok": True,
                "status": _normalize_status(new_status),
                "handler": handler,
            }
        )
    except Exception as e:
        current_app.logger.exception("update_ticket_status failed")
        return jsonify({"ok": False, "msg": f"update_ticket_status failed: {e}"}), 500



