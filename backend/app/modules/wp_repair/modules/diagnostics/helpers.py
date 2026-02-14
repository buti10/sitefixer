from __future__ import annotations

import posixpath
import re
from typing import Dict, List, Optional, Tuple

from app.modules.wp_repair.modules.sftp.connect import sftp_connect


def _read_text_sftp(sftp, path: str, max_bytes: int = 2_000_000) -> str:
    f = sftp.open(path, "r")
    try:
        data = f.read(max_bytes)
        if isinstance(data, bytes):
            return data.decode("utf-8", errors="replace")
        return str(data)
    finally:
        f.close()


def _write_text_sftp(sftp, path: str, text: str) -> None:
    f = sftp.open(path, "w")
    try:
        f.write(text)
    finally:
        f.close()


def sftp_exists(host: str, port: int, username: str, password: str, path: str) -> bool:
    client = sftp_connect(host, port, username, password)
    sftp = client.open_sftp()
    try:
        sftp.stat(path)
        return True
    except Exception:
        return False
    finally:
        try:
            sftp.close()
        except Exception:
            pass
        try:
            client.close()
        except Exception:
            pass


def read_text_remote(host: str, port: int, username: str, password: str, path: str, max_bytes: int = 2_000_000) -> str:
    client = sftp_connect(host, port, username, password)
    sftp = client.open_sftp()
    try:
        return _read_text_sftp(sftp, path, max_bytes=max_bytes)
    finally:
        try:
            sftp.close()
        except Exception:
            pass
        try:
            client.close()
        except Exception:
            pass


def write_text_remote(host: str, port: int, username: str, password: str, path: str, text: str) -> None:
    client = sftp_connect(host, port, username, password)
    sftp = client.open_sftp()
    try:
        _write_text_sftp(sftp, path, text)
    finally:
        try:
            sftp.close()
        except Exception:
            pass
        try:
            client.close()
        except Exception:
            pass


def find_wp_config_candidates(wp_root: str) -> List[str]:
    wp_root = posixpath.normpath(wp_root)
    parent = posixpath.dirname(wp_root)
    return [
        posixpath.join(wp_root, "wp-config.php"),
        posixpath.join(parent, "wp-config.php"),
    ]


def choose_wp_config_path(host: str, port: int, username: str, password: str, wp_root: str) -> Optional[str]:
    for p in find_wp_config_candidates(wp_root):
        if sftp_exists(host, port, username, password, p):
            return p
    return None


def patch_wp_config_debug(text: str, enable: bool) -> Tuple[str, Dict[str, object]]:
    """
    Whitelist patch:
    - WP_DEBUG
    - WP_DEBUG_LOG
    - WP_DEBUG_DISPLAY
    Inserts before "That's all" marker if missing.
    """
    report = {
        "wp_debug": None,
        "wp_debug_log": None,
        "wp_debug_display": None,
        "inserted_block": False,
        "replaced": [],
    }

    def set_define(src: str, key: str, value_php: str) -> Tuple[str, bool]:
        # replace existing define('KEY', ...)
        pat = re.compile(r"define\(\s*['\"]" + re.escape(key) + r"['\"]\s*,\s*([^)]+)\)\s*;", re.IGNORECASE)
        if pat.search(src):
            src2 = pat.sub(f"define('{key}', {value_php});", src)
            return src2, True
        return src, False

    if enable:
        targets = {
            "WP_DEBUG": "true",
            "WP_DEBUG_LOG": "true",
            "WP_DEBUG_DISPLAY": "false",
        }
    else:
        targets = {
            "WP_DEBUG": "false",
            "WP_DEBUG_LOG": "false",
            "WP_DEBUG_DISPLAY": "false",
        }

    out = text
    for k, v in targets.items():
        out, did = set_define(out, k, v)
        if did:
            report["replaced"].append(k)

    # insert missing keys
    missing = [k for k in targets.keys() if k not in report["replaced"] and f"'{k}'" not in out and f"\"{k}\"" not in out]
    if missing:
        block_lines = ["", "/* Sitefixer diagnostics */"]
        for k in missing:
            block_lines.append(f"define('{k}', {targets[k]});")
        block_lines.append("/* /Sitefixer diagnostics */")
        block = "\n".join(block_lines) + "\n"

        marker = "/* That's all, stop editing! */"
        idx = out.find(marker)
        if idx != -1:
            out = out[:idx] + block + out[idx:]
            report["inserted_block"] = True
        else:
            out = out + "\n" + block
            report["inserted_block"] = True

    return out, report


def parse_table_prefix(wp_config_text: str) -> Optional[str]:
    m = re.search(r"^\s*\$table_prefix\s*=\s*['\"]([^'\"]+)['\"]\s*;", wp_config_text, re.MULTILINE)
    return m.group(1) if m else None


def tail_text(text: str, max_lines: int = 250, max_chars: int = 120_000) -> str:
    lines = text.splitlines()
    if len(lines) > max_lines:
        lines = lines[-max_lines:]
    out = "\n".join(lines)
    if len(out) > max_chars:
        out = out[-max_chars:]
    return out


_FATAL_PATTERNS = [
    re.compile(r"PHP Fatal error:", re.IGNORECASE),
    re.compile(r"Uncaught Error", re.IGNORECASE),
    re.compile(r"Parse error", re.IGNORECASE),
    re.compile(r"Allowed memory size", re.IGNORECASE),
]


def extract_errors(log_tail: str) -> List[Dict[str, object]]:
    """
    Very simple extractor to feed UI.
    """
    out: List[Dict[str, object]] = []
    for line in log_tail.splitlines():
        if any(p.search(line) for p in _FATAL_PATTERNS):
            sev = "fatal"
            if "Allowed memory size" in line:
                sev = "memory"
            elif "Parse error" in line:
                sev = "parse"
            out.append({"severity": sev, "line": line.strip()})
    return out


def detect_plugin_from_log(log_tail: str) -> Optional[str]:
    # wp-content/plugins/<slug>/
    m = re.search(r"wp-content/plugins/([^/]+)/", log_tail, re.IGNORECASE)
    return m.group(1) if m else None
