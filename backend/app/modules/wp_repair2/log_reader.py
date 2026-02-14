# /var/www/sitefixer/backend/app/modules/wp-repair/log_reader.py
from __future__ import annotations

import os
import re
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


_MAX_BYTES = 1_500_000  # total read cap per log file
_DEFAULT_TAIL_LINES = 300


@dataclass
class LogEntry:
    ts: Optional[str]
    level: str
    message: str
    file: Optional[str] = None
    line: Optional[int] = None
    plugin_slug: Optional[str] = None
    theme_slug: Optional[str] = None
    raw: Optional[str] = None


def _safe_realpath(p: str) -> Path:
    return Path(p).expanduser().resolve(strict=False)


def _read_tail_bytes(path: Path, max_bytes: int = _MAX_BYTES) -> bytes:
    """
    Efficient-ish tail: reads last max_bytes from file.
    """
    if not path.exists() or not path.is_file():
        return b""
    try:
        size = path.stat().st_size
        with path.open("rb") as f:
            if size > max_bytes:
                f.seek(size - max_bytes)
            return f.read()
    except Exception:
        return b""


def _tail_lines(path: Path, lines: int = _DEFAULT_TAIL_LINES) -> List[str]:
    raw = _read_tail_bytes(path)
    if not raw:
        return []
    text = raw.decode("utf-8", errors="replace")
    parts = text.splitlines()
    return parts[-lines:]


def _detect_plugin_theme_from_path(path: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Extract plugin/theme slug from typical WP paths.
    """
    # Normalize separators
    p = path.replace("\\", "/")
    m = re.search(r"/wp-content/plugins/([^/]+)/", p)
    plugin = m.group(1) if m else None
    m2 = re.search(r"/wp-content/themes/([^/]+)/", p)
    theme = m2.group(1) if m2 else None
    return plugin, theme


def _extract_file_line(text: str) -> Tuple[Optional[str], Optional[int]]:
    """
    Common patterns:
      in /path/file.php on line 123
      in /path/file.php:123
    """
    m = re.search(r"\bin\s+([^\s]+\.php)\s+on\s+line\s+(\d+)", text)
    if m:
        return m.group(1), int(m.group(2))
    m = re.search(r"\b([^\s]+\.php):(\d+)\b", text)
    if m:
        return m.group(1), int(m.group(2))
    return None, None


def _guess_level(line: str) -> str:
    l = line.lower()
    if "fatal error" in l or "uncaught" in l:
        return "fatal"
    if "parse error" in l:
        return "fatal"
    if "warning" in l:
        return "warning"
    if "notice" in l:
        return "notice"
    if "deprecated" in l:
        return "deprecated"
    if "error" in l:
        return "error"
    return "info"


def _extract_timestamp(line: str) -> Optional[str]:
    # Matches:
    # [19-Dec-2025 09:12:33 UTC] ...
    # 2025-12-19 09:12:33 ...
    m = re.search(r"^\[([0-9]{1,2}-[A-Za-z]{3}-[0-9]{4}\s+[0-9:]{8}(?:\s+[A-Z]+)?)\]", line)
    if m:
        return m.group(1)
    m2 = re.search(r"^([0-9]{4}-[0-9]{2}-[0-9]{2}\s+[0-9:]{8})", line)
    if m2:
        return m2.group(1)
    return None


def _normalize_log_lines(lines: List[str]) -> List[LogEntry]:
    out: List[LogEntry] = []
    for ln in lines:
        lvl = _guess_level(ln)
        ts = _extract_timestamp(ln)
        file, line_no = _extract_file_line(ln)
        plugin, theme = (None, None)
        if file:
            plugin, theme = _detect_plugin_theme_from_path(file)
        out.append(
            LogEntry(
                ts=ts,
                level=lvl,
                message=ln.strip(),
                file=file,
                line=line_no,
                plugin_slug=plugin,
                theme_slug=theme,
                raw=ln.strip(),
            )
        )
    return out


def _redact_secrets(text: str) -> str:
    # Basic redactions: passwords in wp-config-like strings, tokens, long hex
    t = text
    t = re.sub(r"(DB_PASSWORD'\s*,\s*')[^']*(')", r"\1***\2", t)
    t = re.sub(r"(?i)(password=)[^&\s]+", r"\1***", t)
    t = re.sub(r"(?i)(passwd=)[^&\s]+", r"\1***", t)
    t = re.sub(r"(?i)(token=)[^&\s]+", r"\1***", t)
    t = re.sub(r"(?i)(apikey=)[^&\s]+", r"\1***", t)
    t = re.sub(r"\b[a-f0-9]{32,64}\b", "***", t)  # hashes/tokens
    return t


def _default_log_candidates(root: Path) -> List[Path]:
    """
    Candidates are environment-specific. We support:
    - WordPress debug log
    - Common PHP error log locations under site root
    - Optional explicit env vars
    """
    wp_debug = root / "wp-content" / "debug.log"

    candidates: List[Path] = [wp_debug]

    # Common per-site logs in hosting panels
    for rel in [
        "error_log",
        "php_errorlog",
        "php_error.log",
        "logs/error.log",
        "log/error.log",
        "logs/php_error.log",
        "log/php_error.log",
    ]:
        candidates.append(root / rel)

    # Allow user/operator to configure additional absolute paths
    env = os.getenv("REPAIR_LOG_PATHS", "").strip()
    if env:
        for p in env.split(","):
            p = p.strip()
            if not p:
                continue
            candidates.append(_safe_realpath(p))

    # Deduplicate while keeping order
    seen = set()
    uniq: List[Path] = []
    for c in candidates:
        key = str(c)
        if key in seen:
            continue
        seen.add(key)
        uniq.append(c)
    return uniq


def read_logs(
    root_path: str,
    *,
    tail_lines: int = _DEFAULT_TAIL_LINES,
    redact: bool = True,
    include_nonexistent: bool = False,
) -> Dict[str, Any]:
    """
    Reads last N lines from known logs (best-effort).
    Returns:
      {
        ok: bool,
        root_path: str,
        sources: [{path, exists, entries:[...]}],
        summary: {...},
        errors: [...]
      }
    """
    root = _safe_realpath(root_path)
    sources_out: List[Dict[str, Any]] = []
    errors: List[str] = []

    candidates = _default_log_candidates(root)

    total_entries = 0
    fatals = 0
    plugin_hits: Dict[str, int] = {}
    theme_hits: Dict[str, int] = {}

    for path in candidates:
        exists = path.exists() and path.is_file()
        if not exists and not include_nonexistent:
            continue

        lines = _tail_lines(path, lines=tail_lines) if exists else []
        if redact and lines:
            lines = [_redact_secrets(x) for x in lines]

        entries = _normalize_log_lines(lines)
        total_entries += len(entries)

        for e in entries:
            if e.level == "fatal":
                fatals += 1
            if e.plugin_slug:
                plugin_hits[e.plugin_slug] = plugin_hits.get(e.plugin_slug, 0) + 1
            if e.theme_slug:
                theme_hits[e.theme_slug] = theme_hits.get(e.theme_slug, 0) + 1

        sources_out.append(
            {
                "path": str(path),
                "exists": exists,
                "entries": [asdict(e) for e in entries],
            }
        )

    # Compact top offenders
    top_plugins = sorted(plugin_hits.items(), key=lambda kv: kv[1], reverse=True)[:5]
    top_themes = sorted(theme_hits.items(), key=lambda kv: kv[1], reverse=True)[:5]

    return {
        "ok": True,
        "root_path": str(root),
        "sources": sources_out,
        "summary": {
            "entries": total_entries,
            "fatals": fatals,
            "top_plugins": [{"slug": s, "count": c} for s, c in top_plugins],
            "top_themes": [{"slug": s, "count": c} for s, c in top_themes],
        },
        "errors": errors,
        "meta": {
            "tail_lines": tail_lines,
            "redact": redact,
            "generated_at": int(time.time()),
        },
    }
