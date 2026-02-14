from __future__ import annotations

import posixpath
import stat
from typing import Any, Dict, List

from ..sftp.connect import sftp_connect


DROPIN_FILES = [
    "object-cache.php",     # P1
    "advanced-cache.php",   # P1
    "db.php",               # P2 (nur optional)
    "sunrise.php",          # P2 (nur optional)
]

P1_DEFAULT = ["object-cache.php", "advanced-cache.php"]
P2_RISKY = ["db.php", "sunrise.php"]


def _safe_read_head(sftp, path: str, max_bytes: int = 4096) -> str:
    try:
        f = sftp.open(path, "r")
        try:
            data = f.read(max_bytes)
            if isinstance(data, bytes):
                return data.decode("utf-8", errors="replace")
            return str(data)
        finally:
            f.close()
    except Exception:
        return ""


def _fingerprint(text: str) -> Dict[str, Any]:
    t = (text or "").lower()
    hints: List[str] = []
    if "redis" in t:
        hints.append("redis")
    if "memcached" in t:
        hints.append("memcached")
    if "w3 total cache" in t or "w3tc" in t:
        hints.append("w3tc")
    if "wp super cache" in t:
        hints.append("wp-super-cache")
    if "litespeed" in t:
        hints.append("litespeed")
    if "batcache" in t:
        hints.append("batcache")
    if "hyperdb" in t:
        hints.append("hyperdb")
    if "domain mapping" in t or "sunrise" in t:
        hints.append("domain-mapping/sunrise")

    # first few non-empty lines
    lines = []
    for ln in (text or "").splitlines():
        ln = ln.strip()
        if not ln:
            continue
        lines.append(ln[:200])
        if len(lines) >= 5:
            break

    return {"hints": hints, "head_lines": lines}


def dropins_preview(
    host: str,
    port: int,
    username: str,
    password: str,
    wp_root: str,
) -> Dict[str, Any]:
    wp_root = posixpath.normpath(wp_root)
    wp_content = posixpath.join(wp_root, "wp-content")

    client = sftp_connect(host, port, username, password)
    sftp = client.open_sftp()
    try:
        items: List[Dict[str, Any]] = []
        for name in DROPIN_FILES:
            p = posixpath.join(wp_content, name)
            try:
                st = sftp.stat(p)
                is_file = stat.S_ISREG(st.st_mode)
                head = _safe_read_head(sftp, p, 4096) if is_file else ""
                fp = _fingerprint(head)
                items.append({
                    "name": name,
                    "path": p,
                    "exists": True,
                    "type": "file" if is_file else "other",
                    "size": int(getattr(st, "st_size", 0)),
                    "mtime": int(getattr(st, "st_mtime", 0) or 0),
                    "fingerprint": fp,
                    "risk": "p2" if name in P2_RISKY else "p1",
                })
            except Exception:
                items.append({
                    "name": name,
                    "path": p,
                    "exists": False,
                    "risk": "p2" if name in P2_RISKY else "p1",
                })

        present = [x for x in items if x.get("exists")]
        present_p1 = [x for x in present if x.get("risk") == "p1"]
        present_p2 = [x for x in present if x.get("risk") == "p2"]

        return {
            "ok": True,
            "wp_root": wp_root,
            "wp_content": wp_content,
            "present_count": len(present),
            "present_p1_count": len(present_p1),
            "present_p2_count": len(present_p2),
            "recommended_default_disable": P1_DEFAULT,
            "risky_requires_explicit": P2_RISKY,
            "items": items,
        }
    finally:
        try:
            sftp.close()
        except Exception:
            pass
        try:
            client.close()
        except Exception:
            pass
