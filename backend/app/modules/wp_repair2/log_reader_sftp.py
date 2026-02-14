# app/modules/wp_repair/log_reader_sftp.py
from __future__ import annotations

import posixpath
import re
from typing import Any, Dict, List, Optional

# --- helpers ---

def _safe_tail(text: str, tail_lines: int) -> str:
    if tail_lines <= 0:
        return ""
    lines = text.splitlines()
    return "\n".join(lines[-tail_lines:])

def _redact(s: str) -> str:
    # simple redaction: urls with creds, common secrets
    s = re.sub(r'(?i)(password|pass|pwd)\s*=\s*([^\s&]+)', r'\1=***', s)
    s = re.sub(r'(?i)(DB_PASSWORD|AUTH_KEY|SECURE_AUTH_KEY|LOGGED_IN_KEY|NONCE_KEY|AUTH_SALT|SECURE_AUTH_SALT|LOGGED_IN_SALT|NONCE_SALT)\s*\'[^\']+\'',
               r"\1 '***'", s)
    return s

def _sftp_read_text(sftp, path: str, max_bytes: int = 1_000_000) -> Optional[str]:
    try:
        f = sftp.open(path, "r")
        try:
            data = f.read(max_bytes)
            if isinstance(data, bytes):
                return data.decode("utf-8", "replace")
            return str(data)
        finally:
            f.close()
    except Exception:
        return None

def _exists(sftp, path: str) -> bool:
    try:
        sftp.stat(path)
        return True
    except Exception:
        return False

def _summarize_entries(text: str) -> Dict[str, Any]:
    # Minimal parser: find fatals + plugin/theme file hints
    entries: List[Dict[str, Any]] = []

    fatal_rx = re.compile(r"(?i)(fatal error|parse error|allowed memory size|error establishing a database connection)")
    plugin_rx = re.compile(r"wp-content/plugins/([^/]+)/", re.IGNORECASE)
    theme_rx  = re.compile(r"wp-content/themes/([^/]+)/", re.IGNORECASE)

    top_plugins: Dict[str, int] = {}
    top_themes: Dict[str, int] = {}

    for line in text.splitlines():
        msg = line.strip()
        if not msg:
            continue

        if fatal_rx.search(msg):
            entries.append({"level": "fatal", "message": msg})

        pm = plugin_rx.search(msg)
        if pm:
            top_plugins[pm.group(1)] = top_plugins.get(pm.group(1), 0) + 1

        tm = theme_rx.search(msg)
        if tm:
            top_themes[tm.group(1)] = top_themes.get(tm.group(1), 0) + 1

    def _top(d: Dict[str, int], n: int) -> List[Dict[str, Any]]:
        items = sorted(d.items(), key=lambda x: x[1], reverse=True)[:n]
        return [{"slug": k, "hits": v} for k, v in items]

    return {
        "entries": entries[-50:],  # keep last 50 fatals
        "summary": {
            "top_plugins": _top(top_plugins, 5),
            "top_themes": _top(top_themes, 3),
        },
    }

# --- public ---

def read_logs_sftp(*, sftp, wp_root: str, tail_lines: int = 300, redact: bool = True) -> Dict[str, Any]:
    """
    Reads common WP log locations via SFTP and returns a structure compatible with your diagnose rules:
      { sources:[{path, ok, tail, entries:[] }], summary:{top_plugins, top_themes} }
    """
    wp_root = wp_root.rstrip("/") or "/"

    candidates = [
        posixpath.join(wp_root, "wp-content", "debug.log"),
        posixpath.join(wp_root, "error_log"),
        posixpath.join(posixpath.dirname(wp_root), "error_log"),  # sometimes one level above
    ]

    sources: List[Dict[str, Any]] = []
    merged_text = ""

    for p in candidates:
        if not _exists(sftp, p):
            sources.append({"path": p, "ok": False, "reason": "not_found"})
            continue

        raw = _sftp_read_text(sftp, p)
        if raw is None:
            sources.append({"path": p, "ok": False, "reason": "read_failed"})
            continue

        tail = _safe_tail(raw, tail_lines)
        if redact:
            tail = _redact(tail)

        sources.append({"path": p, "ok": True, "tail": tail})
        merged_text += "\n" + tail

    summary = _summarize_entries(merged_text)

    # map to your expected keys
    return {
        "ok": True,
        "sources": [
            {
                "path": s["path"],
                "ok": s.get("ok", False),
                "reason": s.get("reason"),
                # keep compatible fields
                "entries": summary["entries"] if s.get("ok") else [],
                "tail": s.get("tail", ""),
            }
            for s in sources
        ],
        "summary": summary["summary"],
    }
