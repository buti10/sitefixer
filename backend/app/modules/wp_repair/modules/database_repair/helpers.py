from __future__ import annotations

import posixpath
import re
from typing import Any, Dict, Optional, Tuple


_RE_WP_ALLOW = re.compile(
    r"define\(\s*['\"]WP_ALLOW_REPAIR['\"]\s*,\s*(true|false|1|0)\s*\)\s*;?",
    re.IGNORECASE,
)

_RE_TABLE_PREFIX = re.compile(r"\$table_prefix\s*=\s*['\"]([^'\"]+)['\"]\s*;")


def _exists(sftp, path: str) -> bool:
    try:
        sftp.stat(path)
        return True
    except Exception:
        return False


def find_wp_config_path(sftp, wp_root: str) -> Optional[str]:
    """Locate wp-config.php (common locations).

    - <wp_root>/wp-config.php
    - <wp_root>/../wp-config.php
    """
    wp_root = posixpath.normpath(wp_root)
    p1 = posixpath.join(wp_root, "wp-config.php")
    if _exists(sftp, p1):
        return p1

    parent = posixpath.dirname(wp_root.rstrip("/"))
    if parent and parent != "/":
        p2 = posixpath.join(parent, "wp-config.php")
        if _exists(sftp, p2):
            return p2

    return None


def read_remote_text(sftp, path: str, max_bytes: int = 2_000_000) -> str:
    f = sftp.open(path, "r")
    try:
        data = f.read(max_bytes)
        if isinstance(data, bytes):
            return data.decode("utf-8", errors="replace")
        return str(data)
    finally:
        try:
            f.close()
        except Exception:
            pass


def parse_wp_config_info(wp_config_text: str) -> Dict[str, Any]:
    """Extract a few safe-to-return details from wp-config.php."""
    m = _RE_WP_ALLOW.search(wp_config_text or "")
    allow_val = None
    if m:
        v = (m.group(1) or "").strip().lower()
        allow_val = v in {"true", "1"}

    m2 = _RE_TABLE_PREFIX.search(wp_config_text or "")
    table_prefix = m2.group(1) if m2 else None

    return {
        "wp_allow_repair_defined": bool(m),
        "wp_allow_repair_value": allow_val,
        "table_prefix": table_prefix,
    }


def ensure_site_base_url(domain_or_url: str) -> str:
    """Return a normalized base URL (no trailing slash).

    Accepts:
    - example.com
    - https://example.com
    - https://example.com/some/path  (path will be kept)
    """
    s = (domain_or_url or "").strip()
    if not s:
        return ""

    # If already has scheme, keep it.
    if s.startswith("http://") or s.startswith("https://"):
        return s.rstrip("/")

    return ("https://" + s).rstrip("/")


def build_repair_url(base_url: str) -> str:
    base = (base_url or "").rstrip("/")
    return base + "/wp-admin/maint/repair.php"


def patch_enable_wp_allow_repair(wp_config_text: str) -> Tuple[str, bool]:
    """Ensure WP_ALLOW_REPAIR is enabled.

    Returns: (patched_text, changed)
    """
    txt = wp_config_text or ""

    m = _RE_WP_ALLOW.search(txt)
    if m:
        # Already defined -> set to true
        cur = (m.group(1) or "").strip().lower()
        if cur in {"true", "1"}:
            return txt, False

        patched = _RE_WP_ALLOW.sub("define('WP_ALLOW_REPAIR', true);", txt, count=1)
        return patched, True

    # Insert shortly after opening PHP tag.
    ins = "define('WP_ALLOW_REPAIR', true);\n"
    if "<?php" in txt:
        patched = txt.replace("<?php", "<?php\n" + ins, 1)
        return patched, True

    # Worst-case: prepend.
    return "<?php\n" + ins + txt, True
