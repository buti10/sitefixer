# /var/www/sitefixer/backend/app/wp_bridge.py
import os, json, mysql.connector, phpserialize
from datetime import datetime, timedelta
from flask import current_app

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
    return mysql.connector.connect(**{k:v for k,v in _cfg().items() if k!="prefix"})

def _parse_name(raw: str) -> str:
    try:
        n = json.loads(raw)
        if isinstance(n, dict):
            return (n.get("first-name","")+" "+n.get("last-name","")).strip()
        return str(n)
    except Exception: pass
    try:
        n = phpserialize.loads(raw.encode(), decode_strings=True)
        if isinstance(n, dict):
            return (n.get("first-name","")+" "+n.get("last-name","")).strip()
        return str(n)
    except Exception: pass
    return raw

def _parse_ymd(s: str) -> datetime:
    try:
        return datetime.fromisoformat(s)
    except Exception:
        if len(s)==7 and s[4]=='-':
            return datetime.fromisoformat(s+"-01")
        raise

def get_wp_tickets_range(start: str|None, end: str|None):
    cfg = _cfg(); prefix = cfg["prefix"]
    db = _conn(); cur = db.cursor(dictionary=True)

    start_dt = _parse_ymd(start) if start else datetime(1970,1,1)
    end_dt   = (_parse_ymd(end) + timedelta(days=1)) if end else datetime(2100,1,1)

    cur.execute(
        f"""SELECT entry_id, date_created
              FROM {prefix}frmt_form_entry
             WHERE date_created >= %s AND date_created < %s
             ORDER BY entry_id DESC
             LIMIT 1000""",
        (start_dt, end_dt)
    )
    entries = cur.fetchall()

    out = []
    for row in entries:
        entry_id = int(row["entry_id"])
        created  = row["date_created"]

        cur.execute(
            f"SELECT meta_key, meta_value FROM {prefix}frmt_form_entry_meta WHERE entry_id=%s",
            (entry_id,)
        )
        meta = {m["meta_key"]: m["meta_value"] for m in cur.fetchall()}

        name = _parse_name(meta.get("name-1","")) if meta.get("name-1") else ""

        out.append({
            "ticket_id"   : entry_id,
            "created_at"  : created.isoformat() if hasattr(created, "isoformat") else str(created),
            "name"        : name,
            # FTP
            "ftp_host": meta.get("zugang_ftp_host",""),
            "ftp_user": meta.get("zugang_ftp_user",""),
            "ftp_pass": meta.get("zugang_ftp_pass",""),
            # Website (Alias für Frontend)
            "website_user":  meta.get("zugang_website_user",""),
            "website_login": meta.get("zugang_website_user",""),   # Alias
            "website_pass":  meta.get("zugang_website_pass",""),
            # Hosting (bisher fehlend)
            "hosting_url":  meta.get("zugang_hosting_url",""),
            "hosting_user": meta.get("zugang_hosting_user",""),
            "hosting_pass": meta.get("zugang_hosting_pass",""),
            "email"       : meta.get("email-1",""),
            "domain"      : meta.get("url-1",""),
            "prio"        : meta.get("radio-1") or meta.get("priority") or None,
            "status"      : meta.get("status") or None,
            "beschreibung": meta.get("textarea-1") or None,
            "hoster"      : meta.get("textarea-2") or None,
            "cms"         : meta.get("radio-2") or None,
        })

    cur.close(); db.close()
    return out

def get_wp_customers():
    return get_wp_tickets_range(None, None)

def get_kundendetails(ticket_id: int):
    cfg = _cfg(); prefix = cfg["prefix"]
    db = _conn(); cur = db.cursor(dictionary=True)
    cur.execute(f"SELECT meta_key, meta_value FROM {prefix}frmt_form_entry_meta WHERE entry_id=%s", (ticket_id,))
    meta = {r["meta_key"]: r["meta_value"] for r in cur.fetchall()}
    cur.close(); db.close()
    return {
        "ticket_id": ticket_id,
        "domain": meta.get("url-1",""),
        "name": _parse_name(meta.get("name-1","")) if meta.get("name-1") else "",
        "email": meta.get("email-1",""),
        "ftp_host": meta.get("zugang_ftp_host",""),
        "ftp_user": meta.get("zugang_ftp_user",""),
        "ftp_pass": meta.get("zugang_ftp_pass",""),
        "website_user": meta.get("zugang_website_user",""),
        "website_pass": meta.get("zugang_website_pass",""),
        "prio": meta.get("radio-1") or None,
        "status": meta.get("status") or None,
        "beschreibung": meta.get("textarea-1") or None,
        "hoster": meta.get("textarea-2") or None,
        "cms": meta.get("radio-2") or None,
    }
