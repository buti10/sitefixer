# app/modules/repair/opslog.py
import os, json, time
from typing import Any, Dict
from flask import current_app

def _log_dir() -> str:
    d = current_app.config.get("OPS_LOG_DIR", "/var/www/sitefixer/ops-logs")
    os.makedirs(d, exist_ok=True)
    return d

def log_action(session_id: int, action: str, payload: Dict[str, Any]) -> None:
    rec = {
        "ts": int(time.time()),
        "session_id": session_id,
        "action": action,
        "payload": payload,
    }
    path = os.path.join(_log_dir(), f"session-{session_id}.jsonl")
    with open(path, "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
