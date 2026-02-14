from __future__ import annotations

import re
from typing import Dict, Tuple


MASK = "****MASKED****"


def mask_wp_config(text: str) -> Tuple[str, Dict[str, int]]:
    """
    Masks DB_PASSWORD and auth keys/salts in wp-config.php output.
    Does NOT change remote file, only API output.
    """
    stats = {"db_password": 0, "salts": 0}

    # DB_PASSWORD
    pat_db = re.compile(r"(define\(\s*['\"]DB_PASSWORD['\"]\s*,\s*)['\"][^'\"]*['\"](\s*\)\s*;)", re.IGNORECASE)
    text, n = pat_db.subn(r"\1'" + MASK + r"'\2", text)
    stats["db_password"] += n

    # AUTH/SALT keys
    key_names = [
        "AUTH_KEY","SECURE_AUTH_KEY","LOGGED_IN_KEY","NONCE_KEY",
        "AUTH_SALT","SECURE_AUTH_SALT","LOGGED_IN_SALT","NONCE_SALT",
    ]
    for k in key_names:
        pat = re.compile(r"(define\(\s*['\"]" + re.escape(k) + r"['\"]\s*,\s*)['\"][^'\"]*['\"](\s*\)\s*;)", re.IGNORECASE)
        text, n2 = pat.subn(r"\1'" + MASK + r"'\2", text)
        stats["salts"] += n2

    return text, stats


def apply_masking(path: str, text: str) -> Tuple[str, Dict[str, int]]:
    p = (path or "").lower()
    if p.endswith("wp-config.php"):
        return mask_wp_config(text)
    return text, {}
