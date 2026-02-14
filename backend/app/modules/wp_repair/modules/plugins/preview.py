from __future__ import annotations

import posixpath
import re
import stat
from typing import Any, Dict, List, Optional, Tuple

from ..sftp.connect import sftp_connect

_MAX_PLUGINS_DEFAULT = 500
_MAINFILE_READ_MAX = 24_000  # genug für Plugin Header

# WICHTIG: Viele Plugins nutzen PHPDoc mit "* Plugin Name:"
# => optionales "*" + optionaler Whitespace vor dem Feld erlauben
_HDR_PREFIX = r"^\s*(?:\*\s*)?"
_PLUGIN_NAME_RE = re.compile(_HDR_PREFIX + r"Plugin Name:\s*(.+)\s*$", re.IGNORECASE | re.MULTILINE)
_VERSION_RE = re.compile(_HDR_PREFIX + r"Version:\s*(.+)\s*$", re.IGNORECASE | re.MULTILINE)
_TEXTDOMAIN_RE = re.compile(_HDR_PREFIX + r"Text Domain:\s*(.+)\s*$", re.IGNORECASE | re.MULTILINE)

# Dateien, die häufig existieren, aber i.d.R. NICHT der Plugin-Header sind
_BAD_MAINFILE_NAMES = {
    "index.php",
    "uninstall.php",
    "autoload.php",
    "composer.json",
    "readme.txt",
    "license.txt",
    "freemius.php",  # oft nur loader
}


def _is_safe_slug(slug: str) -> bool:
    if not slug or "/" in slug or "\\" in slug:
        return False
    if slug in (".", ".."):
        return False
    if ".." in slug:
        return False
    return True


def _read_head(sftp, path: str, limit: int = _MAINFILE_READ_MAX) -> Tuple[str, Optional[str]]:
    try:
        f = sftp.open(path, "r")
        try:
            data = f.read(limit)
        finally:
            f.close()
        if isinstance(data, bytes):
            return data.decode("utf-8", errors="replace"), None
        return str(data), None
    except Exception as e:
        return "", str(e)


def _extract_headers(text: str) -> Dict[str, str]:
    out: Dict[str, str] = {}
    src = text or ""

    m = _PLUGIN_NAME_RE.search(src)
    if m:
        out["plugin_name"] = m.group(1).strip()

    m = _VERSION_RE.search(src)
    if m:
        out["version"] = m.group(1).strip()

    m = _TEXTDOMAIN_RE.search(src)
    if m:
        out["text_domain"] = m.group(1).strip()

    return out


def _is_good_candidate_filename(fn: str) -> bool:
    if not fn or "/" in fn or "\\" in fn:
        return False
    low = fn.lower()
    if low in _BAD_MAINFILE_NAMES:
        return False
    if not low.endswith(".php"):
        return False
    return True


def _candidate_mainfiles(slug: str, entries: List[str]) -> List[str]:
    """
    Deterministische Reihenfolge:
    1) <slug>.php (wenn nicht geblacklistet)
    2) alle anderen .php im Root (sortiert), aber ohne typische false positives
    """
    cand: List[str] = []
    primary = f"{slug}.php"
    if primary in entries and _is_good_candidate_filename(primary):
        cand.append(primary)

    php_files = sorted(
        [e for e in entries if _is_good_candidate_filename(e) and e not in cand],
        key=lambda x: x.lower(),
    )
    cand.extend(php_files)
    return cand


def plugins_preview(
    host: str,
    port: int,
    username: str,
    password: str,
    wp_root: str,
    *,
    max_plugins: int = _MAX_PLUGINS_DEFAULT,
    include_ok: bool = True,
) -> Dict[str, Any]:
    """
    Read-only inventory + basic risk flags.
    - main_file wird NUR gesetzt, wenn Plugin-Header gefunden wurde
    """
    wp_root = (wp_root or "").rstrip("/")
    plugins_root = posixpath.join(wp_root, "wp-content", "plugins")

    client = sftp_connect(host, port, username, password)
    sftp = client.open_sftp()
    try:
        try:
            root_attrs = sftp.stat(plugins_root)
            if not stat.S_ISDIR(root_attrs.st_mode):
                return {"ok": False, "error": "plugins_root_not_dir", "plugins_root": plugins_root}
        except Exception:
            return {"ok": False, "error": "plugins_root_missing", "plugins_root": plugins_root}

        items: List[Dict[str, Any]] = []
        risky = 0

        try:
            dirents = sftp.listdir_attr(plugins_root)
        except Exception as e:
            return {"ok": False, "error": f"list_failed: {e}", "plugins_root": plugins_root}

        # Plugins sind i.d.R. Verzeichnisse
        plugin_dirs: List[Tuple[str, Any]] = []
        for a in dirents:
            name = getattr(a, "filename", "")
            if not _is_safe_slug(name):
                continue
            if stat.S_ISDIR(a.st_mode):
                plugin_dirs.append((name, a))

        plugin_dirs.sort(key=lambda x: x[0].lower())
        plugin_dirs = plugin_dirs[: max(1, int(max_plugins or _MAX_PLUGINS_DEFAULT))]

        for slug, _a in plugin_dirs:
            pdir = posixpath.join(plugins_root, slug)

            status = "ok"
            risk_level = "low"
            recommendation = "none"
            headers: Dict[str, str] = {}
            main_file: Optional[str] = None
            last_read_error: Optional[str] = None

            try:
                entries = sftp.listdir(pdir)
            except Exception as e:
                status = "unreadable"
                risk_level = "high"
                recommendation = "disable"
                entries = []
                last_read_error = str(e)

            if not entries:
                status = "empty_dir"
                risk_level = "high"
                recommendation = "disable"
            else:
                cands = _candidate_mainfiles(slug, entries)

                found = False
                for fn in cands[:50]:
                    full = posixpath.join(pdir, fn)

                    try:
                        st = sftp.stat(full)
                        if not stat.S_ISREG(st.st_mode):
                            continue
                    except Exception:
                        continue

                    head, err = _read_head(sftp, full)
                    if err:
                        last_read_error = err
                        continue

                    h = _extract_headers(head)
                    if h.get("plugin_name"):
                        main_file = fn
                        headers = h
                        found = True
                        last_read_error = None
                        break

                if not found:
                    if last_read_error:
                        status = "unreadable_main_file"
                        risk_level = "high"
                        recommendation = "disable"
                    else:
                        status = "header_not_found"
                        risk_level = "medium"
                        recommendation = "none"

            if status != "ok":
                risky += 1

            if include_ok or status != "ok":
                read_error = last_read_error if status == "unreadable_main_file" else None
                items.append(
                    {
                        "slug": slug,
                        "path": posixpath.join("wp-content", "plugins", slug),
                        "abs_path": pdir,
                        "status": status,
                        "risk_level": risk_level,
                        "recommended_action": recommendation,
                        "main_file": main_file,
                        "headers": headers,
                        "read_error": read_error,
                    }
                )

        return {
            "ok": True,
            "plugins_root": plugins_root,
            "summary": {"total": len(plugin_dirs), "returned": len(items), "risky": risky},
            "plugins": items,
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
