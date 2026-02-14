from __future__ import annotations

from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional
import re
import time

import requests


@dataclass
class HttpCheckResult:
    name: str
    url: str
    ok: bool
    status: Optional[int] = None
    final_url: Optional[str] = None
    redirects: int = 0
    elapsed_ms: int = 0
    error: Optional[str] = None
    snippet: Optional[str] = None


def _norm_url(u: str) -> str:
    u = (u or "").strip()
    if not u:
        return ""
    if not re.match(r"^https?://", u, re.I):
        u = "https://" + u
    return u


def _fetch(url: str, timeout: int = 15, verify_tls: bool = True) -> HttpCheckResult:
    t0 = time.time()
    try:
        r = requests.get(
            url,
            timeout=timeout,
            allow_redirects=True,
            headers={"User-Agent": "SitefixerRepairBot/1.0"},
            verify=verify_tls,
        )
        elapsed = int((time.time() - t0) * 1000)

        text = ""
        try:
            text = r.text or ""
        except Exception:
            text = ""

        snippet = text[:500] if text else None

        return HttpCheckResult(
            name="",
            url=url,
            ok=(200 <= r.status_code < 400),
            status=r.status_code,
            final_url=str(r.url) if r.url else None,
            redirects=len(r.history) if r.history else 0,
            elapsed_ms=elapsed,
            snippet=snippet,
        )
    except requests.exceptions.SSLError as e:
        return HttpCheckResult(name="", url=url, ok=False, error=f"TLS/SSL: {e.__class__.__name__}")
    except requests.exceptions.Timeout:
        return HttpCheckResult(name="", url=url, ok=False, error="Timeout")
    except requests.exceptions.RequestException as e:
        return HttpCheckResult(name="", url=url, ok=False, error=f"Request: {e.__class__.__name__}")


def run_http_diagnose(domain: str, *, timeout: int = 15, verify_tls: bool = True) -> Dict[str, Any]:
    base = _norm_url(domain)
    if not base:
        return {"ok": False, "msg": "domain fehlt"}

    targets = [
        ("home", base.rstrip("/") + "/"),
        ("wp_login", base.rstrip("/") + "/wp-login.php"),
        ("wp_admin", base.rstrip("/") + "/wp-admin/"),
        ("wp_json", base.rstrip("/") + "/wp-json/"),
    ]

    checks: List[HttpCheckResult] = []
    findings: List[Dict[str, Any]] = []

    for name, url in targets:
        res = _fetch(url, timeout=timeout, verify_tls=verify_tls)
        res.name = name
        checks.append(res)

        # Findings ableiten
        if res.error:
            findings.append({
                "id": f"http_{name}_error",
                "severity": "high",
                "title": f"HTTP Fehler: {name}",
                "details": f"{url} → {res.error}",
                "evidence": asdict(res),
                "fixes": ["htaccess_reset", "plugins_disable_all"],  # später sinnvoll erweitern
            })
            continue

        if res.status in (404,):
            findings.append({
                "id": f"http_{name}_404",
                "severity": "high" if name in ("home", "wp_admin") else "medium",
                "title": f"HTTP 404: {name}",
                "details": f"{url} liefert 404. Häufig .htaccess/Rewrite/Docroot falsch.",
                "evidence": asdict(res),
                "fixes": ["htaccess_reset"],
            })

        if res.status and res.status >= 500:
            findings.append({
                "id": f"http_{name}_5xx",
                "severity": "critical" if name == "home" else "high",
                "title": f"HTTP {res.status}: {name}",
                "details": f"{url} liefert Serverfehler. Häufig Plugin/Theme/PHP-Fatal.",
                "evidence": asdict(res),
                "fixes": ["plugins_disable_all", "debug_disable"],
            })

        if res.redirects >= 8:
            findings.append({
                "id": f"http_{name}_redirect_loop",
                "severity": "high",
                "title": "Viele Redirects / möglicher Redirect-Loop",
                "details": f"{url} → {res.redirects} Redirects (final: {res.final_url}).",
                "evidence": asdict(res),
                "fixes": [],  # später siteurl/home fix + caching off etc.
            })

    facts = {
        "base": base,
        "timeout": timeout,
        "verify_tls": verify_tls,
    }

    return {
        "ok": True,
        "facts": facts,
        "checks": [asdict(x) for x in checks],
        "findings": findings,
    }
