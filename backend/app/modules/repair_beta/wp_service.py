import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests

from .sftp_service import sftp_connect


# -----------------------------
# small helpers
# -----------------------------
def _norm_root(p: str) -> str:
    p = (p or "/").strip()
    if not p.startswith("/"):
        p = "/" + p
    if not p.endswith("/"):
        p += "/"
    return p


def _join(root: str, rel: str) -> str:
    return _norm_root(root) + rel.lstrip("/")


def _sftp_exists(sftp, path: str) -> bool:
    try:
        sftp.stat(path)
        return True
    except Exception:
        return False


def _sftp_read_text(sftp, path: str) -> str:
    with sftp.open(path, "r") as f:
        data = f.read()
        if isinstance(data, (bytes, bytearray)):
            return data.decode("utf-8", "replace")
        return str(data)


def _sftp_size(sftp, path: str) -> int:
    return int(sftp.stat(path).st_size)


def _mode_octal(st_mode: int) -> str:
    # keep last 4 oct digits
    return oct(st_mode & 0o7777)


def _is_world_writable(st_mode: int) -> bool:
    return bool(st_mode & 0o002)


def _is_group_writable(st_mode: int) -> bool:
    return bool(st_mode & 0o020)


def _recommended_ok(path: str, is_dir: bool, mode: int) -> Tuple[bool, str]:
    # conservative defaults for shared hosting
    if is_dir:
        rec = 0o755
        ok = (mode & 0o777) == rec and not _is_world_writable(mode)
        return ok, "0755"
    # files
    name = path.rsplit("/", 1)[-1].lower()
    if name == "wp-config.php":
        # allow 0640/0600/0644 depending on hosting realities
        m = mode & 0o777
        ok = (m in (0o600, 0o640, 0o644)) and not _is_world_writable(mode)
        return ok, "0600/0640/0644"
    rec = 0o644
    ok = (mode & 0o777) == rec and not _is_world_writable(mode)
    return ok, "0644"


_CONST_RE = re.compile(
    r"define\(\s*['\"](?P<k>[A-Z0-9_]+)['\"]\s*,\s*(?P<v>[^)]+)\)\s*;",
    re.I,
)

_PREFIX_RE = re.compile(r"^\s*\$table_prefix\s*=\s*['\"]([^'\"]+)['\"]\s*;", re.M)


def _parse_wp_config_constants(text: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for m in _CONST_RE.finditer(text):
        k = m.group("k").upper()
        v_raw = m.group("v").strip()
        v_norm = v_raw.lower()
        if v_norm in ("true", "false"):
            out[k] = (v_norm == "true")
        else:
            # keep raw (includes quotes sometimes)
            out[k] = v_raw
    pm = _PREFIX_RE.search(text)
    if pm:
        out["TABLE_PREFIX"] = pm.group(1)
    return out


def _strip_quotes(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    v = v.strip()
    if (v.startswith("'") and v.endswith("'")) or (v.startswith('"') and v.endswith('"')):
        return v[1:-1]
    return v


def _safe_url(u: Optional[str]) -> Optional[str]:
    if not u:
        return None
    u = u.strip()
    u = _strip_quotes(u) or u
    if not re.match(r"^https?://", u, re.I):
        u = "https://" + u
    return u.rstrip("/")


def _http_check(url: str, path: str, timeout: int = 12) -> Dict[str, Any]:
    full = url.rstrip("/") + path
    try:
        r = requests.get(full, allow_redirects=True, timeout=timeout, headers={"User-Agent": "SitefixerRepairBot/1.0"})
        return {
            "url": full,
            "status": r.status_code,
            "final_url": str(r.url),
        }
    except Exception as e:
        return {"url": full, "error": type(e).__name__}


def run_wp_diagnose(*, host: str, port: int, user: str, password: str, wp_root: str, site_url: Optional[str] = None) -> Dict[str, Any]:
    """
    Returns:
      { ok, wp_root, facts, findings[] }
    Findings carry fix IDs used by /wp/fix/apply:
      - debug_disable
      - debug_rotate
      - permissions_fix
      - htaccess_reset (wenn du den Fix ergänzt, siehe unten)
    """
    wp_root = _norm_root(wp_root)

    facts: Dict[str, Any] = {}
    findings: List[Dict[str, Any]] = []

    # key WP paths
    wp_config = _join(wp_root, "wp-config.php")
    version_php = _join(wp_root, "wp-includes/version.php")
    debug_log = _join(wp_root, "wp-content/debug.log")
    htaccess = _join(wp_root, ".htaccess")

    with sftp_connect(host=host, user=user, password=password, port=port) as sftp:
        # --- wp-config presence + parse
        facts["wp_root"] = wp_root
        facts["wp_config_exists"] = _sftp_exists(sftp, wp_config)

        wp_consts: Dict[str, Any] = {}
        if facts["wp_config_exists"]:
            cfg_text = _sftp_read_text(sftp, wp_config)
            wp_consts = _parse_wp_config_constants(cfg_text)
        facts["has_db_name"] = "DB_NAME" in wp_consts
        facts["has_db_user"] = "DB_USER" in wp_consts
        facts["has_db_host"] = "DB_HOST" in wp_consts
        facts["has_auth_keys"] = any(k.startswith("AUTH_KEY") or k.endswith("_KEY") for k in wp_consts.keys())
        facts["table_prefix_set"] = bool(wp_consts.get("TABLE_PREFIX"))

        # --- WP_HOME / WP_SITEURL
        wp_home = _safe_url(wp_consts.get("WP_HOME"))
        wp_siteurl = _safe_url(wp_consts.get("WP_SITEURL"))
        facts["wp_home"] = wp_home
        facts["wp_siteurl"] = wp_siteurl

        # --- version
        wp_version = None
        if _sftp_exists(sftp, version_php):
            txt = _sftp_read_text(sftp, version_php)
            m = re.search(r"\$wp_version\s*=\s*['\"]([^'\"]+)['\"]\s*;", txt)
            if m:
                wp_version = m.group(1)
        facts["wp_version"] = wp_version

        # --- debug.log
        facts["debug_log_exists"] = _sftp_exists(sftp, debug_log)
        facts["debug_log_size"] = _sftp_size(sftp, debug_log) if facts["debug_log_exists"] else 0

        # --- permissions snapshot (minimal but useful)
        perm_targets = [
            (wp_config, False),
            (_join(wp_root, "wp-admin"), True),
            (_join(wp_root, "wp-includes"), True),
            (_join(wp_root, "wp-content"), True),
            (htaccess, False),
            (_join(wp_root, "index.php"), False),
        ]

        permissions: Dict[str, Any] = {}
        perm_bad = False
        for path, is_dir in perm_targets:
            if not _sftp_exists(sftp, path):
                continue
            st = sftp.stat(path)
            mode = st.st_mode
            ok, rec = _recommended_ok(path, is_dir, mode)

            item = {
                "path": path,
                "is_dir": is_dir,
                "mode": _mode_octal(mode),
                "recommended": rec,
                "world_writable": _is_world_writable(mode),
                "group_writable": _is_group_writable(mode),
                "ok": ok,
            }
            permissions[path] = item
            if not ok or item["world_writable"]:
                perm_bad = True

        facts["permissions"] = permissions

        # --- derive site url for HTTP checks
        base_url = site_url or wp_home or wp_siteurl
        base_url = _safe_url(base_url) if base_url else None
        facts["site_url_used"] = base_url

    # -----------------------------
    # Findings generation (structured)
    # -----------------------------
    # Debug settings hint (if debug log exists and is growing)
    if facts.get("debug_log_exists"):
        size = int(facts.get("debug_log_size") or 0)
        if size >= 1024 * 1024:  # >= 1MB
            findings.append({
                "id": "debug_log_large",
                "severity": "medium",
                "title": "debug.log ist groß",
                "details": f"Größe: {size} Bytes. Kann I/O/Performance belasten.",
                "fixes": ["debug_disable", "debug_rotate"],
            })
        else:
            # still useful: recommend disabling in production
            findings.append({
                "id": "debug_log_present",
                "severity": "low",
                "title": "debug.log vorhanden",
                "details": f"Größe: {size} Bytes. In Produktion sollte Debug-Logging meist deaktiviert sein.",
                "fixes": ["debug_disable"],
            })

    # Permissions issues
    if facts.get("permissions"):
        bad_items = [v for v in facts["permissions"].values() if v.get("ok") is False or v.get("world_writable")]
        if bad_items:
            findings.append({
                "id": "permissions_suspect",
                "severity": "high" if any(x.get("world_writable") for x in bad_items) else "medium",
                "title": "Rechte/Permissions untypisch",
                "details": f"{len(bad_items)} Pfade weichen von empfohlenen Werten ab.",
                "evidence": {"count": len(bad_items)},
                "fixes": ["permissions_fix"],
            })

    # HTTP checks (404/500) only if we have a usable URL
    if facts.get("site_url_used"):
        base = facts["site_url_used"]
        checks = [
            ("/", "home"),
            ("/wp-login.php", "wp_login"),
            ("/wp-admin/", "wp_admin"),
            ("/wp-json/", "wp_json"),
        ]
        http_results = {}
        for path, key in checks:
            http_results[key] = _http_check(base, path)
        facts["http"] = http_results

        # Evaluate
        def _status(r: Dict[str, Any]) -> Optional[int]:
            return r.get("status") if isinstance(r, dict) else None

        home_s = _status(http_results.get("home", {}))
        login_s = _status(http_results.get("wp_login", {}))
        admin_s = _status(http_results.get("wp_admin", {}))
        json_s = _status(http_results.get("wp_json", {}))

        # 500 family
        if any(s is not None and 500 <= s <= 599 for s in (home_s, login_s, admin_s, json_s)):
            findings.append({
                "id": "http_5xx",
                "severity": "critical",
                "title": "HTTP 5xx (Serverfehler) erkannt",
                "details": f"home={home_s}, login={login_s}, admin={admin_s}, json={json_s}",
                "fixes": [],  # wird Phase 2: safe plugin/theme disable + htaccess + errorlog
            })

        # 404 patterns
        if (login_s == 404) or (admin_s == 404):
            findings.append({
                "id": "wp_admin_404",
                "severity": "high",
                "title": "WP-Admin/WP-Login liefert 404",
                "details": f"wp-login.php={login_s}, wp-admin={admin_s}. Häufig .htaccess/Rewrite/Permalinks Problem.",
                "fixes": ["htaccess_reset"],  # ergänzen wir als Fix (siehe unten)
            })
    else:
        findings.append({
            "id": "site_url_unknown",
            "severity": "info",
            "title": "HTTP-Checks übersprungen",
            "details": "WP_HOME/WP_SITEURL nicht gefunden. Übergib optional site_url an /wp/diagnose (z.B. Ticket-Domain).",
            "fixes": [],
        })

    return {
        "ok": True,
        "wp_root": wp_root,
        "facts": facts,
        "findings": findings,
    }
