# app/modules/comms_chat/svc_lhc.py
from typing import Any, Dict, List, Optional, Union
import os, logging, time
import requests
from requests.auth import HTTPBasicAuth
from werkzeug.utils import secure_filename

MOCK = os.getenv("LHC_MOCK") == "1"
log = logging.getLogger(__name__)

# ── Einheitliche ENV-Variablen ────────────────────────────────────────────────
# LHC_ORIGIN z.B. https://chat.sitefixer.de   (OHNE trailing slash)
# Wir hängen den REST-Pfad immer selbst an.
LHC_ORIGIN = os.getenv("LHC_ORIGIN", "https://chat.sitefixer.de").rstrip("/")
LHC_USER   = os.getenv("LHC_USER", "")
LHC_PASS   = os.getenv("LHC_PASS", "")
TIMEOUT    = int(os.getenv("LHC_TIMEOUT", "15"))

if not LHC_USER or not LHC_PASS:
    log.warning("LHC_USER / LHC_PASS nicht gesetzt – Basic Auth könnte scheitern.")

BASE = f"{LHC_ORIGIN}/index.php/restapi"
AUTH = HTTPBasicAuth(LHC_USER, LHC_PASS)
HDRS = {"Accept": "application/json"}

class LHCError(RuntimeError):
    def __init__(self, where: str, resp: Optional[requests.Response] = None, msg: str = ""):
        detail = f"{where}: {msg}"
        if resp is not None:
            body = (resp.text or "")[:400]
            detail += f" | status={resp.status_code} | url={resp.url} | body={body}"
        super().__init__(detail)

def _url(path: str) -> str:
    return f"{BASE}/{path.lstrip('/')}"

def _req(method: str, path: str, **kw) -> requests.Response:
    try:
        r = requests.request(method, _url(path), auth=AUTH, headers=HDRS, timeout=TIMEOUT, **kw)
    except requests.RequestException as e:
        raise LHCError(f"{method} {_url(path)}", None, repr(e))
    if not r.ok:
        raise LHCError(f"{method} {_url(path)}", r, "http error")
    return r

# ── Health/Debug ──────────────────────────────────────────────────────────────
def lhc_health(timeout: float = 3.0) -> Dict[str, Any]:
    if MOCK:
        return {"version": "mock", "time": "now"}
    # timeout wird von _req bereits respektiert, wenn übergeben
    return _req("GET", "health", timeout=timeout).json() or {"ok": True}
    
def lhc_raw_chats(params=None) -> Any:
    return _req("GET", "chats", params=params or {"limit": 10}).json()

# ── Helpers ───────────────────────────────────────────────────────────────────
def _to_iso(ts: Any) -> Optional[str]:
    try:
        if ts in (None, "", 0, "0"):
            return None
        # LHC liefert meist Unix-Sekunden
        return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(int(ts)))
    except Exception:
        return None

def _list_from(payload: Union[dict, list]) -> list:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        return (
            payload.get("result", {}).get("messages")
            or payload.get("messages")
            or payload.get("items")
            or payload.get("list")
            or payload.get("msg")
            or []
        )
    return []

# ── API Adapter ───────────────────────────────────────────────────────────────
def lhc_inbox() -> List[Dict[str, Any]]:
    """
    Liefert eine generische Liste offener/letzter Chats.
    Wir normalisieren nur „leicht“, das Frontend kann verfeinern.
    """
    js = _req("GET", "chats", params={"limit": 50, "offset": 0}).json()
    rows = js if isinstance(js, list) else js.get("items") or js.get("list") or []

    out: List[Dict[str, Any]] = []
    for it in rows:
        cid = it.get("id") or it.get("chat_id")
        # Status kann als Zahl, Label oder Text kommen
        _val = it.get("status_label")
if _val is None:
    _val = it.get("status")
raw_status = ("" if _val is None else str(_val)).strip().lower()

        # message_count: mehrere Feldnamen möglich
        unread = (
            it.get("has_unread_messages")
            or it.get("has_unread_op_messages")
            or it.get("unread_messages")
            or 0
        )

        out.append({
            "id": int(cid) if cid is not None else None,
            "visitor": it.get("nick") or it.get("email") or "Visitor",
            "page": it.get("referrer") or it.get("link") or it.get("department_name") or "",
            "status": raw_status,                  # Frontend mappt auf waiting/active/open/closed
            "message_count": int(unread) if str(unread).isdigit() else 0,
            "waiting_since": _to_iso(it.get("time") or it.get("time_created") or it.get("time_created_front")),
            "operator": it.get("operator") or it.get("name_support") or None,
            "pending": it.get("pending") or it.get("pnd") or None,
        })
    return out

def lhc_accept(chat_id: int) -> None:
    # 1 == active; setzt den Chat auf „Operator hat übernommen“
    _req("POST", "setchatstatus", data={"chat_id": str(chat_id), "status": "1"})

def lhc_messages(chat_id: int) -> List[Dict[str, Any]]:
    """
    Holt alle Messages des Chats und normalisiert in unser
    Frontend-Format. Keine Nullfelder für Text/Zeiten.
    """
    # A) direkte Nachrichtenliste
    p = _req("GET", "fetchchatmessages", params={"chat_id": str(chat_id)}).json()
    items = _list_from(p)
    if not items:
        # B) Fallback über Chat-Objekt mit Messages
        q = _req("GET", "fetchchat", params={"chat_id": str(chat_id), "include_messages": 1}).json()
        if isinstance(q, dict):
            items = (
                q.get("chat", {}).get("messages")
                or q.get("messages")
                or q.get("result", {}).get("messages")
                or []
            )
        elif isinstance(q, list):
            items = q

    out: List[Dict[str, Any]] = []
    for m in items:
        if not isinstance(m, dict):
            continue
        mid = m.get("id") or m.get("msg_id")
        txt = m.get("msg") or m.get("message") or ""
        uid = m.get("user_id")
        when = m.get("time") or m.get("time_created") or m.get("time_iso")
        author = "agent" if (uid or 0) > 0 or m.get("sender") == "operator" or m.get("name_support") else "visitor"

        out.append({
            "id": str(mid) if mid is not None else "",
            "author": author,
            "text": str(txt),
            "sentAt": _to_iso(when),
            "deliveredAt": _to_iso(when),
            "readAt": None,     # LHC liefert hier nichts Verlässliches
            "attachments": [],
        })
    return out

def lhc_send(chat_id: int, text: str) -> Dict[str, Any]:
    _req("POST", "addmsgadmin", data={"chat_id": str(chat_id), "msg": text, "sender": "operator"})
    now = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    return {"deliveredAt": now}

def lhc_upload(chat_id: int, file_storage):
    name = secure_filename(file_storage.filename)
    files = {"files": (name, file_storage.stream, file_storage.mimetype or "application/octet-stream")}
    return _req("POST", "file", files=files, data={"chat_id": str(chat_id)}).json()
