from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

import paramiko

# Wir nutzen deine vorhandenen SFTP-Helper aus repair_beta (sind bei dir vorhanden)
from app.modules.repair_beta.sftp_client import exists as sftp_exists
from app.modules.repair_beta.sftp_client import read_text as sftp_read_text
from app.modules.repair_beta.sftp_client import listdir as sftp_listdir


_MAX_READ_BYTES = 512_000


def _is_wp_root(sftp: paramiko.SFTPClient, root: str) -> bool:
    root = root.rstrip("/") or "/"
    return sftp_exists(sftp, f"{root}/wp-config.php") and sftp_exists(sftp, f"{root}/wp-settings.php")


def _read_wp_version(sftp: paramiko.SFTPClient, root: str) -> Optional[str]:
    root = root.rstrip("/") or "/"
    p = f"{root}/wp-includes/version.php"
    if not sftp_exists(sftp, p):
        return None
    txt = sftp_read_text(sftp, p, max_bytes=120_000)  # repair_beta helper unterstützt max_bytes
    m = re.search(r"\$wp_version\s*=\s*'([^']+)'\s*;", txt)
    return m.group(1).strip() if m else None


def _parse_header_value(text: str, header: str) -> Optional[str]:
    m = re.search(rf"^{re.escape(header)}\s*:\s*(.+)$", text, re.MULTILINE | re.IGNORECASE)
    return m.group(1).strip() if m else None


def _list_plugin_slugs(sftp: paramiko.SFTPClient, wp_root: str) -> List[str]:
    plugins_dir = f"{wp_root.rstrip('/')}/wp-content/plugins"
    if not sftp_exists(sftp, plugins_dir):
        return []
    out: List[str] = []
    for name in sftp_listdir(sftp, plugins_dir):
        if name.startswith("."):
            continue
        out.append(name)
    return sorted(out)


def _list_theme_slugs(sftp: paramiko.SFTPClient, wp_root: str) -> List[str]:
    themes_dir = f"{wp_root.rstrip('/')}/wp-content/themes"
    if not sftp_exists(sftp, themes_dir):
        return []
    out: List[str] = []
    for name in sftp_listdir(sftp, themes_dir):
        if name.startswith("."):
            continue
        out.append(name)
    return sorted(out)


def build_inventory_sftp(
    *,
    sftp: paramiko.SFTPClient,
    wp_root: str,
) -> Dict[str, Any]:
    wp_root = wp_root.rstrip("/") or "/"

    result: Dict[str, Any] = {
        "ok": True,
        "wp_root": wp_root,
        "wp_detected": _is_wp_root(sftp, wp_root),
        "wp_version": None,
        "plugins": [],
        "themes": [],
        "errors": [],
    }

    if not result["wp_detected"]:
        result["errors"].append("WordPress root not detected via SFTP (missing wp-config.php/wp-settings.php).")
        return result

    result["wp_version"] = _read_wp_version(sftp, wp_root)
    result["plugins"] = _list_plugin_slugs(sftp, wp_root)
    result["themes"] = _list_theme_slugs(sftp, wp_root)

    return result
