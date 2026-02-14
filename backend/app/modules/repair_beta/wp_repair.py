# app/modules/repair_beta/wp_repair.py
from __future__ import annotations
import posixpath
import re
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from .sftp_client import (
    SFTPConn,
    clamp_path,
    close_sftp,
    connect_sftp,
    exists,
    listdir,
    read_text,
    rename_safe,
    safe_chmod,
    stat_mode,
    RepairError,
)


def _join(root: str, rel: str) -> str:
    if root != "/" and not root.endswith("/"):
        root += "/"
    return posixpath.normpath(posixpath.join(root, rel))


def detect_wp_version(sftp, wp_root: str) -> Optional[str]:
    version_php = _join(wp_root, "wp-includes/version.php")
    if not exists(sftp, version_php):
        return None
    txt = read_text(sftp, version_php, max_bytes=200_000)
    m = re.search(r"\$wp_version\s*=\s*'([^']+)';", txt)
    return m.group(1) if m else None


def detect_wp_config_facts(sftp, wp_root: str) -> Dict[str, Any]:
    cfg_path = _join(wp_root, "wp-config.php")
    facts: Dict[str, Any] = {
        "has_db_name": False,
        "has_db_user": False,
        "has_db_password": False,
        "has_db_host": False,
        "has_auth_keys": False,
        "table_prefix_set": False,
        "multisite": False,
    }
    if not exists(sftp, cfg_path):
        return facts

    txt = read_text(sftp, cfg_path, max_bytes=400_000)

    def has_define(name: str) -> bool:
        return re.search(rf"define\(\s*['\"]{re.escape(name)}['\"]\s*,", txt) is not None

    facts["has_db_name"] = has_define("DB_NAME")
    facts["has_db_user"] = has_define("DB_USER")
    facts["has_db_password"] = has_define("DB_PASSWORD")
    facts["has_db_host"] = has_define("DB_HOST")

    # auth keys/salts
    keys = ["AUTH_KEY", "SECURE_AUTH_KEY", "LOGGED_IN_KEY", "NONCE_KEY", "AUTH_SALT", "SECURE_AUTH_SALT", "LOGGED_IN_SALT", "NONCE_SALT"]
    facts["has_auth_keys"] = all(has_define(k) for k in keys)

    # table_prefix
    facts["table_prefix_set"] = re.search(r"^\s*\$table_prefix\s*=\s*['\"][^'\"]+['\"]\s*;", txt, re.M) is not None

    # multisite
    facts["multisite"] = has_define("MULTISITE") or ("define('WP_ALLOW_MULTISITE'" in txt)

    return facts


def list_wp_plugins(sftp, wp_root: str) -> Tuple[List[str], List[str], List[str]]:
    plugins_dir = _join(wp_root, "wp-content/plugins")
    mu_dir = _join(wp_root, "wp-content/mu-plugins")
    themes_dir = _join(wp_root, "wp-content/themes")

    plugins = [x for x in listdir(sftp, plugins_dir) if x not in (".", "..")]
    mu_plugins = [x for x in listdir(sftp, mu_dir) if x not in (".", "..")]
    themes = [x for x in listdir(sftp, themes_dir) if x not in (".", "..")]

    return plugins, mu_plugins, themes


def debug_log_facts(sftp, wp_root: str) -> Dict[str, Any]:
    p = _join(wp_root, "wp-content/debug.log")
    out = {"debug_log_exists": False, "debug_log_size": 0}
    try:
        st = sftp.stat(p)
        out["debug_log_exists"] = True
        out["debug_log_size"] = int(st.st_size or 0)
    except Exception:
        pass
    return out


def permission_facts(sftp, wp_root: str) -> Dict[str, Any]:
    """
    Check common WordPress expected permissions (best-effort).
    """
    checks = {
        "wp_root": (wp_root, None),
        "wp-config.php": (_join(wp_root, "wp-config.php"), ("0600", "0640")),
        ".htaccess": (_join(wp_root, ".htaccess"), ("0644",)),
        "wp-content": (_join(wp_root, "wp-content"), ("0755",)),
        "wp-content/plugins": (_join(wp_root, "wp-content/plugins"), ("0755",)),
        "wp-content/themes": (_join(wp_root, "wp-content/themes"), ("0755",)),
        "wp-content/uploads": (_join(wp_root, "wp-content/uploads"), ("0755",)),
    }

    perms: Dict[str, Any] = {}
    for key, (path, expected) in checks.items():
        mode = stat_mode(sftp, path)
        perms[key] = {
            "path": path,
            "mode": mode,
            "expected": list(expected) if expected else None,
            "ok": (mode in expected) if (mode and expected) else None,
            "exists": exists(sftp, path),
        }
    return perms


def build_findings(facts: Dict[str, Any], perms: Dict[str, Any]) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []

    # debug.log large
    if facts.get("debug_log_exists") and (facts.get("debug_log_size") or 0) >= 50 * 1024 * 1024:
        findings.append({
            "id": "debug_log_large",
            "severity": "medium",
            "title": "debug.log ist sehr groß",
            "details": "Kann Speicher/I/O belasten. Empfehlung: rotieren/archivieren.",
            "evidence": {"size": facts.get("debug_log_size")},
            "fixes": ["rotate_debug_log"],
        })

    # wp-config missing critical defines
    if not facts.get("has_db_name") or not facts.get("has_db_user") or not facts.get("has_db_host"):
        findings.append({
            "id": "wp_config_db_incomplete",
            "severity": "high",
            "title": "wp-config.php DB-Defines unvollständig",
            "details": "DB_NAME/DB_USER/DB_HOST scheinen zu fehlen oder sind nicht erkennbar.",
            "fixes": [],
        })

    # auth keys missing
    if facts.get("has_auth_keys") is False:
        findings.append({
            "id": "wp_config_auth_keys_missing",
            "severity": "high",
            "title": "wp-config.php Auth Keys/Salts fehlen",
            "details": "Fehlende Keys reduzieren Sicherheit. Empfehlung: Keys/Salts setzen.",
            "fixes": [],
        })

    # permissions findings
    for k, v in perms.items():
        if not isinstance(v, dict):
            continue
        if v.get("exists") is False:
            continue
        exp = v.get("expected")
        ok = v.get("ok")
        mode = v.get("mode")
        if exp and ok is False and mode:
            # wp-config should be tighter => high, otherwise medium
            sev = "high" if k == "wp-config.php" else "medium"
            findings.append({
                "id": f"perm_{k}",
                "severity": sev,
                "title": f"Rechte nicht empfohlen: {k}",
                "details": f"Aktuell {mode}, erwartet {', '.join(exp)}.",
                "evidence": {"path": v.get("path"), "mode": mode, "expected": exp},
                "fixes": ["fix_permissions"],
            })

    return findings


def wp_diagnose(conn: SFTPConn, wp_root: str) -> Dict[str, Any]:
    t = None
    sftp = None
    try:
        t, sftp = connect_sftp(conn)
        wp_root = clamp_path(wp_root, wp_root)  # normalize
        # Minimal sanity: must contain wp-includes/version.php
        wp_version = detect_wp_version(sftp, wp_root)
        if not wp_version:
            raise RepairError("Kein WordPress erkannt (wp-includes/version.php fehlt).")

        cfg = detect_wp_config_facts(sftp, wp_root)
        plugins, mu_plugins, themes = list_wp_plugins(sftp, wp_root)
        dbg = debug_log_facts(sftp, wp_root)
        perms = permission_facts(sftp, wp_root)

        facts: Dict[str, Any] = {
            "wp_version": wp_version,
            "wp_home": None,
            "wp_siteurl": None,
            **cfg,
            **dbg,
            "plugins": sorted(plugins),
            "mu_plugins": sorted(mu_plugins),
            "themes": sorted(themes),
            "permissions": perms,
        }

        findings = build_findings(facts, perms)

        return {"ok": True, "wp_root": wp_root, "facts": facts, "findings": findings}
    finally:
        close_sftp(t, sftp)


def fix_rotate_debug_log(conn: SFTPConn, wp_root: str) -> Dict[str, Any]:
    t = None
    sftp = None
    try:
        t, sftp = connect_sftp(conn)
        wp_root = clamp_path(wp_root, wp_root)
        log_path = _join(wp_root, "wp-content/debug.log")
        if not exists(sftp, log_path):
            return {"ok": True, "changed": False, "msg": "debug.log nicht vorhanden"}

        st = sftp.stat(log_path)
        old_size = int(st.st_size or 0)

        ts = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
        dst = _join(wp_root, f"wp-content/debug.log.{ts}.bak")
        rename_safe(sftp, log_path, dst)

        # recreate empty debug.log
        f = sftp.open(log_path, "w")
        f.close()
        safe_chmod(sftp, log_path, "0644")

        return {"ok": True, "changed": True, "moved_to": dst, "old_size": old_size}
    finally:
        close_sftp(t, sftp)


def fix_permissions(conn: SFTPConn, wp_root: str) -> Dict[str, Any]:
    """
    Apply recommended permissions to a safe set of known WordPress paths.
    Does NOT recurse the whole tree.
    """
    t = None
    sftp = None
    try:
        t, sftp = connect_sftp(conn)
        wp_root = clamp_path(wp_root, wp_root)

        actions: List[Dict[str, Any]] = []

        def apply(path: str, mode: str):
            if exists(sftp, path):
                before = stat_mode(sftp, path)
                safe_chmod(sftp, path, mode)
                after = stat_mode(sftp, path)
                actions.append({"path": path, "before": before, "after": after, "mode": mode})

        apply(_join(wp_root, "wp-config.php"), "0640")
        apply(_join(wp_root, ".htaccess"), "0644")

        # Directories
        apply(_join(wp_root, "wp-content"), "0755")
        apply(_join(wp_root, "wp-content/plugins"), "0755")
        apply(_join(wp_root, "wp-content/themes"), "0755")
        apply(_join(wp_root, "wp-content/uploads"), "0755")

        # A few core files (optional)
        apply(_join(wp_root, "index.php"), "0644")
        apply(_join(wp_root, "wp-settings.php"), "0644")

        return {"ok": True, "changed": True, "actions": actions}
    finally:
        close_sftp(t, sftp)
