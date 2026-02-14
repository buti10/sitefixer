import os, json, mimetypes, time
from typing import Any, Dict, List, Optional
import requests
from requests.auth import HTTPBasicAuth

# ── Konfiguration ──────────────────────────────────────────────────────────────
_API_URL  = os.environ.get("LHC_API_URL",  "https://chat.sitefixer.de/index.php/site_admin/restapi").rstrip("/")
_API_USER = os.environ.get("LHC_API_USER", "").strip()
_API_KEY  = os.environ.get("LHC_API_KEY",  "").strip()
_TIMEOUT  = float(os.environ.get("LHC_API_TIMEOUT", "10"))
_MOCK     = (os.environ.get("LHC_MOCK", "0") == "1")

if not _MOCK:
    if not _API_URL or "/restapi" not in _API_URL:
        raise RuntimeError(f"LHC_API_URL invalid: '{_API_URL}' (erwartet Pfad .../site_admin/restapi)")
    if not _API_USER or not _API_KEY:
        raise RuntimeError("LHC_API_USER / LHC_API_KEY fehlen – bitte .env korrekt setzen.")


# ── Fehlerklasse ───────────────────────────────────────────────────────────────
class LHCError(RuntimeError):
    pass

_session = requests.Session()
_session.headers.update({
    "Accept": "application/json",
    "User-Agent": "curl/8.5.0",
})

def _auth():
    return HTTPBasicAuth(_API_USER, _API_KEY)

def _url(path: str) -> str:
    return f"{_API_URL}/{path.lstrip('/')}"

def _json_or_error(r: requests.Response, path: str):
    if r.status_code >= 400:
        # Inhalt kürzen, um Log zu schonen
        text_short = (r.text or "")[:400]
        raise LHCError(f"{r.request.method} {path} -> {r.status_code} {text_short}")
    ct = r.headers.get("content-type","")
    if "application/json" in ct:
        data = r.json()
    else:
        # Manche 503 liefern HTML
        raise LHCError(f"{r.request.method} {path} -> Non-JSON response: {(r.text or '')[:400]}")
    if isinstance(data, dict) and data.get("error") is True:
        raise LHCError(f"LHC error on {path}: {data.get('r') or data.get('result') or data}")
    return data

def _get(path, params=None, retries: int = 2, backoff: float = 0.5):
    last = None
    for i in range(retries + 1):
        r = _session.get(_url(path), params=params, auth=_auth(), timeout=_TIMEOUT)
        try:
            return _json_or_error(r, path)
        except LHCError as e:
            last = e
            # 503 / Wartungsseite → kurz backoff und nochmal
            if "503" in str(e) and i < retries:
                time.sleep(backoff * (i+1))
                continue
            raise
    if last:
        raise last

def _post(path: str, data: Optional[Dict[str, Any]] = None, files: Optional[Dict[str, Any]] = None, retries: int = 1):
    for i in range(retries + 1):
        r = _session.post(_url(path), data=data, files=files, auth=_auth(), timeout=_TIMEOUT)
        try:
            return _json_or_error(r, path)
        except LHCError as e:
            if "503" in str(e) and i < retries:
                time.sleep(0.5 * (i+1))
                continue
            raise

# ── Health / Whoami / Conf ────────────────────────────────────────────────────
def lhc_health() -> Dict[str, Any]:
    if _MOCK:
        return {"isonline": True, "mock": True}
    return _get("isonline")

def lhc_whoami():
    # Manche LHC liefern hier nur HTML → nimm isonline + User zurück
    try:
        _ = _get("whoami")
        return {"ok": True, "isonline": True, "user": _API_USER}
    except Exception:
        return {"ok": True, "isonline": True, "user": _API_USER}

def lhc_conf():
    return {"url": _API_URL, "user": _API_USER, "key_set": bool(_API_KEY)}

# ── Inbox (pending/active) ────────────────────────────────────────────────────
def lhc_inbox(limit: int = 50, since: Optional[int] = None, _force_mock: bool = False) -> Dict[str, Any]:
    if _MOCK or _force_mock:
        items = [
            {"id": 101, "chat_id": 101, "from": "visitor-101", "text": "Hallo?", "time": 1730000000, "files": []},
            {"id": 102, "chat_id": 102, "from": "visitor-102", "text": "Brauche Hilfe", "time": 1730000600, "files": []},
        ]
        return {"items": items[:limit], "next_since": (since or 0) + len(items[:limit])}

    params = {
        "limit": max(1, min(200, limit)),
        "status_ids[]": ["0","1"],
        "sort": "id_desc"
    }
    raw = _get("chats", params=params)
    # Normalisieren
    def _map(c: Dict[str, Any]) -> Dict[str, Any]:
        last_msg = ""
        lm = c.get("last_msg") or c.get("last_message")
        if isinstance(lm, dict):
            last_msg = lm.get("msg") or ""
        elif isinstance(lm, str):
            last_msg = lm
        ts = c.get("time") or c.get("last_user_msg_time") or c.get("pnd_time") or c.get("updtime")
        return {
            "id": int(c.get("id")),
            "chat_id": int(c.get("id")),
            "from": c.get("nick") or c.get("user") or "visitor",
            "text": last_msg or c.get("msg") or "",
            "time": int(ts) if ts else None,
            "files": []
        }
    items_src = raw if isinstance(raw, list) else raw.get("list") or raw.get("items") or []
    items = [_map(c) for c in items_src]
    return {"items": items, "next_since": None}

# ── Chat annehmen (versch. LHC-Builds) ────────────────────────────────────────
def lhc_accept(chat_id: int) -> Dict[str, Any]:
    data = {"chat_id": chat_id}
    return _post("accept", data=data)

# ── Nachrichten lesen ─────────────────────────────────────────────────────────
def lhc_messages(chat_id: int) -> List[Dict[str, Any]]:
    if _MOCK:
        return [
            {"id": 1, "user": "visitor", "msg": "Hi", "time": 1730000000},
            {"id": 2, "user": "operator", "msg": "Hallo, wie kann ich helfen?", "time": 1730000100},
        ]
    # Versuche in Reihenfolge: detail → messages → messages_plain
    data = _get(f"chat/{chat_id}")
    msgs = []
    if isinstance(data, dict):
        for key in ("messages", "msg", "messages_plain"):
            v = data.get(key)
            if isinstance(v, list):
                msgs = v
                break
    out = []
    for m in msgs:
        if isinstance(m, dict):
            out.append({
                "id": int(m.get("id", 0)),
                "user": m.get("user") or m.get("name") or m.get("from") or "unknown",
                "msg": m.get("msg") or m.get("text") or "",
                "time": int(m.get("time") or m.get("ts") or 0),
            })
        else:
            out.append({"id": 0, "user": "unknown", "msg": str(m), "time": 0})
    return out

# ── Nachricht senden (für deine Instanz) ──────────────────────────────────────
def lhc_send(chat_id: int, text: str) -> Dict[str, Any]:
    data = {"chat_id": chat_id, "msg": text}
    return _post("addmsgadmin", data=data)

# ── Datei Upload (unverändert) ────────────────────────────────────────────────
def lhc_upload(chat_id: int, filepath: str) -> Dict[str, Any]:
    if _MOCK:
        return {"ok": True, "file": filepath, "mock": True}
    mime = mimetypes.guess_type(filepath)[0] or "application/octet-stream"
    with open(filepath, "rb") as f:
        files = {"file": (os.path.basename(filepath), f, mime)}
        return _post(f"chat/{chat_id}/upload", files=files)
