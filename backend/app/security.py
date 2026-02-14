# app/security.py
from fastapi import Header, HTTPException
import os

NOCOBASE_SERVICE_TOKEN = os.getenv("NOCOBASE_SERVICE_TOKEN", "")

def require_nocobase_token(authorization: str = Header(default="")):
    # Expect: "Bearer <token>"
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="missing bearer token")
    token = authorization.removeprefix("Bearer ").strip()
    if not NOCOBASE_SERVICE_TOKEN or token != NOCOBASE_SERVICE_TOKEN:
        raise HTTPException(status_code=403, detail="invalid token")
    return True
