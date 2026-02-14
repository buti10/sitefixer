from __future__ import annotations

import base64
import os
from typing import Optional

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


class CryptoError(Exception):
    pass


def _key() -> bytes:
    b64 = os.getenv("SF_TICKET_ENC_KEY_B64", "").strip()
    if not b64:
        raise CryptoError("Missing SF_TICKET_ENC_KEY_B64")
    k = base64.b64decode(b64)
    if len(k) != 32:
        raise CryptoError("SF_TICKET_ENC_KEY_B64 must decode to 32 bytes")
    return k


def encrypt_to_b64(plaintext: Optional[str]) -> Optional[str]:
    if plaintext is None:
        return None
    s = str(plaintext)
    if not s:
        return None
    aes = AESGCM(_key())
    nonce = os.urandom(12)
    ct = aes.encrypt(nonce, s.encode("utf-8"), None)
    return base64.b64encode(nonce + ct).decode("ascii")


def decrypt_from_b64(value: Optional[str]) -> str:
    if value is None:
        return ""
    s = str(value).strip()
    if not s:
        return ""

    raw = base64.b64decode(s)
    if len(raw) < 12 + 16:
        # nonce(12) + tag(16) minimum
        return ""

    nonce = raw[:12]
    ct = raw[12:]

    aes = AESGCM(_key())
    pt = aes.decrypt(nonce, ct, None)
    return pt.decode("utf-8", errors="replace")
