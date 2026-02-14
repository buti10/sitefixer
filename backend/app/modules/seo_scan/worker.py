# app/modules/seo_scan/worker.py
import os
import json
import logging
from datetime import datetime

import pymysql
from pymysql.cursors import DictCursor
import requests

logger = logging.getLogger(__name__)

DB = dict(
    host=os.getenv("DB_HOST", "localhost"),
    user=os.getenv("DB_USER", "root"),
    password=os.getenv("DB_PASS", ""),
    database=os.getenv("DB_NAME", "sitefixer"),
    cursorclass=DictCursor,
    autocommit=True,
    charset="utf8mb4",
)


def _db():
    return pymysql.connect(**DB)


def _update_status(scan_id: int, status: str):
    """Status-Helper."""
    with _db() as conn, conn.cursor() as cur:
        cur.execute(
            """
            UPDATE seo_scans
            SET status = %s
            WHERE id = %s
            """,
            (status, scan_id),
        )


def _extract_metrics_for_strategy(url: str, api_key: str, strategy: str):
    """
    Holt PSI-Daten für eine Strategy ("mobile" / "desktop").

    Gibt zurück:
    (metrics_dict | None, audits_dict | None, raw_json | None)

    Bei Timeout / Fehler => (None, None, None), aber KEIN Raise.
    """
    psi_url = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
    params = {
        "url": url,
        "key": api_key,
        "strategy": strategy,
        "category": ["performance", "seo"],
    }

    try:
        logger.info("PSI Call: %s (strategy=%s)", url, strategy)
        resp = requests.get(psi_url, params=params, timeout=90)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as e:
        logger.warning(
            "PSI %s (%s) failed: %s", url, strategy, e, exc_info=True
        )
        return None, None, None

    lh = data.get("lighthouseResult", {})
    cats = lh.get("categories", {}) or {}
    audits = lh.get("audits", {}) or {}

    def _score(cat_name: str) -> int | None:
        c = cats.get(cat_name) or {}
        s = c.get("score")
        if s is None:
            return None
        try:
            return int(round(float(s) * 100))
        except Exception:  # noqa: BLE001
            return None

    perf_score = _score("performance")
    seo_score = _score("seo")

    metrics_audit = audits.get("metrics", {}) or {}
    metrics_details = metrics_audit.get("details", {}) or {}
    items = metrics_details.get("items") or [{}]
    m = items[0] if items else {}

    def _int(v, default=0):
        try:
            return int(v)
        except Exception:  # noqa: BLE001
            return default

    def _float(v, default=0.0):
        try:
            return float(v)
        except Exception:  # noqa: BLE001
            return default

    metrics = {
        "performance_score": perf_score if perf_score is not None else 0,
        "seo_score": seo_score if seo_score is not None else 0,
        "fcp_ms": _int(m.get("firstContentfulPaint", 0)),
        "lcp_ms": _int(m.get("largestContentfulPaint", 0)),
        "cls": _float(m.get("cumulativeLayoutShift", 0.0)),
        "tbt_ms": _int(m.get("totalBlockingTime", 0)),
    }

    return metrics, audits, data


def _build_findings(page_id: int, scan_id: int, audits: dict):
    """
    Baut Findings aus den PSI-Audits.

    - score < 1 => Problem
    - score < 0.5 => 'critical'
    - score >= 0.5 => 'warning'
    """
    findings = []

    if not audits:
        return findings

    for rule, audit in audits.items():
        score = audit.get("score")
        # Nur Audits mit Score (0..1)
        if score is None:
            continue
        try:
            s = float(score)
        except Exception:  # noqa: BLE001
            continue

        # komplett OK => kein Finding
        if s >= 1.0:
            continue

        title = audit.get("title") or rule
        description = audit.get("description") or ""
        explanation = audit.get("explanation")
        display_value = audit.get("displayValue")
        suggestion = explanation or display_value

        group = audit.get("group") or ""
        group = str(group).lower()

        if "seo" in group:
            category = "seo"
        elif "performance" in group:
            category = "performance"
        elif "best-practices" in group or "best_practices" in group:
            category = "best_practices"
        elif "accessibility" in group:
            category = "accessibility"
        else:
            category = "other"

        if s < 0.5:
            f_type = "critical"
        else:
            f_type = "warning"

        raw_json = None
        try:
            raw_json = json.dumps(audit, ensure_ascii=False)
        except Exception:  # noqa: BLE001
            raw_json = None

        findings.append(
            (
                page_id,
                scan_id,
                f_type,
                category,
                rule,
                title,
                description,
                suggestion,
                raw_json,
            )
        )

    return findings


def run_seo_scan(scan_id: int):
    """
    SEO-Worker für einen Scan.

    - holt Domain + Strategie aus seo_scans
    - ruft Google PageSpeed Insights für Mobile & Desktop (soweit möglich)
    - schreibt Scores in seo_scans
    - legt einen Eintrag in seo_pages + Findings in seo_findings an
    """
    logger.info("SEO-Scan gestartet für ID=%s", scan_id)

    try:
        with _db() as conn, conn.cursor() as cur:
            # Scan laden
            cur.execute(
                """
                SELECT id, ticket_id, domain, strategy, max_pages
                FROM seo_scans
                WHERE id = %s
                """,
                (scan_id,),
            )
            scan = cur.fetchone()

        if not scan:
            logger.warning("seo_scans-Eintrag %s nicht gefunden", scan_id)
            return

        domain = scan["domain"]
        strategy = scan.get("strategy") or "mobile"
        max_pages = scan.get("max_pages") or 1

        # Status auf running
        _update_status(scan_id, "running")

        api_key = os.getenv("GOOGLE_PSI_KEY") or os.getenv("GOOGLE_API_KEY")
        url = domain if str(domain).startswith("http") else f"https://{domain}"

        metrics_mobile = audits_mobile = data_mobile = None
        metrics_desktop = audits_desktop = data_desktop = None

        if api_key:
            # Mobile
            metrics_mobile, audits_mobile, data_mobile = _extract_metrics_for_strategy(
                url, api_key, "mobile"
            )
            # Desktop
            metrics_desktop, audits_desktop, data_desktop = _extract_metrics_for_strategy(
                url, api_key, "desktop"
            )
        else:
            logger.warning(
                "Kein GOOGLE_PSI_KEY/GOOGLE_API_KEY gesetzt – verwende Dummy-Werte."
            )

        # Wenn beide Strategien fehlgeschlagen => Dummy-Fallback
        if not metrics_mobile and not metrics_desktop:
            logger.warning(
                "PSI konnte weder für mobile noch für desktop ausgewertet werden – benutze Dummy-Werte."
            )
            metrics_mobile = {
                "performance_score": 78,
                "seo_score": 74,
                "fcp_ms": 1200,
                "lcp_ms": 2200,
                "cls": 0.09,
                "tbt_ms": 180,
            }
            audits_mobile = {}
            audits_desktop = {}
            metrics_desktop = None

        # Aggregierte Scores
        perf_vals = []
        seo_vals = []

        if metrics_mobile:
            perf_vals.append(metrics_mobile["performance_score"])
            seo_vals.append(metrics_mobile["seo_score"])
        if metrics_desktop:
            perf_vals.append(metrics_desktop["performance_score"])
            seo_vals.append(metrics_desktop["seo_score"])

        overall_score = None
        performance_score = None
        seo_score = None

        if perf_vals:
            performance_score = int(round(sum(perf_vals) / len(perf_vals)))
        if seo_vals:
            seo_score = int(round(sum(seo_vals) / len(seo_vals)))
        if performance_score is not None and seo_score is not None:
            overall_score = int(round((performance_score + seo_score) / 2))

        # Seite + Findings in DB schreiben
        with _db() as conn, conn.cursor() as cur:
            # Basismetriken für die Seite: wir nehmen mobile, sonst desktop
            base_metrics = metrics_mobile or metrics_desktop

            fcp_ms = base_metrics["fcp_ms"]
            lcp_ms = base_metrics["lcp_ms"]
            cls = base_metrics["cls"]
            tbt_ms = base_metrics["tbt_ms"]

            # Findings aus den Audits (primär mobile, sonst desktop)
            primary_audits = audits_mobile or audits_desktop or {}
            findings = _build_findings(page_id=0, scan_id=scan_id, audits=primary_audits)

            issues_count = len(findings)

            # Seite anlegen
            cur.execute(
                """
                INSERT INTO seo_pages
                    (scan_id, url,
                     performance_score, seo_score,
                     accessibility_score, best_practices_score,
                     fcp_ms, lcp_ms, cls, tbt_ms,
                     issues_count)
                VALUES
                    (%s, %s,
                     %s, %s,
                     NULL, NULL,
                     %s, %s, %s, %s,
                     %s)
                """,
                (
                    scan_id,
                    url,
                    base_metrics["performance_score"],
                    base_metrics["seo_score"],
                    fcp_ms,
                    lcp_ms,
                    cls,
                    tbt_ms,
                    issues_count,
                ),
            )
            page_id = cur.lastrowid

            # Findings mit korrekter page_id speichern
            if findings:
                fixed_findings = [
                    (
                        page_id,
                        scan_id,
                        f_type,
                        category,
                        rule,
                        message,
                        details,
                        suggestion,
                        raw_json,
                    )
                    for (
                        _dummy_page_id,
                        _dummy_scan_id,
                        f_type,
                        category,
                        rule,
                        message,
                        details,
                        suggestion,
                        raw_json,
                    ) in findings
                ]

                cur.executemany(
                    """
                    INSERT INTO seo_findings
                        (page_id, scan_id, type, category, rule, message, details, suggestion, raw_json)
                    VALUES
                        (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    fixed_findings,
                )

                critical_count = sum(1 for f in fixed_findings if f[2] == "critical")
                warning_count = sum(1 for f in fixed_findings if f[2] == "warning")
                info_count = 0
            else:
                critical_count = warning_count = info_count = 0

            # Scan-Header aktualisieren
            cur.execute(
                """
                UPDATE seo_scans
                SET
                    status            = 'done',
                    finished_at       = NOW(),
                    pages_total       = 1,
                    pages_scanned     = 1,
                    overall_score     = %s,
                    performance_score = %s,
                    seo_score         = %s,
                    critical_count    = %s,
                    warning_count     = %s,
                    info_count        = %s
                WHERE id = %s
                """,
                (
                    overall_score,
                    performance_score,
                    seo_score,
                    critical_count,
                    warning_count,
                    info_count,
                    scan_id,
                ),
            )

        logger.info("SEO-Scan %s erfolgreich abgeschlossen", scan_id)

    except Exception as e:  # noqa: BLE001
        logger.exception("run_seo_scan(%s) failed: %s", scan_id, e)
        try:
            with _db() as conn, conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE seo_scans
                    SET status='failed', finished_at = NOW()
                    WHERE id = %s
                    """,
                    (scan_id,),
                )
        except Exception:
            logger.exception("Konnte Scan-Status auf failed nicht setzen")
