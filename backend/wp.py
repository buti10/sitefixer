import os, json, phpserialize, mysql.connector

CFG = {
    "host": os.getenv("WP_HOST"),
    "port": int(os.getenv("WP_PORT", "3306")),
    "user": os.getenv("WP_USER"),
    "password": os.getenv("WP_PASSWORD"),
    "database": os.getenv("WP_DATABASE"),
    "prefix": os.getenv("WP_PREFIX", "wp_"),
}

def _conn():
    return mysql.connector.connect(
        host=CFG["host"], port=CFG["port"], user=CFG["user"],
        password=CFG["password"], database=CFG["database"]
    )

def _parse_name(raw):
    if not raw: return ""
    try:
        n = json.loads(raw)
        if isinstance(n, dict):
            return f"{n.get('first-name','')} {n.get('last-name','')}".strip()
        return str(n)
    except Exception:
        pass
    try:
        n = phpserialize.loads(raw.encode(), decode_strings=True)
        if isinstance(n, dict):
            return f"{n.get('first-name','')} {n.get('last-name','')}".strip()
        return str(n)
    except Exception:
        return str(raw)

def list_tickets(limit=200):
    db = _conn(); cur = db.cursor(dictionary=True)
    p = CFG["prefix"]
    cur.execute(f"SELECT entry_id FROM {p}frmt_form_entry ORDER BY entry_id DESC LIMIT %s", (limit,))
    ids = [int(r["entry_id"]) for r in cur.fetchall()]
    out = []
    for eid in ids:
        cur.execute(f"SELECT meta_key, meta_value FROM {p}frmt_form_entry_meta WHERE entry_id=%s", (eid,))
        meta = {m["meta_key"]: m["meta_value"] for m in cur.fetchall()}
        out.append({
            "ticket_id": eid,
            "name": _parse_name(meta.get("name-1","")),
            "email": meta.get("email-1",""),
            "beschreibung": meta.get("desc-1","") or meta.get("textarea-1","") or "",
            "prio": meta.get("priority","") or meta.get("prio",""),
            "status": meta.get("status","") or meta.get("payment_status",""),
        })
    cur.close(); db.close()
    return out

def ticket_details(ticket_id:int):
    db = _conn(); cur = db.cursor(dictionary=True)
    p = CFG["prefix"]
    cur.execute(f"SELECT meta_key, meta_value FROM {p}frmt_form_entry_meta WHERE entry_id=%s", (ticket_id,))
    meta = {m["meta_key"]: m["meta_value"] for m in cur.fetchall()}
    cur.close(); db.close()
    return {
        "ticket_id": ticket_id,
        "name": _parse_name(meta.get("name-1","")),
        "email": meta.get("email-1",""),
        "beschreibung": meta.get("desc-1","") or meta.get("textarea-1","") or "",
        "prio": meta.get("priority","") or meta.get("prio",""),
        "status": meta.get("status","") or meta.get("payment_status",""),

        "sftp": {
            "host": meta.get("zugang_ftp_host",""),
            "user": meta.get("zugang_ftp_user",""),
            "pass": meta.get("zugang_ftp_pass",""),
        },
        "hosting": {
            "url": meta.get("zugang_hosting_url",""),
            "user": meta.get("zugang_hosting_user",""),
            "pass": meta.get("zugang_hosting_pass",""),
        },
        "backend": {
            "url": meta.get("zugang_website_url","") or meta.get("url-1",""),
            "user": meta.get("zugang_website_user",""),
            "pass": meta.get("zugang_website_pass",""),
        },
        "domain": meta.get("url-1",""),
    }
import json, phpserialize

def _parse_name(raw):
    if not raw: return ""
    try:
        n = json.loads(raw)
        if isinstance(n, dict):
            return f"{n.get('first-name','')} {n.get('last-name','')}".strip()
    except Exception:
        pass
    try:
        n = phpserialize.loads(raw.encode(), decode_strings=True)
        if isinstance(n, dict):
            return f"{n.get('first-name','')} {n.get('last-name','')}".strip()
    except Exception:
        pass
    return str(raw)