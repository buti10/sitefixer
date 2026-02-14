# app/modules/comms_woot/services.py
from __future__ import annotations

import os
import time
import logging
from typing import Optional, List, Dict
from datetime import datetime, timedelta
import requests
from flask import current_app
from sqlalchemy import func
from sqlalchemy.orm import aliased

from app.extensions import db
from app.models import User
from app.models_extra import (
    CustomerPSA,
    WootConversationLog,
    WootConversationOrigin,
)

# ---------------------------------------------------------------------------
# Basis-Konfiguration aus ENV
# ---------------------------------------------------------------------------

BASE = os.environ.get("WOOT_BASE_URL", "").rstrip("/")
ACC = os.environ.get("WOOT_ACCOUNT_ID", "")
PAT = os.environ.get("WOOT_API_TOKEN", "")
PLAT = os.environ.get("WOOT_PLATFORM_TOKEN", "")

# Optional: kleines In-Memory-Caching für Agentenliste
_agent_cache_ts: float | None = None
_agent_cache_data: list[dict] | None = None
_AGENT_CACHE_TTL = 30  # Sekunden

VERIFY = os.environ.get("WOOT_VERIFY_TLS", "true").lower() != "false"
TIMEOUT = (5, 20)
CURL_UA = os.environ.get("WOOT_UA", "curl/8.5.0")

# nur ASCII-Header, um Encoding-Probleme zu vermeiden
SAFE_HEADERS = {
    "Accept": "application/json",
    "Accept-Charset": "utf-8",
    "Accept-Language": "en",
    "Accept-Encoding": "identity",
    "User-Agent": CURL_UA,
}

# ---------------------------------------------------------------------------
# interne Helfer
# ---------------------------------------------------------------------------


def _assert_conf(require_pat: bool = True, require_plat: bool = False) -> bool:
    """
    Prüft, ob die nötigen ENV-Variablen gesetzt sind und grob plausibel aussehen.
    """
    missing = []

    if not BASE:
        missing.append("WOOT_BASE_URL")
    if not ACC:
        missing.append("WOOT_ACCOUNT_ID")
    if require_pat and not PAT:
        missing.append("WOOT_API_TOKEN")
    if require_plat and not PLAT:
        missing.append("WOOT_PLATFORM_TOKEN")

    # ACC muss int-fähig sein
    try:
        int(ACC)
    except Exception:
        missing.append("WOOT_ACCOUNT_ID (muss int sein)")

    if missing:
        raise RuntimeError("Chatwoot-Konfiguration unvollständig: " + ", ".join(missing))

    if not BASE.startswith("http"):
        raise RuntimeError(f"WOOT_BASE_URL unplausibel: {BASE}")

    return True


def _h_pat() -> dict:
    if not PAT:
        raise RuntimeError("WOOT_API_TOKEN fehlt")
    h = dict(SAFE_HEADERS)
    h["api_access_token"] = PAT
    return h


def _h_plat() -> dict:
    if not PLAT:
        raise RuntimeError("WOOT_PLATFORM_TOKEN fehlt")
    h = dict(SAFE_HEADERS)
    h["api_access_token"] = PLAT
    return h


def get_json(url: str, headers: dict, params: dict | None = None) -> dict:
    """
    Führt einen GET gegen Chatwoot aus und gibt immer ein dict zurück:
    { ok, status, data | error, url, resp_headers, sent_headers }
    """
    s = requests.Session()
    s.trust_env = False  # keine Proxy-Umgebungsvariablen benutzen

    try:
        r = s.get(
            url,
            headers=headers,
            params=params,
            timeout=TIMEOUT,
            verify=VERIFY,
            allow_redirects=False,
        )
    except Exception as e:
        return {
            "ok": False,
            "status": 599,
            "url": url,
            "error": f"{type(e).__name__}: {e}",
        }

    try:
        body = r.json()
    except Exception:
        body = r.text

    if r.status_code >= 400:
        return {
            "ok": False,
            "status": r.status_code,
            "url": url,
            "error": body,
            "resp_headers": dict(r.headers),
            "sent_headers": {k: v for k, v in r.request.headers.items()},
        }

    return {
        "ok": True,
        "status": r.status_code,
        "data": body,
    }


def _fetch_agents_from_chatwoot() -> list[dict]:
    """
    Ruft die Agentenliste aus Chatwoot ab.
    Erwartet /api/v1/accounts/:acc/agents mit Feldern:
      - id
      - email
      - availability_status (online/away/offline)
    """
    if not PAT:
        raise RuntimeError("WOOT_API_TOKEN missing")

    global _agent_cache_ts, _agent_cache_data

    now = time.time()
    if _agent_cache_ts and _agent_cache_data is not None:
        if now - _agent_cache_ts < _AGENT_CACHE_TTL:
            return _agent_cache_data

    url = f"{BASE}/api/v1/accounts/{ACC}/agents"
    r = requests.get(
        url,
        headers={"api_access_token": PAT},
        timeout=5,
    )
    r.raise_for_status()
    data = r.json()

    agents = data if isinstance(data, list) else data.get("data", [])
    _agent_cache_data = agents
    _agent_cache_ts = now
    return agents


def _is_agent_online(woot_user_id: int) -> bool:
    """
    Prüft, ob der Agent (Chatwoot-User-ID) aktuell 'online' ist.
    """
    try:
        agents = _fetch_agents_from_chatwoot()
    except Exception as e:
        current_app.logger.warning("could not fetch agents for online check: %s", e)
        return False

    for a in agents:
        if int(a.get("id", 0)) == int(woot_user_id):
            status = (a.get("availability_status") or "").lower()
            return status == "online"
    return False


def _find_fallback_agent(exclude_woot_id: int | None = None) -> Optional[User]:
    """
    Sucht einen 'anderen' online-User als Fallback.
    """
    try:
        agents = _fetch_agents_from_chatwoot()
    except Exception as e:
        current_app.logger.warning("could not fetch agents for fallback: %s", e)
        return None

    online_ids: list[int] = []
    for a in agents:
        status = (a.get("availability_status") or "").lower()
        if status != "online":
            continue
        aid = int(a.get("id", 0) or 0)
        if not aid:
            continue
        if exclude_woot_id and aid == int(exclude_woot_id):
            continue
        online_ids.append(aid)

    if not online_ids:
        return None

    u = (
        User.query
        .filter(User.woot_user_id.in_(online_ids))
        .filter(User.active == True)
        .order_by(User.id.asc())
        .first()
    )
    return u


# ---------------------------------------------------------------------------
# Öffentliche Service-Funktionen (REST-Proxys etc.)
# ---------------------------------------------------------------------------


def me_profile() -> dict:
    """
    /api/v1/profile mit PAT
    """
    _assert_conf(require_pat=True, require_plat=False)
    url = f"{BASE}/api/v1/profile"
    return get_json(url, _h_pat())


def account_show(account_id: int) -> dict:
    """
    /platform/api/v1/accounts/:id mit Platform-Token
    """
    _assert_conf(require_pat=False, require_plat=True)
    url = f"{BASE}/platform/api/v1/accounts/{account_id}"
    return get_json(url, _h_plat())


def sso_link(user_id: int) -> dict:
    """
    /platform/api/v1/users/:id/login mit Platform-Token
    """
    _assert_conf(require_pat=False, require_plat=True)
    url = f"{BASE}/platform/api/v1/users/{user_id}/login"
    return get_json(url, _h_plat())


def reports_inbox(since: int, until: int, business_hours: bool = False) -> dict:
    """
    Holt die zusammengefassten Account-Statistiken von Chatwoot.
    """

    if not PAT:
        return {
            "ok": False,
            "status": 500,
            "error": "WOOT_API_TOKEN missing",
        }

    url = f"{BASE}/api/v2/accounts/{ACC}/reports/summary"
    params = {
        "type": "account",
        "since": since,
        "until": until,
    }

    try:
        r = requests.get(
            url,
            headers={"api_access_token": PAT},
            params=params,
            timeout=5,
        )
    except Exception as e:
        return {
            "ok": False,
            "status": 502,
            "error": f"reports request failed: {e}",
        }

    status = r.status_code
    try:
        data = r.json()
    except ValueError:
        data = {"error": r.text or "invalid json from chatwoot"}

    if "status" not in data:
        data["status"] = status

    if "current" in data and isinstance(data["current"], dict):
        curr = data["current"]
        data.setdefault("conversations_count", curr.get("conversations_count"))
        data.setdefault("incoming_messages_count", curr.get("incoming_messages_count"))
        data.setdefault("outgoing_messages_count", curr.get("outgoing_messages_count"))
        data.setdefault("resolutions_count", curr.get("resolutions_count"))

    return data


def create_woot_user(email: str, name: str, password: str, role: str = "agent") -> int:
    """
    Legt einen neuen User in Chatwoot per Platform API an und hängt ihn an das
    bestehende Account (ACC) an. Gibt die Chatwoot-User-ID zurück.
    """
    if not PLAT:
        raise RuntimeError("WOOT_PLATFORM_TOKEN (Platform API) nicht konfiguriert")

    url_user = f"{BASE}/platform/api/v1/users"
    r = requests.post(
        url_user,
        headers={
            "Content-Type": "application/json",
            "api_access_token": PLAT,
        },
        json={
            "name": name,
            "display_name": name,
            "email": email,
            "password": password,
            "custom_attributes": {},
        },
        timeout=10,
    )
    if r.status_code != 200:
        raise RuntimeError(f"create user failed: {r.status_code} {r.text}")

    data = r.json()
    woot_id = data.get("id")
    if not woot_id:
        raise RuntimeError(f"no id returned from /platform/users: {data}")

    role_str = "administrator" if role == "admin" else "agent"
    url_acc_user = f"{BASE}/platform/api/v1/accounts/{ACC}/account_users"
    r2 = requests.post(
        url_acc_user,
        headers={
            "Content-Type": "application/json",
            "api_access_token": PLAT,
        },
        json={
            "user_id": woot_id,
            "role": role_str,
        },
        timeout=10,
    )
    if r2.status_code != 200:
        raise RuntimeError(f"create account_user failed: {r2.status_code} {r2.text}")

    return int(woot_id)


# ---------------------------------------------------------------------------
# PSA-Routing / Autoassignment
# ---------------------------------------------------------------------------


def _chatwoot_assign_conversation(conversation_id: int, woot_user_id: int) -> None:
    """
    Setzt den Assignee in Chatwoot. Fehler werden geloggt, aber werfen i.d.R.
    keine Exception mehr, damit unser internes Logging nicht kaputtgeht.
    """
    if not PAT:
        raise RuntimeError("WOOT_API_TOKEN missing")

    url = f"{BASE}/api/v1/accounts/{ACC}/conversations/{conversation_id}/assignments"
    r = requests.post(
        url,
        headers={"api_access_token": PAT, "Content-Type": "application/json"},
        json={"assignee_id": woot_user_id},
        timeout=5,
    )

    if r.status_code in (200, 201):
        return

    if r.status_code == 404:
        current_app.logger.warning(
            "Chatwoot assign 404 for conv %s, user %s: %s",
            conversation_id,
            woot_user_id,
            r.text,
        )
        return

    current_app.logger.error(
        "Chatwoot assign failed for conv %s, user %s: %s %s",
        conversation_id,
        woot_user_id,
        r.status_code,
        r.text,
    )


def _find_psa_by_email(email: str) -> Optional[User]:
    if not email:
        return None

    email_norm = email.strip().lower()
    link = CustomerPSA.query.filter(CustomerPSA.email == email_norm).first()
    if not link:
        return None

    return User.query.get(link.psa_user_id)


def _extract_email_from_payload(payload: dict) -> str | None:
    # 1) Kontakt-Daten (falls Chatwoot die E-Mail dort setzt)
    contact = payload.get("contact") or {}
    email = contact.get("email")
    if email:
        return email

    # 2) Custom Attributes der Conversation (Pre-Chat Form)
    conv = payload.get("conversation") or payload
    custom = conv.get("custom_attributes") or {}

    # dein Feld: emailAddress
    email = custom.get("emailAddress") or custom.get("email")
    if email:
        return email

    # 3) Fallback: manchmal steckt es im meta.sender
    meta = conv.get("meta") or payload.get("meta") or {}
    sender = meta.get("sender") or {}
    email = sender.get("email")
    return email



def _find_psa_for_conversation(payload: dict) -> Optional[User]:
    email = _extract_email_from_payload(payload)
    if not email:
        current_app.logger.info("no email in webhook payload, cannot find PSA")
        return None

    return _find_psa_by_email(email)


def _extract_referer(payload: dict) -> str | None:
    """
    Versucht, die Herkunfts-URL aus dem Chatwoot-Payload zu ziehen.
    Schaut in mehrere typische Felder.
    """
    conv = payload.get("conversation") or {}
    add = conv.get("additional_attributes") or {}
    meta = conv.get("meta") or {}
    sender = meta.get("sender") or {}
    sender_add = sender.get("additional_attributes") or {}
    custom = conv.get("custom_attributes") or {}
    contact = payload.get("contact") or {}
    contact_add = contact.get("additional_attributes") or {}

    keys_url = (
        "referer",
        "referrer",
        "page_url",
        "website_url",
        "landing_page",
        "url",
    )

    candidates: list[str] = []

    def add_candidate(val):
        if isinstance(val, str) and val.strip():
            candidates.append(val.strip())

    for k in keys_url:
        add_candidate(add.get(k))

    for k in keys_url:
        add_candidate(sender_add.get(k))

    for k in keys_url:
        add_candidate(custom.get(k))

    for k in keys_url:
        add_candidate(contact_add.get(k))

    if candidates:
        current_app.logger.info(
            "resolved referer candidates=%s, chosen=%s",
            candidates,
            candidates[0],
        )
        return candidates[0]

    current_app.logger.info("no referer candidate found in payload")
    return None


def _parse_initiated_at(value: str | None):
    if not value:
        return None
    try:
        # Beispiel-Format: "Tue Mar 03 2020 18:37:38 GMT-0700 (Mountain Standard Time)"
        return datetime.strptime(value[:24], "%a %b %d %Y %H:%M:%S")
    except Exception:
        return None


def handle_conversation_created(payload: dict) -> None:
    """
    Wird vom /webhook-Endpoint für event == conversation_created aufgerufen.

    Unterstützt zwei Payload-Varianten:
    1) Eigener Test:
       {
         "event": "conversation_created",
         "conversation": { "id": ..., "additional_attributes": { "referer": "..." } },
         "contact": {...}
       }

    2) Echtes Chatwoot-Webhook-Format:
       {
         "event": "conversation_created",
         "id": 21,
         "additional_attributes": {
             "referer": "https://...",
             "initiated_at": {...},
             "browser": {...},
             "browser_language": "de",
         },
         "messages": [...],
         "meta": {...},
         ...
       }
    """
    # -------------------------------------------------------------
    # 1) Conversation-Objekt bestimmen (embedded oder top-level)
    # -------------------------------------------------------------
    conv_obj = payload.get("conversation")
    if isinstance(conv_obj, dict):
        conv = conv_obj
    else:
        # Chatwoot schickt bei manchen Events Felder top-level (id, additional_attributes, ...)
        conv = payload

    # 2) Kontakt-Daten (falls vorhanden)
    contact = payload.get("contact") or {}

    # IDs
    conv_id = conv.get("id") or conv.get("display_id") or payload.get("id")
    if not conv_id:
        current_app.logger.info("conversation_created payload without id: %s", payload)
        return

    cw_contact_id = contact.get("id")

    # E-Mail aus Payload extrahieren (nutzt contact/custom/meta)
    email = (_extract_email_from_payload(payload) or "").strip().lower()

    # -------------------------------------------------------------
    # 3) Zusatzattribute: Referer, Browser, Sprache, initiated_at
    # -------------------------------------------------------------
    add_attrs = (
        conv.get("additional_attributes")
        or payload.get("additional_attributes")
        or {}
    ) or {}

    referer = add_attrs.get("referer")

    # initiated_at kann dict oder string sein
    initiated_raw = add_attrs.get("initiated_at")
    initiated_str: str | None = None
    if isinstance(initiated_raw, dict):
        initiated_str = initiated_raw.get("timestamp")
    elif isinstance(initiated_raw, str):
        initiated_str = initiated_raw

    # Browser-/Plattform-Infos aus Chatwoot
    browser = (add_attrs.get("browser") or {}) or {}
    browser_name = browser.get("browser_name")
    platform_name = browser.get("platform_name")
    browser_version = browser.get("browser_version")
    platform_version = browser.get("platform_version")
    browser_language = add_attrs.get("browser_language")

    # Channel (z.B. "Channel::WebWidget")
    channel = conv.get("channel") or payload.get("channel")

    current_app.logger.info(
        "conversation_created: conv_id=%s email=%s referer=%s browser=%s/%s lang=%s initiated_raw=%r",
        conv_id,
        email or None,
        referer,
        browser_name,
        platform_name,
        browser_language,
        initiated_raw,
    )

    # -------------------------------------------------------------
    # 4) PSA & Fallback-Agent bestimmen
    # -------------------------------------------------------------
    psa_user = _find_psa_for_conversation(payload)
    target_user: Optional[User] = None

    if psa_user and getattr(psa_user, "woot_user_id", None):
        # PSA online?
        if _is_agent_online(psa_user.woot_user_id):
            target_user = psa_user
            current_app.logger.info(
                "PSA %s (woot_user_id=%s) is online, assigning conversation %s",
                psa_user.id,
                psa_user.woot_user_id,
                conv_id,
            )
        else:
            current_app.logger.info(
                "PSA %s (woot_user_id=%s) offline for conversation %s, trying fallback",
                psa_user.id,
                psa_user.woot_user_id,
                conv_id,
            )
            fb = _find_fallback_agent(exclude_woot_id=psa_user.woot_user_id)
            if fb and getattr(fb, "woot_user_id", None):
                target_user = fb
                current_app.logger.info(
                    "Using fallback user %s (woot_user_id=%s) for conversation %s",
                    fb.id,
                    fb.woot_user_id,
                    conv_id,
                )
    else:
        current_app.logger.info(
            "no PSA found for conversation %s, trying fallback only",
            conv_id,
        )
        fb = _find_fallback_agent(exclude_woot_id=None)
        if fb and getattr(fb, "woot_user_id", None):
            target_user = fb
            current_app.logger.info(
                "Using fallback user %s (woot_user_id=%s) for conversation %s (no PSA)",
                fb.id,
                fb.woot_user_id,
                conv_id,
            )

    # -------------------------------------------------------------
    # 5) Logging in eigener DB (Log + Origins)
    # -------------------------------------------------------------
    try:
        log = WootConversationLog.query.filter_by(
            cw_conversation_id=conv_id
        ).first()
        if not log:
            log = WootConversationLog(cw_conversation_id=conv_id)
            db.session.add(log)

        log.cw_contact_id = cw_contact_id
        log.email = email or None
        log.referer = referer or None
        log.initiated_at = _parse_initiated_at(initiated_str)

        # NEU: technische Infos
        log.browser_name = browser_name
        log.platform_name = platform_name
        log.browser_version = browser_version
        log.platform_version = platform_version
        log.browser_language = browser_language
        log.channel = channel

        # Routing
        log.psa_user_id = psa_user.id if psa_user else None
        log.assigned_user_id = target_user.id if target_user else None

        # Herkunftsseite separat in woot_conversation_origins loggen
        if referer:
            origin = WootConversationOrigin(
                cw_conversation_id=conv_id,
                page=referer,
                created_at=datetime.utcnow(),
            )
            db.session.add(origin)
            current_app.logger.info(
                "stored origin for conv %s: %s",
                conv_id,
                referer,
            )

        db.session.commit()
    except Exception as e:
        current_app.logger.exception(
            "failed to write WootConversationLog/Origin for %s: %s",
            conv_id,
            e,
        )
        db.session.rollback()

    # -------------------------------------------------------------
    # 6) Assign in Chatwoot (falls wir einen Ziel-User haben)
    # -------------------------------------------------------------
    if not target_user or not getattr(target_user, "woot_user_id", None):
        current_app.logger.info(
            "no target user found for conversation %s, leaving unassigned",
            conv_id,
        )
        return

    _chatwoot_assign_conversation(conv_id, target_user.woot_user_id)
    current_app.logger.info(
        "Assigned conversation %s to user %s (woot_user_id=%s)",
        conv_id,
        target_user.id,
        target_user.woot_user_id,
    )



# ---------------------------------------------------------------------------
# Auswertung Herkunftsseiten
# ---------------------------------------------------------------------------


def get_top_origins(since_ts: int | None, until_ts: int | None) -> list[dict]:
    """
    Aggregiert die häufigsten Herkunftsseiten aus WootConversationOrigin.
    """
    q = db.session.query(
        WootConversationOrigin.page.label("page"),
        func.count().label("cnt"),
    )

    if since_ts:
        q = q.filter(
            WootConversationOrigin.created_at
            >= datetime.utcfromtimestamp(since_ts)
        )
    if until_ts:
        q = q.filter(
            WootConversationOrigin.created_at
            <= datetime.utcfromtimestamp(until_ts)
        )

    q = (
        q.group_by(WootConversationOrigin.page)
        .order_by(func.count().desc())
        .limit(10)
    )

    rows = q.all()
    return [{"page": r.page, "count": int(r.cnt)} for r in rows]



# ... oben vorhandene Imports bleiben

# WICHTIG: WootConversationLog ist ja bereits weiter oben importiert:
# from app.models_extra import CustomerPSA, WootConversationLog, WootConversationOrigin

def get_recent_logs(limit: int = 25) -> list[dict]:
    """
    Liefert die letzten N Konversationen aus woot_conversation_log inkl.
    Browser/OS/Lang + PSA/Assigned. Zusätzlich 'page' (alias für referer).
    """
    try:
        limit_int = int(limit or 25)
    except Exception:
        limit_int = 25

    limit_int = max(1, min(limit_int, 100))

    PSA = aliased(User)
    ASSIGNED = aliased(User)

    q = (
        db.session.query(WootConversationLog, PSA, ASSIGNED)
        .outerjoin(PSA, WootConversationLog.psa_user_id == PSA.id)
        .outerjoin(ASSIGNED, WootConversationLog.assigned_user_id == ASSIGNED.id)
        .order_by(WootConversationLog.created_at.desc())
        .limit(limit_int)
    )

    rows = q.all()
    items: list[dict] = []

    for log, psa, assigned in rows:
        items.append(
            {
                "id": log.id,
                "cw_conversation_id": log.cw_conversation_id,
                "cw_contact_id": log.cw_contact_id,
                "email": log.email,
                "referer": log.referer,
                "page": log.referer,  # Alias für das Frontend
                "initiated_at": log.initiated_at.isoformat() if log.initiated_at else None,
                "browser_name": log.browser_name,
                "platform_name": log.platform_name,
                "browser_version": log.browser_version,
                "platform_version": log.platform_version,
                "browser_language": log.browser_language,
                "channel": log.channel,
                "psa_id": log.psa_user_id,
                "psa_name": (
                    (
                        getattr(psa, "full_name", None)
                        or getattr(psa, "name", None)
                        or getattr(psa, "email", None)
                    )
                    if psa
                    else None
                ),
                "assigned_id": log.assigned_user_id,
                "assigned_name": (
                    (
                        getattr(assigned, "full_name", None)
                        or getattr(assigned, "name", None)
                        or getattr(assigned, "email", None)
                    )
                    if assigned
                    else None
                ),
                "created_at": log.created_at.isoformat()
                if isinstance(log.created_at, datetime)
                else None,
            }
        )

    return items


def cleanup_old_logs(days: int = 30) -> int:
    """
    Löscht alte Einträge aus woot_conversation_log und woot_conversation_origins.
    Gibt die Gesamtanzahl gelöschter Datensätze zurück.
    """
    cutoff = datetime.utcnow() - timedelta(days=max(1, days))

    origins_deleted = (
        db.session.query(WootConversationOrigin)
        .filter(WootConversationOrigin.created_at < cutoff)
        .delete(synchronize_session=False)
    )

    logs_deleted = (
        db.session.query(WootConversationLog)
        .filter(WootConversationLog.created_at < cutoff)
        .delete(synchronize_session=False)
    )

    db.session.commit()
    return int((origins_deleted or 0) + (logs_deleted or 0))