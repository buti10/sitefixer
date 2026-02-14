# app/modules/cooms_visitors/routes.py

from flask import Blueprint, request, jsonify
from datetime import datetime, timedelta
from app.extensions import db
from .models import LiveVisitor
from .geo import lookup_geo

bp_live = Blueprint("live_visitors", __name__, url_prefix="/api/live")


# ----------------------------------------------------------
# Hilfsfunktionen
# ----------------------------------------------------------
def _client_ip() -> str:
    """
    Ermittelt echte Client-IP hinter Caddy/Proxy.
    Nimmt die erste IP aus X-Forwarded-For, sonst remote_addr.
    """
    fwd = request.headers.get("X-Forwarded-For", "")
    if fwd:
        return fwd.split(",")[0].strip()
    return request.remote_addr or "0.0.0.0"


def detect_device(ua: str | None) -> str:
    """
    Grobe Device-Erkennung aus dem User-Agent:
    desktop / mobile / tablet / bot / other
    """
    if not ua:
        return "other"
    u = ua.lower()
    if any(k in u for k in ["bot", "spider", "crawler"]):
        return "bot"
    if "ipad" in u or "tablet" in u:
        return "tablet"
    if "mobile" in u or "iphone" in u or ("android" in u and "mobile" in u):
        return "mobile"
    return "desktop"


def detect_os(ua: str | None) -> str:
    """
    Einfaches OS-Mapping für die Übersicht (optional, nur Aggregation).
    """
    if not ua:
        return "Unbekannt"
    u = ua.lower()
    if "windows" in u:
        return "Windows"
    if "mac os x" in u or "macintosh" in u:
        return "macOS"
    if "iphone" in u or "ipad" in u or "ios" in u:
        return "iOS"
    if "android" in u:
        return "Android"
    if "linux" in u:
        return "Linux"
    return "Unbekannt"


# ----------------------------------------------------------
# CORS für Tracking von WordPress
# (zusätzlich zu globalem CORS in __init__.py)
# ----------------------------------------------------------
@bp_live.after_request
def add_cors_headers(response):
    allowed = [
        "https://staging.sitefixer.de",
        "https://sitefixer.de",
        "https://www.sitefixer.de",
    ]
    origin = request.headers.get("Origin")
    if origin in allowed:
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Headers"] = "Content-Type"
        response.headers["Access-Control-Allow-Methods"] = "POST, GET, OPTIONS"
        response.headers["Access-Control-Allow-Credentials"] = "true"
    return response


@bp_live.route("/track", methods=["OPTIONS"])
def track_options():
    return ("", 200)


# ----------------------------------------------------------
# POST /api/live/track
# Wird vom JS-Snippet auf der WP-Seite aufgerufen
# ----------------------------------------------------------
@bp_live.post("/track")
def track():
    data = request.get_json() or {}

    site = data.get("site") or "main"
    session_id = data.get("session_id")
    url = data.get("url")
    referrer = data.get("referrer")
    ua = data.get("user_agent")
    extra = data.get("extra")

    if not session_id or not url:
        return jsonify({"error": "session_id and url required"}), 400

    ip = _client_ip()
    now = datetime.utcnow()
    device = detect_device(ua)

    v = LiveVisitor.query.filter_by(site=site, session_id=session_id).first()

    if not v:
        country, city = lookup_geo(ip) if ip else (None, None)

        v = LiveVisitor(
            site=site,
            session_id=session_id,
            url=url,
            referrer=referrer,
            user_agent=ua,
            ip=ip,
            country_code=country,
            city=city,
            device_type=device,
            extra=None if extra is None else str(extra),
            first_seen=now,
            last_seen=now,
        )
        db.session.add(v)
    else:
        # bestehende Session aktualisieren
        v.url = url
        if referrer:
            v.referrer = referrer
        if ua:
            v.user_agent = ua
            v.device_type = detect_device(ua)

        v.ip = ip
        v.extra = None if extra is None else str(extra)
        v.last_seen = now

        if not v.country_code and ip:
            v.country_code, v.city = lookup_geo(ip)

    db.session.commit()
    return jsonify({"ok": True})


# ----------------------------------------------------------
# GET /api/live/visitors
# Aggregierte Live-Daten für das Dashboard
# ----------------------------------------------------------
@bp_live.get("/visitors")
def visitors():
    # optional: Zeitfenster & Bots-Steuerung per Query-Param
    try:
        window_minutes = int(request.args.get("window", "2"))
        if window_minutes < 1 or window_minutes > 60:
            window_minutes = 2
    except ValueError:
        window_minutes = 2

    include_bots = request.args.get("bots", "0").lower() in ("1", "true", "yes")

    now = datetime.utcnow()
    window = now - timedelta(minutes=window_minutes)

    q = LiveVisitor.query.filter(LiveVisitor.last_seen >= window)

    if not include_bots:
        q = q.filter(LiveVisitor.device_type != "bot")

    q = q.order_by(LiveVisitor.last_seen.desc())

    visitors = [v.as_dict() for v in q]

    total = len(visitors)
    by_page: dict[str, int] = {}
    by_browser: dict[str, int] = {}
    by_country: dict[str, int] = {}
    by_device: dict[str, int] = {}
    by_os: dict[str, int] = {}

    for v in visitors:
        # Seiten
        url = v["url"] or ""
        by_page[url] = by_page.get(url, 0) + 1

        # Browser
        ua = (v["user_agent"] or "").lower()
        if "chrome" in ua and "edge" not in ua:
            browser = "Chrome"
        elif "firefox" in ua:
            browser = "Firefox"
        elif "safari" in ua and "chrome" not in ua:
            browser = "Safari"
        elif "edge" in ua:
            browser = "Edge"
        else:
            browser = "Andere"
        by_browser[browser] = by_browser.get(browser, 0) + 1

        # Länder
        cc = v.get("country_code") or "Unbekannt"
        by_country[cc] = by_country.get(cc, 0) + 1

        # Geräte
        dt = v.get("device_type") or "other"
        by_device[dt] = by_device.get(dt, 0) + 1

        # Betriebssystem
        os_name = detect_os(v.get("user_agent"))
        by_os[os_name] = by_os.get(os_name, 0) + 1

    return jsonify(
        {
            "total_online": total,
            "visitors": visitors,
            "by_page": by_page,
            "by_browser": by_browser,
            "by_country": by_country,
            "by_device": by_device,
            "by_os": by_os,
            "window_minutes": window_minutes,
            "include_bots": include_bots,
            "last_updated": now.isoformat(),
        }
    )
