import time
import secrets
from dataclasses import dataclass
from typing import Dict, Any, Optional

@dataclass
class Session:
    sid: str
    created_at: float
    expires_at: float
    data: Dict[str, Any]

class InMemoryTTLStore:
    def __init__(self):
        self._sessions: Dict[str, Session] = {}

    def create(self, data: Dict[str, Any], ttl_seconds: int = 1800) -> str:
        sid = secrets.token_urlsafe(24)
        now = time.time()
        self._sessions[sid] = Session(
            sid=sid,
            created_at=now,
            expires_at=now + ttl_seconds,
            data=data,
        )
        return sid

    def get(self, sid: str) -> Optional[Session]:
        s = self._sessions.get(sid)
        if not s:
            return None
        if time.time() > s.expires_at:
            self._sessions.pop(sid, None)
            return None
        return s

    def delete(self, sid: str) -> None:
        self._sessions.pop(sid, None)

store = InMemoryTTLStore()
