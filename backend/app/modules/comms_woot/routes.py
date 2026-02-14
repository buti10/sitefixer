# app/modules/comms_woot/routes.py
from flask import Blueprint, jsonify, request, current_app
from flask_jwt_extended import jwt_required, get_jwt_identity
from app.models import User
from . import services as svc

import hmac
import hashlib
import json
import requests
from app.extensions import db

bp = Blueprint("comms_woot", __name__, url_prefix="/api/comms/woot")


@bp.get("/_conf")
def conf():
    """
    Liefert nur die lokale Konfiguration (ohne Secrets).
    """
    return jsonify(
        {
            "ok": True,
            "base": svc.BASE,
            "account_id": svc.ACC,
            "has_pat": bool(svc.PAT),
            "has_platform": bool(svc.PLAT),
        }
    )


@bp.get("/me")
def me():
    """
    Proxy auf Chatwoot /api/v1/profile
    """
    try:
        data = svc.me_profile()
        return jsonify(data), (data.get("status") or 200)
    except Exception as e:
        current_app.logger.exception("comms_woot /me failed: %s", e)
        return jsonify({"ok": False, "status": 500, "error": str(e)}), 500


@bp.get("/account")
def account():
    """
    Proxy auf /platform/api/v1/accounts/:id
    """
    try:
        acc_id = request.args.get("id", type=int)
        if not acc_id:
            return (
                jsonify(
                    {"ok": False, "status": 400, "error": "query param 'id' required"}
                ),
                400,
            )
        data = svc.account_show(acc_id)
        return jsonify(data), (data.get("status") or 200)
    except Exception as e:
        current_app.logger.exception("comms_woot /account failed: %s", e)
        return jsonify({"ok": False, "status": 500, "error": str(e)}), 500


@bp.get("/reports/inbox")
def reports_inbox_view():
    """
    Proxy auf /api/v2/accounts/:id/summary_reports/inbox
    """
    try:
        since = request.args.get("since", type=int)
        until = request.args.get("until", type=int)
        business_hours = request.args.get("business_hours", "false").lower() == "true"

        if since is None or until is None:
            return (
                jsonify(
                    {
                        "ok": False,
                        "status": 400,
                        "error": "since & until (unix timestamp) required",
                    }
                ),
                400,
            )

        data = svc.reports_inbox(
            since=since,
            until=until,
            business_hours=business_hours,
        )
        return jsonify(data), (data.get("status") or 200)
    except Exception as e:
        current_app.logger.exception("comms_woot /reports/inbox failed: %s", e)
        return jsonify({"ok": False, "status": 500, "error": str(e)}), 500


@bp.get("/sso-link")
@jwt_required()
def woot_sso_link():
    """
    Liefert einen einmaligen Login-Link für den aktuell eingeloggten Benutzer,
    basierend auf dessen User.woot_user_id.
    """
    uid = int(get_jwt_identity())
    u = User.query.get_or_404(uid)

    if not u.woot_user_id:
        return jsonify(
            {
                "ok": False,
                "status": 400,
                "error": "woot_user_id missing on user",
            }
        ), 400

    base = current_app.config.get("WOOT_BASE", "https://chat.sitefixer.de")
    token = current_app.config.get("WOOT_PLATFORM_TOKEN")

    if not token:
        return jsonify(
            {
                "ok": False,
                "status": 500,
                "error": "platform token missing",
            }
        ), 500

    # RICHTIGER Endpoint laut Doku:
    # GET /platform/api/v1/users/{id}/login
    url = f"{base}/platform/api/v1/users/{u.woot_user_id}/login"

    try:
        r = requests.get(
            url,
            headers={"api_access_token": token},
            timeout=5,
        )
    except Exception as e:
        return jsonify(
            {
                "ok": False,
                "status": 502,
                "error": f"platform request failed: {e}",
            }
        ), 502

    if r.status_code != 200:
        return jsonify(
            {
                "ok": False,
                "status": r.status_code,
                "error": r.text,
            }
        ), 502

    data = r.json()
    login_url = data.get("url")
    if not login_url:
        return jsonify(
            {
                "ok": False,
                "status": 500,
                "error": "no url returned from platform",
            }
        ), 500

    return jsonify({"ok": True, "url": login_url})


def _verify_woot_signature(raw_body: bytes, signature: str | None) -> bool:
    """
    Optional: Webhook-Signatur von Chatwoot prüfen.
    In Chatwoot -> Webhooks -> Secret konfigurieren -> WOOT_WEBHOOK_SECRET.
    """
    secret = current_app.config.get("WOOT_WEBHOOK_SECRET")
    if not secret:
        # Keine Prüfung konfiguriert
        return True
    if not signature:
        return False
    mac = hmac.new(secret.encode("utf-8"), msg=raw_body, digestmod=hashlib.sha256)
    expected = mac.hexdigest()
    # Chatwoot sendet normalerweise hex-String, ggf. anpassen falls anders
    return hmac.compare_digest(expected, signature)


@bp.post("/webhook")
def woot_webhook():
    """
    Nimmt Webhooks von Chatwoot entgegen.
    Reagiert aktuell auf:
      - conversation_created
      - webwidget_triggered
    und loggt jeden Payload.
    """
    raw = request.get_data()

    try:
        payload = json.loads(raw.decode("utf-8"))
    except Exception:
        return jsonify({"ok": False, "error": "invalid json"}), 400

    event = payload.get("event")
    current_app.logger.info("woot webhook event=%s payload=%s", event, payload)

    # Falls du später ein Secret in Chatwoot setzt, kannst du hier _verify_woot_signature nutzen
    # sig = request.headers.get("X-Chatwoot-Signature")
    # if not _verify_woot_signature(raw, sig):
    #     current_app.logger.warning("invalid Chatwoot signature")
    #     return jsonify({"ok": False, "error": "invalid signature"}), 403

    if event in ("conversation_created", "webwidget_triggered"):
        try:
            svc.handle_conversation_created(payload)
        except Exception as e:
            current_app.logger.exception("handle_conversation_created failed: %s", e)
            # Immer 200, damit Chatwoot nicht Spam-Logs produziert
            return jsonify({"ok": False}), 200

    return jsonify({"ok": True}), 200


@bp.get("/reports/origins")
@jwt_required()
def origins_report():
    """
    Liefert Top-Herkunftsseiten aus unserer eigenen Tabelle woot_conversation_origins.
    Aggregation macht services.get_top_origins().
    """
    since = request.args.get("since", type=int)
    until = request.args.get("until", type=int)

    try:
        items = svc.get_top_origins(since, until)
        return jsonify({"ok": True, "items": items})
    except Exception as e:
        current_app.logger.exception("comms_woot /reports/origins failed: %s", e)
        # lieber 200 mit ok=False zurückgeben, damit das Frontend nicht komplett kaputt ist
        return jsonify({"ok": False, "items": [], "error": "internal error"}), 200


@bp.get("/logs/recent")
@jwt_required()
def recent_logs():
    limit = request.args.get("limit", type=int) or 20
    try:
        items = svc.get_recent_logs(limit)
        return jsonify({"ok": True, "items": items})
    except Exception as e:
        current_app.logger.exception("comms_woot /logs/recent failed: %s", e)
        return jsonify({"ok": False, "items": [], "error": "internal error"}), 200


@bp.delete("/logs/cleanup")
@jwt_required()
def cleanup_logs():
    """
    Löscht Chat-Logs und Origins, die älter als X Tage sind (Default: 30).
    """
    days = request.args.get("days", 30, type=int) or 30

    try:
        deleted = svc.cleanup_old_logs(days)
        return jsonify({"ok": True, "deleted": deleted, "days": days})
    except Exception as e:
        current_app.logger.exception("comms_woot /logs/cleanup failed: %s", e)
        return jsonify({"ok": False, "deleted": 0, "error": "internal error"}), 200
