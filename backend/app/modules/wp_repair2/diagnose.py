# /var/www/sitefixer/backend/app/modules/wp-repair/diagnose.py
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from app.modules.wp_repair.sftp_sessions import get_sftp_client
from app.modules.wp_repair.inventory_sftp import build_inventory_sftp
try:
    from app.modules.wp_repair.qlog_reader_sftp import read_logs_sftp
except Exception:
    read_logs_sftp = None
from app.modules.wp_repair.qlog_reader_sftp import read_logs_sftp

from .inventory import build_inventory, SftpFS, LocalFS
from .http_probe import probe_site
from .log_reader import read_logs


# -----------------------------
# Rule helpers
# -----------------------------

def _pick_http_status(http: Dict[str, Any], key: str) -> Optional[int]:
    try:
        return int(http["targets"][key]["status"])
    except Exception:
        return None


def _has_redirect_loop(target: Dict[str, Any]) -> bool:
    # A crude check: many hops OR repeated urls
    try:
        hops = target.get("hops") or []
        if len(hops) >= 6:
            return True
        seen = set()
        for h in hops:
            u = h.get("url")
            if not u:
                continue
            if u in seen:
                return True
            seen.add(u)
    except Exception:
        pass
    return False


def _extract_error_signals(logs: Dict[str, Any]) -> Dict[str, Any]:
    """
    Summarize common fatal patterns + top plugin/theme offenders.
    """
    signals: Dict[str, Any] = {
        "fatal_entries": [],
        "pattern_hits": {},
        "top_plugins": logs.get("summary", {}).get("top_plugins", []),
        "top_themes": logs.get("summary", {}).get("top_themes", []),
    }

    patterns = {
        "memory_exhausted": re.compile(r"Allowed memory size of .* exhausted", re.IGNORECASE),
        "parse_error": re.compile(r"Parse error", re.IGNORECASE),
        "undefined_function": re.compile(r"Call to undefined function", re.IGNORECASE),
        "class_not_found": re.compile(r"Class .* not found", re.IGNORECASE),
        "cannot_redeclare": re.compile(r"Cannot redeclare", re.IGNORECASE),
        "db_connect": re.compile(r"Error establishing a database connection|Access denied for user|Unknown database", re.IGNORECASE),
        "missing_file": re.compile(r"failed to open stream: No such file or directory", re.IGNORECASE),
    }
    signals["pattern_hits"] = {k: 0 for k in patterns.keys()}

    # Collect up to N fatals across all sources
    fatals: List[Dict[str, Any]] = []
    for src in logs.get("sources", []) or []:
        for e in src.get("entries", []) or []:
            if e.get("level") == "fatal" or "fatal error" in (e.get("message", "").lower()):
                fatals.append(e)

            msg = e.get("message", "") or ""
            for key, rx in patterns.items():
                if rx.search(msg):
                    signals["pattern_hits"][key] += 1

    # Keep last 15 fatals
    signals["fatal_entries"] = fatals[-15:]

    return signals


def _recommend_actions(
    *,
    inventory: Dict[str, Any],
    http: Dict[str, Any],
    logs: Dict[str, Any],
) -> Tuple[str, List[Dict[str, Any]]]:
    """
    Returns: (suspected_cause, recommended_actions[])
    Action format:
      { "id": "fix.htaccess.reset", "label": "...", "severity": "P1|P2|P3", "params": {...} }
    """
    actions: List[Dict[str, Any]] = []
    suspected = "unknown"

    fe = _extract_error_signals(logs)
    fatal_entries = fe.get("fatal_entries", [])
    top_plugins = fe.get("top_plugins", [])
    top_themes = fe.get("top_themes", [])
    hits = fe.get("pattern_hits", {}) or {}

    # HTTP statuses
    st_front = _pick_http_status(http, "frontend")
    st_login = _pick_http_status(http, "login")
    st_admin = _pick_http_status(http, "admin")

    # Redirect loops
    loop_front = _has_redirect_loop(http.get("targets", {}).get("frontend", {}) or {})
    loop_login = _has_redirect_loop(http.get("targets", {}).get("login", {}) or {})
    loop_admin = _has_redirect_loop(http.get("targets", {}).get("admin", {}) or {})

    # Signals from inventory
    dropins = inventory.get("dropins", {}) or {}
    has_object_cache = bool(dropins.get("object_cache"))
    has_advanced_cache = bool(dropins.get("advanced_cache"))
    has_maintenance = bool(dropins.get("maintenance"))

    # --- P1 emergency recommendations ---
    # Maintenance mode
    if has_maintenance:
        suspected = "maintenance_mode"
        actions.append({
            "id": "fix.maintenance.remove",
            "label": "Maintenance-Mode entfernen (.maintenance)",
            "severity": "P1",
            "params": {},
        })

    # Redirect loop: likely URLs or htaccess
    if loop_front or loop_login or loop_admin:
        suspected = "redirect_loop"
        actions.append({
            "id": "fix.htaccess.reset",
            "label": ".htaccess zurücksetzen (WP Standard)",
            "severity": "P1",
            "params": {},
        })
        actions.append({
            "id": "db.fix.siteurl_home",
            "label": "DB prüfen: siteurl/home (Redirect-Loop Fix)",
            "severity": "P1",
            "params": {},
        })

    # 404 widespread (rewrite)
    if (st_front == 404 and st_login in (404, None)) or (st_admin == 404):
        suspected = "rewrite_or_root"
        actions.append({
            "id": "fix.htaccess.reset",
            "label": ".htaccess zurücksetzen (Rewrite reparieren)",
            "severity": "P1",
            "params": {},
        })

    # 403 (permissions or WAF) – safe attempt permissions first
    if st_front == 403 or st_login == 403 or st_admin == 403:
        suspected = "permissions_or_waf"
        actions.append({
            "id": "fix.permissions.normalize",
            "label": "Dateirechte normalisieren (755/644)",
            "severity": "P1",
            "params": {},
        })
    if st_front == 200 and st_login == 200 and st_admin == 200 and inventory.get("wp_detected"):
        suspected = "ok_or_soft_issue"
        actions.append({
            "id": "info.review.plugins",
            "label": "Hinweis: Plugins/Drop-ins prüfen (Read-only)",
            "severity": "P3",
            "params": {},
        })

    # 500/critical errors – isolate plugins/themes first
    if st_front in (500, 502, 503) or st_admin in (500, 502, 503) or hits.get("parse_error", 0) > 0:
        # If plugin/themepath appears, prefer targeted
        suspected = "php_runtime"
        actions.append({
            "id": "fix.cache.disable_dropins",
            "label": "Cache/Drop-ins deaktivieren (object-cache/advanced-cache)",
            "severity": "P1",
            "params": {},
        })
        actions.append({
            "id": "plugins.disable_all",
            "label": "Alle Plugins deaktivieren (Notfall)",
            "severity": "P1",
            "params": {},
        })
        actions.append({
            "id": "themes.switch_default",
            "label": "Auf Default-Theme wechseln (Notfall)",
            "severity": "P2",
            "params": {"theme": "twentytwentyfour"},
        })

    # DB connect errors
    if hits.get("db_connect", 0) > 0:
        suspected = "database"
        actions.append({
            "id": "db.check.connection",
            "label": "DB Verbindung testen (wp-config)",
            "severity": "P1",
            "params": {},
        })

    # Memory exhausted
    if hits.get("memory_exhausted", 0) > 0:
        suspected = "php_memory"
        actions.append({
            "id": "env.recommend.memory_limit",
            "label": "Empfehlung: memory_limit erhöhen (z. B. 256M/512M)",
            "severity": "P2",
            "params": {},
        })

    # --- Targeted replace suggestions from logs (top offenders) ---
    # If top plugin offenders exist, suggest replace
    for p in top_plugins[:2]:
        slug = p.get("slug")
        if not slug:
            continue
        actions.append({
            "id": "plugins.replace",
            "label": f"Plugin ersetzen (WP.org): {slug}",
            "severity": "P2",
            "params": {"slug": slug, "prefer_installed_version": True},
        })
        suspected = suspected if suspected != "unknown" else "plugin"

    for t in top_themes[:1]:
        slug = t.get("slug")
        if not slug:
            continue
        actions.append({
            "id": "themes.replace",
            "label": f"Theme ersetzen (WP.org): {slug}",
            "severity": "P3",
            "params": {"slug": slug, "prefer_installed_version": True},
        })
        suspected = suspected if suspected != "unknown" else "theme"

    # Core replace as later option if still broken
    if (st_front in (500, 404) and st_login in (500, 404)) and inventory.get("wp_detected"):
        actions.append({
            "id": "core.replace",
            "label": "WordPress Core ersetzen (gleiche Version)",
            "severity": "P3",
            "params": {"prefer_same_version": True},
        })
        suspected = suspected if suspected != "unknown" else "core"

    # De-duplicate by action id + params
    uniq: List[Dict[str, Any]] = []
    seen = set()
    for a in actions:
        key = (a.get("id"), str(a.get("params", {})))
        if key in seen:
            continue
        seen.add(key)
        uniq.append(a)

    if suspected == "unknown":
        # fallback
        suspected = "needs_triage"
        uniq.insert(0, {
            "id": "plugins.disable_all",
            "label": "Alle Plugins deaktivieren (sicherer erster Test)",
            "severity": "P2",
            "params": {},
        })

    return suspected, uniq


# -----------------------------
# Public API
# -----------------------------

def run_diagnose(
    *,
    root_path: str,
    base_url: str,
    session_id: str,
    verify_ssl: bool = True,
    capture_snippet: bool = True,
    tail_lines: int = 300,
    redact_logs: bool = True,
) -> Dict[str, Any]:
    """
    Orchestrates:
      - inventory (filesystem)
      - http probes
      - logs tail + normalization
      - rule-based recommendations
    """
    
    client = None
    sftp = None
    try:
        client, sftp = get_sftp_client(session_id)
        inv = build_inventory_sftp(sftp=sftp, wp_root=root_path)

        http = probe_site(base_url, verify_ssl=verify_ssl, capture_snippet=capture_snippet)
        logs = None
        if read_logs_sftp:
                logs = read_logs_sftp(...)
        else:
            logs = {"ok": False, "error": "qlog_reader_sftp missing"}

        suspected, actions = _recommend_actions(inventory=inv, http=http, logs=logs)

        triage = {
            "frontend": _pick_http_status(http, "frontend"),
            "login": _pick_http_status(http, "login"),
            "admin": _pick_http_status(http, "admin"),
        }

        return {
            "ok": True,
            "input": {"root_path": root_path, "base_url": base_url, "verify_ssl": verify_ssl},
            "triage": triage,
            "suspected_cause": suspected,
            "recommended_actions": actions,
            "inventory": inv,
            "http": http,
            "logs": logs,
        }
    finally:
        try:
            if sftp: sftp.close()
        except Exception:
            pass
        try:
            if client: client.close()
        except Exception:
            pass

