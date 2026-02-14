# app/modules/comms_chat/routes.py
from flask import Blueprint, request, jsonify
from typing import Any, Dict, List, Optional

from .svc_lhc import (
    lhc_inbox, lhc_accept, lhc_messages, lhc_send, lhc_upload,
    lhc_health, lhc_whoami, lhc_conf, LHCError
)

import logging
# --- Zeitformat-Helper ---
from datetime import datetime, timezone
def _ts_iso_unix(v):
    try:
        v = int(v)
        return datetime.fromtimestamp(v, tz=timezone.utc).isoformat()
    except Exception:
        return None

log = logging.getLogger("comms_chat")

bp = Blueprint("comms_chat", __name__, url_prefix="/api/comms/chat")

# ── Helpers ───────────────────────────────────────────────────────────────────
def _ok(data): 
    return jsonify(data), 200

def _err(e: Exception):
    code = 502 if isinstance(e, LHCError) else 500
    log.exception("comms_chat error: %s", e)
    return jsonify({"error": str(e)}), code


def _filter_since_id(items: List[Dict[str, Any]], last: Optional[int]) -> List[Dict[str, Any]]:
    if not last:
        return items
    out = []
    for m in items:
        try:
            mid = int(m.get("id") or 0)
        except Exception:
            mid = 0
        if mid > last:
            out.append(m)
    return out

# ── Endpoints ─────────────────────────────────────────────────────────────────
@bp.route("/inbox", methods=["GET"])
def inbox():
    """
    Query:
      limit: 1..200 (default 50)
      since: unix (optional)
      mock:  '1' => erzwingt Mock-Antwort (zum Testen, unabhängig von LHC_MOCK)
    Response:
      { items:[{id,chat_id,frm,txt,ts_iso,files:[]}], next_since }
    """
    try:
        limit = max(1, min(200, request.args.get("limit", default=50, type=int)))
        since = request.args.get("since", type=int)
        force_mock = (request.args.get("mock", "0") == "1")

        raw = lhc_inbox(limit=limit, since=since, _force_mock=force_mock)

        def _map(m):
            return {
                "id": m.get("id"),
                "chat_id": m.get("chat_id") or m.get("chatid"),
                "frm": m.get("from") or m.get("user"),
                "txt": m.get("text") or m.get("msg") or "",
                "ts_iso": _ts_iso_unix(m.get("time") or m.get("ts")),
                "files": m.get("files") or [],
            }

        items_src = (raw.get("items") if isinstance(raw, dict) else raw) or []
        items = [_map(m) for m in items_src]
        next_since = raw.get("next_since") if isinstance(raw, dict) else None
        return _ok({"items": items, "next_since": next_since})
    except Exception as e:
        return _err(e)


@bp.post("/accept")
def accept():
    try:
        data = request.get_json(silent=True) or {}
        chat_id = int(data.get("chat_id", 0))
        if not chat_id:
            return jsonify({"error": "chat_id required"}), 400
        lhc_accept(chat_id)
        return _ok({"ok": True})
    except Exception as e:
        return _err(e)

@bp.get("/<int:chat_id>/messages")
def messages(chat_id: int):
    try:
        items = lhc_messages(chat_id)
        # Optional inkrementell: /messages?last=<id>
        last = request.args.get("last")
        last_int = int(last) if last and last.isdigit() else None
        if last_int:
            items = _filter_since_id(items, last_int)
        return _ok({"items": items})
    except Exception as e:
        return _err(e)

@bp.post("/send")
def send():
    try:
        data = request.form if request.form else (request.get_json(silent=True) or {})
        chat_id = int(data.get("chat_id", 0))
        text = (data.get("text") or "").strip()
        if not chat_id or not text:
            return jsonify({"error": "chat_id and text required"}), 400
        return _ok(lhc_send(chat_id, text))
    except Exception as e:
        return _err(e)

# --- Debug ---
@bp.get("/_debug/health")
def dbg_health():
    try:
        return _ok(lhc_health())
    except Exception as e:
        return _err(e)

@bp.get("/_debug/raw")
def dbg_raw():
    try:
        return _ok(lhc_inbox(limit=20))
    except Exception as e:
        return _err(e)

    
@bp.route("/health", methods=["GET"])
def health():
    try:
        info = lhc_health()  # <— keine Argumente!
        return _ok({"ok": True, "lhc": info})
    except Exception as e:
        return _err(e)
    
@bp.get("/_diag")
def diag():
    try:
        from .svc_lhc import _API_URL
        return _ok({"api_url": _API_URL})
    except Exception as e:
        return _err(e)

@bp.get("/_debug/whoami")
def dbg_whoami():
    try:
        from .svc_lhc import lhc_whoami
        return _ok(lhc_whoami())
    except Exception as e:
        return _err(e)

@bp.get("/_debug/conf")
def dbg_conf():
    try:
        from .svc_lhc import lhc_conf
        return _ok(lhc_conf())
    except Exception as e:
        return _err(e)


