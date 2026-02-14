# /var/www/sitefixer/backend/app/wp_bridge.py
from __future__ import annotations

import os, json, base64, hashlib
import mysql.connector, phpserialize
from datetime import datetime, timedelta
from flask import current_app

# Scanner-DB Models (SQLAlchemy)
from app.extensions import db
from app.modules.tickets_public.models import Ticket, TicketAccess, TicketScan, TicketEvent

# Crypto Helper (dein encrypt_to_b64 kommt aus app.core.crypto)
# -> wir brauchen hier das Gegenstück
from app.core.crypto import decrypt_from_b64


# =========================
# Status Normalisierung (gleich lassen)
# =========================
_STATUS_NORMALIZE = {
    "": "Neu",
    "neu": "Neu",
    "offen": "Neu",
    "open": "Neu",
    "queued": "Neu",
    "scanning": "Neu",

    "angebot": "Angebot gesendet",
    "angebot gesendet": "Angebot gesendet",
    "await": "Angebot gesendet",
    "waiting": "Angebot gesendet",
    "pending": "Angebot gesendet",

    "bezahlt": "Bezahlt",
    "paid": "Bezahlt",

    "abgeschlossen": "Abgeschlossen",
    "closed": "Abgeschlossen",
    "done": "Abgeschlossen",

    "abgebrochen": "Abgebrochen",
    "cancelled": "Abgebrochen",
    "storniert": "Abgebrochen",
    "failed": "Abgebrochen",
}

def _normalize_status(raw: str | None) -> str:
    if not raw:
        return "Neu"
    s = str(raw).strip().lower()
    return _STATUS_NORMALIZE.get(s, "Neu")


# =========================
# TICKETS-SOURCE SWITCH
# =========================
def _tickets_source() -> str:
    """
    "scanner" = Tickets aus deiner Sitefixer/Scanner DB (SQLAlchemy)
    "wp"      = Tickets aus WordPress DB (Forminator)
    """
    v = (os.getenv("TICKETS_SOURCE") or "scanner").strip().lower()
    return "wp" if v == "wp" else "scanner"


# =========================
# SCANNER-DB: Mapping auf altes WP-Format
# =========================
def _scanner_ticket_to_row(t: Ticket) -> dict:
    # Domain-Feld erwartet dein Vue als "domain"
    domain = (t.site_url or "").strip()

    # Optional: nimm final_url aus letztem preflight, wenn vorhanden
    try:
        s = (
            TicketScan.query
            .filter_by(ticket_id=t.id, scan_type="preflight")
            .order_by(TicketScan.id.desc())
            .first()
        )
        if s and s.result_json and (s.result_json.get("final_url")):
            domain = s.result_json["final_url"]
    except Exception:
        pass

    return {
        "ticket_id": int(t.id),
        "created_at": t.created_at.isoformat() if getattr(t, "created_at", None) else None,
        "name": t.customer_name or "",
        "email": t.customer_email or "",
        "domain": domain,
        "prio": None,
        "status": _normalize_status(t.status),
        "status_handler": getattr(t, "handler", None) if hasattr(t, "handler") else None,
        "beschreibung": None,
        "hoster": None,
        "cms": None,
        "handler": getattr(t, "handler", None) if hasattr(t, "handler") else None,
        # Kompatibilität: diese Felder liefert WP-Bridge normalerweise,
        # aber bei Liste brauchst du sie nicht zwingend – trotzdem setzen wir leer:
        "ftp_host": "",
        "ftp_user": "",
        "ftp_pass": "",
        "website_user": "",
        "website_login": "",
        "website_pass": "",
        "hosting_url": "",
        "hosting_user": "",
        "hosting_pass": "",
    }


def _scanner_access_to_details(t: Ticket, acc: TicketAccess | None) -> dict:
    # Default leer
    ftp_host = ftp_user = ftp_pass = ""
    wp_user = wp_pass = ""

    if acc:
        ftp_host = acc.sftp_host or ""
        ftp_user = acc.sftp_user or ""
        ftp_pass = decrypt_from_b64(acc.sftp_pass_enc) if acc.sftp_pass_enc else ""

        wp_user = acc.wp_admin_user or ""
        wp_pass = decrypt_from_b64(acc.wp_admin_pass_enc) if acc.wp_admin_pass_enc else ""

    domain = (t.site_url or "").strip()
    try:
        s = (
            TicketScan.query
            .filter_by(ticket_id=t.id, scan_type="preflight")
            .order_by(TicketScan.id.desc())
            .first()
        )
        if s and s.result_json and (s.result_json.get("final_url")):
            domain = s.result_json["final_url"]
    except Exception:
        pass

    return {
        "ticket_id": int(t.id),
        "domain": domain,
        "name": t.customer_name or "",
        "email": t.customer_email or "",

        # FTP (SFTP)
        "ftp_host": ftp_host,
        "ftp_user": ftp_user,
        "ftp_pass": ftp_pass,

        # Website (wir mappen WP-Admin darauf, weil dein UI das so nutzt)
        "website_user": wp_user,
        "website_login": "",  # falls du später Login-URL speichern willst
        "website_pass": wp_pass,

        # Hosting (optional später)
        "hosting_url": "",
        "hosting_user": "",
        "hosting_pass": "",

        "prio": None,
        "status": _normalize_status(t.status),
        "status_handler": getattr(t, "handler", None) if hasattr(t, "handler") else None,
        "beschreibung": None,
        "hoster": None,
        "cms": None,

        "attachments": [],
        "handler": getattr(t, "handler", None) if hasattr(t, "handler") else None,
    }


def set_wp_status(ticket_id: int, status: str, handler: str | None = None):
    """
    Bridge-Funktion – Name bleibt, aber:
    Wenn Tickets aus scanner kommen -> update in Scanner-DB.
    Wenn Tickets aus WP kommen -> update in WP-DB.
    """
    if _tickets_source() == "scanner":
        t = db.session.get(Ticket, int(ticket_id))
        if not t:
            return
        t.status = _normalize_status(status)  # wir speichern direkt normalisiert
        if handler and hasattr(t, "handler"):
            setattr(t, "handler", handler)

        # Event log optional
        try:
            db.session.add(TicketEvent(ticket_id=t.id, type="status_changed", payload_json={"status": t.status, "handler": handler}))
        except Exception:
            pass

        db.session.commit()
        return

    # -------- WP FALLBACK (alt) --------
    _set_wp_status_wordpress(ticket_id, status, handler)


def get_wp_tickets_range(start: str | None, end: str | None):
    """
    Wird von /api/wp/tickets genutzt.
    Wir liefern gleiche Felder wie bisher, aber Source ist scanner.
    """
    if _tickets_source() == "scanner":
        start_dt = _parse_ymd(start) if start else datetime(1970, 1, 1)
        end_dt = (_parse_ymd(end) + timedelta(days=1)) if end else datetime(2100, 1, 1)

        q = (
            Ticket.query
            .filter(Ticket.created_at >= start_dt)
            .filter(Ticket.created_at < end_dt)
            .order_by(Ticket.id.desc())
            .limit(1000)
        )
        items = q.all()
        return [_scanner_ticket_to_row(t) for t in items]

    # -------- WP FALLBACK (alt) --------
    return _get_wp_tickets_range_wordpress(start, end)


def get_wp_customers():
    # wird bei dir als alias genutzt
    return get_wp_tickets_range(None, None)


def get_kundendetails(ticket_id: int):
    """
    Wird von /api/wp/tickets/<id> genutzt.
    """
    if _tickets_source() == "scanner":
        t = db.session.get(Ticket, int(ticket_id))
        if not t:
            return None

        acc = TicketAccess.query.filter_by(ticket_id=t.id).first()
        return _scanner_access_to_details(t, acc)

    # -------- WP FALLBACK (alt) --------
    return _get_kundendetails_wordpress(ticket_id)


# =========================================================
# ============== AB HIER: ALTE WP-IMPLEMENTATION ===========
# (damit Products & Co weiter funktionieren)
# =========================================================

def _cfg():
    g = lambda k: os.getenv(k, "")
    return {
        "host": g("WP_DB_HOST"),
        "user": g("WP_DB_USER"),
        "password": g("WP_DB_PASSWORD"),
        "database": g("WP_DB_DATABASE"),
        "prefix": g("WP_DB_PREFIX") or "sndm_",
    }

def _conn():
    return mysql.connector.connect(**{k: v for k, v in _cfg().items() if k != "prefix"})


def _access_key_bytes() -> bytes | None:
    secret = os.getenv("FS_ACCESS_SECRET_KEY", "") or ""
    secret = secret.strip()
    if not secret:
        return None
    return hashlib.sha256(secret.encode("utf-8")).digest()

def _pkcs7_unpad(data: bytes) -> bytes:
    if not data:
        return data
    pad = data[-1]
    if pad < 1 or pad > 16:
        raise ValueError("bad padding")
    if data[-pad:] != bytes([pad]) * pad:
        raise ValueError("bad padding")
    return data[:-pad]

def access_decrypt(stored: str | None) -> str:
    if not stored:
        return ""
    s = str(stored)
    if not s.startswith("enc:v1:"):
        return s

    key = _access_key_bytes()
    if not key:
        return s

    raw_b64 = s[7:]
    try:
        raw = base64.b64decode(raw_b64, validate=True)
        if len(raw) < 17:
            return ""
        iv = raw[:16]
        cipher = raw[16:]

        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.backends import default_backend

        decryptor = Cipher(
            algorithms.AES(key),
            modes.CBC(iv),
            backend=default_backend()
        ).decryptor()

        padded = decryptor.update(cipher) + decryptor.finalize()
        plain = _pkcs7_unpad(padded)
        return plain.decode("utf-8", errors="replace")
    except Exception:
        return ""


def _parse_name(raw: str) -> str:
    try:
        n = json.loads(raw)
        if isinstance(n, dict):
            return (n.get("first-name", "") + " " + n.get("last-name", "")).strip()
        return str(n)
    except Exception:
        pass
    try:
        n = phpserialize.loads(raw.encode(), decode_strings=True)
        if isinstance(n, dict):
            return (n.get("first-name", "") + " " + n.get("last-name", "")).strip()
        return str(n)
    except Exception:
        pass
    return raw

def _parse_ymd(s: str) -> datetime:
    try:
        return datetime.fromisoformat(s)
    except Exception:
        if len(s) == 7 and s[4] == "-":
            return datetime.fromisoformat(s + "-01")
        raise

def _parse_uploads(raw):
    out = []
    if not raw:
        return out
    if isinstance(raw, str) and raw.startswith("http"):
        return [raw]
    try:
        decoded = phpserialize.loads(raw.encode(), decode_strings=True)
        if isinstance(decoded, (list, tuple)):
            for val in decoded:
                if isinstance(val, dict):
                    fu = val.get("file_url")
                    if isinstance(fu, list):
                        out.extend([u for u in fu if isinstance(u, str)])
                    elif isinstance(fu, str):
                        out.append(fu)
        elif isinstance(decoded, dict):
            fu = decoded.get("file_url")
            if isinstance(fu, list):
                out.extend([u for u in fu if isinstance(u, str)])
            elif isinstance(fu, str):
                out.append(fu)
    except Exception:
        pass
    return out


def _set_wp_status_wordpress(ticket_id: int, status: str, handler: str | None = None):
    cfg = _cfg()
    prefix = cfg["prefix"]
    dbx = _conn()
    cur = dbx.cursor()
    try:
        norm_status = _normalize_status(status)
        cur.execute(
            f"""
            INSERT INTO {prefix}frmt_form_entry_meta (entry_id, meta_key, meta_value)
            VALUES (%s, 'status', %s)
            ON DUPLICATE KEY UPDATE meta_value = VALUES(meta_value)
            """,
            (ticket_id, norm_status),
        )
        if handler:
            cur.execute(
                f"""
                INSERT INTO {prefix}frmt_form_entry_meta (entry_id, meta_key, meta_value)
                VALUES (%s, 'scanner_handler', %s)
                ON DUPLICATE KEY UPDATE meta_value = VALUES(meta_value)
                """,
                (ticket_id, handler),
            )
        dbx.commit()
    finally:
        cur.close()
        dbx.close()


def _get_wp_tickets_range_wordpress(start: str | None, end: str | None):
    cfg = _cfg()
    prefix = cfg["prefix"]
    dbx = _conn()
    cur = dbx.cursor(dictionary=True)

    start_dt = _parse_ymd(start) if start else datetime(1970, 1, 1)
    end_dt = (_parse_ymd(end) + timedelta(days=1)) if end else datetime(2100, 1, 1)

    cur.execute(
        f"""SELECT entry_id, date_created
              FROM {prefix}frmt_form_entry
             WHERE date_created >= %s AND date_created < %s
             ORDER BY entry_id DESC
             LIMIT 1000""",
        (start_dt, end_dt),
    )
    entries = cur.fetchall()

    out = []
    for row in entries:
        entry_id = int(row["entry_id"])
        created = row["date_created"]

        cur.execute(
            f"SELECT meta_key, meta_value FROM {prefix}frmt_form_entry_meta WHERE entry_id=%s",
            (entry_id,),
        )
        meta = {m["meta_key"]: m["meta_value"] for m in cur.fetchall()}

        name = _parse_name(meta.get("name-1", "")) if meta.get("name-1") else ""

        out.append(
            {
                "ticket_id": entry_id,
                "created_at": created.isoformat() if hasattr(created, "isoformat") else str(created),
                "name": name,
                "ftp_host": access_decrypt(meta.get("zugang_ftp_host", "")),
                "ftp_user": access_decrypt(meta.get("zugang_ftp_user", "")),
                "ftp_pass": access_decrypt(meta.get("zugang_ftp_pass", "")),
                "website_user": access_decrypt(meta.get("zugang_website_user", "")),
                "website_login": access_decrypt(meta.get("zugang_website_login", "")),
                "website_pass": access_decrypt(meta.get("zugang_website_pass", "")),
                "hosting_url": access_decrypt(meta.get("zugang_hosting_url", "")),
                "hosting_user": access_decrypt(meta.get("zugang_hosting_user", "")),
                "hosting_pass": access_decrypt(meta.get("zugang_hosting_pass", "")),
                "email": meta.get("email-1", ""),
                "domain": meta.get("url-1", ""),
                "prio": meta.get("radio-1") or meta.get("priority") or None,
                "status": meta.get("status") or "Neu",
                "status_handler": meta.get("status_handler") or None,
                "beschreibung": meta.get("textarea-1") or None,
                "hoster": meta.get("textarea-2") or None,
                "cms": meta.get("radio-2") or None,
                "handler": meta.get("scanner_handler") or None,
            }
        )

    cur.close()
    dbx.close()
    return out


def _get_kundendetails_wordpress(ticket_id: int):
    cfg = _cfg()
    prefix = cfg["prefix"]
    dbx = _conn()
    cur = dbx.cursor(dictionary=True)
    cur.execute(
        f"SELECT meta_key, meta_value FROM {prefix}frmt_form_entry_meta WHERE entry_id=%s",
        (ticket_id,),
    )
    meta = {r["meta_key"]: r["meta_value"] for r in cur.fetchall()}
    cur.close()
    dbx.close()

    attachments = _parse_uploads(meta.get("upload-1"))

    return {
        "ticket_id": ticket_id,
        "domain": meta.get("url-1", ""),
        "name": _parse_name(meta.get("name-1", "")) if meta.get("name-1") else "",
        "email": meta.get("email-1", ""),
        "ftp_host": access_decrypt(meta.get("zugang_ftp_host", "")),
        "ftp_user": access_decrypt(meta.get("zugang_ftp_user", "")),
        "ftp_pass": access_decrypt(meta.get("zugang_ftp_pass", "")),
        "website_user": access_decrypt(meta.get("zugang_website_user", "")),
        "website_login": access_decrypt(meta.get("zugang_website_login", "")),
        "website_pass": access_decrypt(meta.get("zugang_website_pass", "")),
        "hosting_url": access_decrypt(meta.get("zugang_hosting_url", "")),
        "hosting_user": access_decrypt(meta.get("zugang_hosting_user", "")),
        "hosting_pass": access_decrypt(meta.get("zugang_hosting_pass", "")),
        "prio": meta.get("radio-1") or None,
        "status": meta.get("status") or "Neu",
        "status_handler": meta.get("status_handler") or None,
        "beschreibung": meta.get("textarea-1") or None,
        "hoster": meta.get("textarea-2") or None,
        "cms": meta.get("radio-2") or None,
        "attachments": attachments,
        "handler": meta.get("scanner_handler") or None,
    }


def get_wp_products():
    cfg = _cfg()
    prefix = cfg["prefix"]
    dbx = _conn()
    cur = dbx.cursor(dictionary=True)
    out = []
    try:
        cur.execute(
            f"SELECT ID, post_title FROM {prefix}posts "
            "WHERE post_type='product' AND post_status='publish' "
            "ORDER BY post_title ASC"
        )
        products = cur.fetchall()
        for p in products:
            pid = int(p["ID"])
            title = p["post_title"]

            cur2 = dbx.cursor()
            cur2.execute(
                f"SELECT meta_value FROM {prefix}postmeta "
                "WHERE post_id=%s AND meta_key='_price' LIMIT 1",
                (pid,),
            )
            row = cur2.fetchone()
            cur2.close()
            price = float(row[0]) if row and row[0] is not None else 0.0
            out.append({"id": pid, "name": title, "price": price})
    finally:
        cur.close()
        dbx.close()
    return out
