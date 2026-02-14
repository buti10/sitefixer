from __future__ import annotations
import json
import time
from typing import Dict, Any
import redis

REDIS_URL = "redis://127.0.0.1:6379/0"
PREFIX = "wp_repair:session:"
TTL_SECONDS = 60 * 60  # 1 Stunde

_r = redis.Redis.from_url(REDIS_URL, decode_responses=True)


def set_session(session_id: str, data: Dict[str, Any]) -> None:
    key = PREFIX + session_id
    payload = dict(data)
    payload["_ts"] = int(time.time())
    _r.setex(key, TTL_SECONDS, json.dumps(payload))


def get_session(session_id: str) -> Dict[str, Any] | None:
    raw = _r.get(PREFIX + session_id)
    if not raw:
        return None
    return json.loads(raw)


def delete_session(session_id: str) -> None:
    _r.delete(PREFIX + session_id)
