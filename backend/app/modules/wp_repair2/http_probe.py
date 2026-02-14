# /var/www/sitefixer/backend/app/modules/wp-repair/http_probe.py
from __future__ import annotations

import time
from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

# Prefer requests, fallback to urllib if not installed
try:
    import requests  # type: ignore
except Exception:  # pragma: no cover
    requests = None  # type: ignore

import ssl
import urllib.request
import urllib.error


DEFAULT_PATHS = {
    "frontend": "/",
    "login": "/wp-login.php",
    "admin": "/wp-admin/",
    "ajax": "/wp-admin/admin-ajax.php",
}


@dataclass
class Hop:
    url: str
    status: int
    location: Optional[str] = None


@dataclass
class ProbeResult:
    ok: bool
    final_url: str
    status: int
    hops: List[Hop]
    elapsed_ms: int
    error: Optional[str] = None
    snippet: Optional[str] = None
    headers: Optional[Dict[str, str]] = None


def _normalize_base_url(base_url: str) -> str:
    base = base_url.strip()
    if not base:
        return base
    if not base.startswith(("http://", "https://")):
        base = "https://" + base
    # ensure trailing slash for urljoin behavior
    if not base.endswith("/"):
        base += "/"
    return base


def _truncate_html(text: str, limit: int = 60_000) -> str:
    if not text:
        return ""
    return text[:limit]


def _probe_with_requests(
    url: str,
    timeout: float,
    max_redirects: int,
    verify_ssl: bool,
    user_agent: str,
    capture_snippet: bool,
) -> ProbeResult:
    assert requests is not None

    sess = requests.Session()
    sess.max_redirects = max_redirects

    headers = {"User-Agent": user_agent, "Accept": "text/html,application/xhtml+xml,*/*;q=0.8"}
    t0 = time.time()
    hops: List[Hop] = []

    try:
        # We want hop visibility -> manual redirect loop
        cur = url
        for _ in range(max_redirects + 1):
            resp = sess.get(
                cur,
                headers=headers,
                timeout=timeout,
                allow_redirects=False,
                verify=verify_ssl,
            )
            loc = resp.headers.get("Location")
            hops.append(Hop(url=cur, status=resp.status_code, location=loc))

            # Redirect?
            if resp.status_code in (301, 302, 303, 307, 308) and loc:
                cur = urljoin(cur, loc)
                continue

            elapsed = int((time.time() - t0) * 1000)
            snippet = None
            if capture_snippet:
                ctype = (resp.headers.get("Content-Type") or "").lower()
                if "text/html" in ctype or "text/plain" in ctype or ctype == "":
                    snippet = _truncate_html(resp.text or "")
            # Normalize headers to str:str
            hdrs = {str(k): str(v) for k, v in resp.headers.items()}
            return ProbeResult(
                ok=True,
                final_url=cur,
                status=resp.status_code,
                hops=hops,
                elapsed_ms=elapsed,
                snippet=snippet,
                headers=hdrs,
            )

        elapsed = int((time.time() - t0) * 1000)
        return ProbeResult(
            ok=False,
            final_url=hops[-1].url if hops else url,
            status=hops[-1].status if hops else 0,
            hops=hops,
            elapsed_ms=elapsed,
            error="Too many redirects",
        )
    except Exception as e:
        elapsed = int((time.time() - t0) * 1000)
        status = hops[-1].status if hops else 0
        final_url = hops[-1].url if hops else url
        return ProbeResult(
            ok=False,
            final_url=final_url,
            status=status,
            hops=hops,
            elapsed_ms=elapsed,
            error=f"{type(e).__name__}: {e}",
        )


def _probe_with_urllib(
    url: str,
    timeout: float,
    max_redirects: int,
    verify_ssl: bool,
    user_agent: str,
    capture_snippet: bool,
) -> ProbeResult:
    t0 = time.time()
    hops: List[Hop] = []

    # urllib auto-follows redirects by default; we need hop visibility.
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, hdrs, newurl):
            return None

    ctx = None
    if not verify_ssl:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE

    opener = urllib.request.build_opener(NoRedirect())
    cur = url

    try:
        for _ in range(max_redirects + 1):
            req = urllib.request.Request(cur, headers={"User-Agent": user_agent})
            try:
                resp = opener.open(req, timeout=timeout, context=ctx)
                code = getattr(resp, "status", 200) or 200
                hdrs = dict(resp.headers.items())
                loc = hdrs.get("Location")
                hops.append(Hop(url=cur, status=int(code), location=loc))

                elapsed = int((time.time() - t0) * 1000)
                snippet = None
                if capture_snippet:
                    ctype = (hdrs.get("Content-Type") or "").lower()
                    if "text/html" in ctype or "text/plain" in ctype or ctype == "":
                        raw = resp.read(60_000)
                        snippet = raw.decode("utf-8", errors="replace")
                return ProbeResult(
                    ok=True,
                    final_url=cur,
                    status=int(code),
                    hops=hops,
                    elapsed_ms=elapsed,
                    snippet=snippet,
                    headers={str(k): str(v) for k, v in hdrs.items()},
                )
            except urllib.error.HTTPError as e:
                hdrs = dict(e.headers.items()) if e.headers else {}
                loc = hdrs.get("Location")
                hops.append(Hop(url=cur, status=int(e.code), location=loc))

                # Redirect?
                if int(e.code) in (301, 302, 303, 307, 308) and loc:
                    cur = urljoin(cur, loc)
                    continue

                elapsed = int((time.time() - t0) * 1000)
                snippet = None
                if capture_snippet:
                    try:
                        raw = e.read(60_000)
                        snippet = raw.decode("utf-8", errors="replace")
                    except Exception:
                        snippet = None
                return ProbeResult(
                    ok=True,
                    final_url=cur,
                    status=int(e.code),
                    hops=hops,
                    elapsed_ms=elapsed,
                    snippet=snippet,
                    headers={str(k): str(v) for k, v in hdrs.items()},
                )

        elapsed = int((time.time() - t0) * 1000)
        return ProbeResult(
            ok=False,
            final_url=hops[-1].url if hops else url,
            status=hops[-1].status if hops else 0,
            hops=hops,
            elapsed_ms=elapsed,
            error="Too many redirects",
        )
    except Exception as e:
        elapsed = int((time.time() - t0) * 1000)
        status = hops[-1].status if hops else 0
        final_url = hops[-1].url if hops else url
        return ProbeResult(
            ok=False,
            final_url=final_url,
            status=status,
            hops=hops,
            elapsed_ms=elapsed,
            error=f"{type(e).__name__}: {e}",
        )


def probe_url(
    url: str,
    *,
    timeout: float = 8.0,
    max_redirects: int = 8,
    verify_ssl: bool = True,
    user_agent: str = "Sitefixer-WPRepair/1.0",
    capture_snippet: bool = True,
) -> Dict[str, Any]:
    """
    Probes a single URL and returns a serializable dict.
    """
    if requests is not None:
        res = _probe_with_requests(url, timeout, max_redirects, verify_ssl, user_agent, capture_snippet)
    else:
        res = _probe_with_urllib(url, timeout, max_redirects, verify_ssl, user_agent, capture_snippet)

    d = asdict(res)
    # dataclass Hop -> dict already via asdict
    return d


def probe_site(
    base_url: str,
    *,
    paths: Optional[Dict[str, str]] = None,
    timeout: float = 8.0,
    max_redirects: int = 8,
    verify_ssl: bool = True,
    capture_snippet: bool = True,
) -> Dict[str, Any]:
    """
    Probes typical WP endpoints:
      - frontend: /
      - login: /wp-login.php
      - admin: /wp-admin/
      - ajax: /wp-admin/admin-ajax.php
    """
    base = _normalize_base_url(base_url)
    paths = paths or DEFAULT_PATHS

    results: Dict[str, Any] = {
        "base_url": base,
        "targets": {},
        "ok": True,
        "errors": [],
    }

    if not base:
        results["ok"] = False
        results["errors"].append("base_url is empty")
        return results

    for key, p in paths.items():
        url = urljoin(base, p.lstrip("/"))
        r = probe_url(
            url,
            timeout=timeout,
            max_redirects=max_redirects,
            verify_ssl=verify_ssl,
            capture_snippet=capture_snippet,
        )
        results["targets"][key] = r
        if not r.get("ok", False):
            results["ok"] = False

    return results
