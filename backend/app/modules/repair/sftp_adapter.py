# app/scanner/sftp_adapter.py
# Liefert den vorhandenen paramiko.SFTPClient zu einer SID aus deinen bestehenden Routen.
from typing import Any, Optional


def get_client_by_sid(sid: str) -> Optional[Any]:
    from app.scanner.routes import sftp_routes as R  # passe an, falls anderer Pfad
    fn = getattr(R, "get_client_by_sid", None)
    if callable(fn):
        return fn(sid)
    for name in ("SFTP_SESSIONS","SESSIONS","POOL","CLIENTS"):
        d = getattr(R, name, None)
        if isinstance(d, dict) and sid in d:
            obj = d[sid]
            return getattr(obj, "sftp", None) or getattr(obj, "client", None) or getattr(obj, "sftp_client", None) or obj
    return None
    return None
