# app/modules/seo_scan/routes.py
import os
import pymysql
from pymysql.cursors import DictCursor

from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required

from redis import Redis
from rq import Queue

from .worker import run_seo_scan

REDIS_URL = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
redis_conn = Redis.from_url(REDIS_URL)
seo_queue = Queue("seo", connection=redis_conn)

seo_bp = Blueprint("seo", __name__, url_prefix="/api/seo")

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


@seo_bp.get("/ping")
def ping():
    return jsonify({"ok": True, "module": "seo_scan"})


@seo_bp.get("/scans")
@jwt_required(optional=True)
def list_scans():
    """
    GET /api/seo/scans?ticket_id=1

    Liefert alle SEO-Scans zu einem Ticket (neuester zuerst).
    Zusätzlich werden Deltas zum jeweils vorherigen Scan berechnet:
    - delta_overall
    - delta_performance
    - delta_seo
    - delta_critical
    - delta_warning
    - delta_info
    """
    ticket_id = request.args.get("ticket_id", type=int)
    if not ticket_id:
        return jsonify({"ok": False, "error": "ticket_id required"}), 400

    try:
        with _db() as conn, conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                    s.id,
                    s.ticket_id,
                    s.domain,
                    s.strategy,
                    s.max_pages,
                    s.status,
                    s.overall_score,
                    s.performance_score,
                    s.seo_score,
                    s.accessibility_score,
                    s.best_practices_score,
                    s.critical_count,
                    s.warning_count,
                    s.info_count,
                    s.is_baseline,
                    s.created_at
                FROM seo_scans s
                WHERE s.ticket_id = %s
                ORDER BY s.created_at DESC, s.id DESC
                """,
                (ticket_id,),
            )
            rows = cur.fetchall() or []

        # --- Deltas zum jeweils vorherigen Scan (zeitlich gesehen) berechnen ---
        # Reihenfolge aus DB: neuester zuerst. Für Deltas gehen wir von alt -> neu.
        def _val(row, key):
            v = row.get(key)
            return v if isinstance(v, (int, float)) and v is not None else 0

        rows_asc = list(reversed(rows))
        prev = None
        for r in rows_asc:
            if prev is None:
                # erster (ältester) Scan: keine Deltas
                r["delta_overall"] = None
                r["delta_performance"] = None
                r["delta_seo"] = None
                r["delta_critical"] = None
                r["delta_warning"] = None
                r["delta_info"] = None
            else:
                r["delta_overall"] = _val(r, "overall_score") - _val(prev, "overall_score")
                r["delta_performance"] = _val(r, "performance_score") - _val(
                    prev, "performance_score"
                )
                r["delta_seo"] = _val(r, "seo_score") - _val(prev, "seo_score")
                r["delta_critical"] = _val(prev, "critical_count") - _val(
                    r, "critical_count"
                )  # Verbesserungen => positiv
                r["delta_warning"] = _val(prev, "warning_count") - _val(
                    r, "warning_count"
                )
                r["delta_info"] = _val(prev, "info_count") - _val(r, "info_count")
            prev = r
        # rows ist eine Liste der gleichen Dicts (nur andere Reihenfolge),
        # daher sind dort jetzt auch die Delta-Felder vorhanden.

        return jsonify({"ok": True, "scans": rows})
    except Exception as e:  # noqa: BLE001
        current_app.logger.exception("seo_scan list_scans failed")
        return jsonify({"ok": False, "error": str(e)}), 500


@seo_bp.post("/scans")
@jwt_required(optional=True)
def create_scan():
    data = request.get_json() or {}
    ticket_id = data.get("ticket_id")
    domain = data.get("domain")
    max_pages = data.get("max_pages") or 100
    strategy = data.get("strategy") or "mobile"

    if not ticket_id or not domain:
        return (
            jsonify(
                {
                    "ok": False,
                    "error": "ticket_id and domain are required",
                }
            ),
            400,
        )

    try:
        with _db() as conn, conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO seo_scans
                    (ticket_id, domain, strategy, max_pages, status,
                     pages_total, pages_scanned,
                     overall_score, performance_score, seo_score,
                     critical_count, warning_count, info_count,
                     is_baseline, created_at)
                VALUES
                    (%s, %s, %s, %s, 'pending',
                     0, 0,
                     NULL, NULL, NULL,
                     0, 0, 0,
                     0, NOW())
                """,
                (ticket_id, domain, strategy, max_pages),
            )
            scan_id = cur.lastrowid

        # === Job in die RQ-Queue 'seo' schieben ===
        seo_queue.enqueue(
            run_seo_scan,
            scan_id,
            job_timeout=600,
            result_ttl=86400,
            description=f"SEO scan for ticket {ticket_id} ({domain})",
        )

        return jsonify({"ok": True, "scan_id": scan_id})
    except Exception as e:  # noqa: BLE001
        current_app.logger.exception("seo_scan create_scan failed")
        return jsonify({"ok": False, "error": str(e)}), 500


@seo_bp.get("/scans/<int:scan_id>/findings")
@jwt_required(optional=True)
def get_scan_findings(scan_id: int):
    """
    GET /api/seo/scans/<scan_id>/findings
    Liefert Struktur:
    {
      ok: true,
      scan_id: 2,
      scan: {...},
      pages: [
        {
          id, url, performance_score, seo_score, ...,
          issues_count,
          findings: [
            { id, type, category, rule, message, details, suggestion, ... }
          ]
        },
        ...
      ]
    }
    """
    try:
        with _db() as conn, conn.cursor() as cur:
            # Scan selbst holen
            cur.execute(
                """
                SELECT
                    id,
                    ticket_id,
                    domain,
                    strategy,
                    max_pages,
                    status,
                    overall_score,
                    performance_score,
                    seo_score,
                    accessibility_score,
                    best_practices_score,
                    critical_count,
                    warning_count,
                    info_count,
                    is_baseline,
                    created_at
                FROM seo_scans
                WHERE id = %s
                """,
                (scan_id,),
            )
            scan = cur.fetchone()

            if not scan:
                return jsonify({"ok": False, "error": "scan not found"}), 404

            # Seiten zu diesem Scan
            cur.execute(
                """
                SELECT
                    id,
                    scan_id,
                    url,
                    performance_score,
                    seo_score,
                    accessibility_score,
                    best_practices_score,
                    fcp_ms,
                    lcp_ms,
                    cls,
                    tbt_ms,
                    issues_count,
                    created_at
                FROM seo_pages
                WHERE scan_id = %s
                ORDER BY id ASC
                """,
                (scan_id,),
            )
            pages = cur.fetchall() or []

            page_map = {p["id"]: {**p, "findings": []} for p in pages}

            if page_map:
                page_ids = list(page_map.keys())
                # Findings für alle Seiten dieses Scans
                in_clause = ",".join(["%s"] * len(page_ids))
                params = page_ids + [scan_id]
                cur.execute(
                    f"""
                    SELECT
                        id,
                        page_id,
                        scan_id,
                        type,
                        category,
                        rule,
                        message,
                        details,
                        suggestion,
                        raw_json,
                        created_at
                    FROM seo_findings
                    WHERE page_id IN ({in_clause})
                      AND scan_id = %s
                    ORDER BY
                        FIELD(type, 'critical','warning','info'),
                        id ASC
                    """,
                    params,
                )
                findings = cur.fetchall() or []

                for f in findings:
                    page_id = f["page_id"]
                    if page_id in page_map:
                        page_map[page_id]["findings"].append(f)

        return jsonify(
            {
                "ok": True,
                "scan_id": scan_id,
                "scan": scan,
                "pages": list(page_map.values()),
            }
        )
    except Exception as e:  # noqa: BLE001
        current_app.logger.exception("seo_scan get_scan_findings failed")
        return jsonify({"ok": False, "error": str(e)}), 500


@seo_bp.post("/scans/<int:scan_id>/mock_fill")
@jwt_required(optional=True)
def mock_fill_scan(scan_id: int):
    """
    Nur zum Testen:
    Legt für einen bestehenden Scan eine Beispiel-Seite + Beispiel-Findings an
    und aktualisiert die Zähler im seo_scans-Eintrag.
    """
    try:
        with _db() as conn, conn.cursor() as cur:
            # Scan laden
            cur.execute(
                """
                SELECT id, ticket_id, domain
                FROM seo_scans
                WHERE id = %s
                """,
                (scan_id,),
            )
            scan = cur.fetchone()
            if not scan:
                return jsonify({"ok": False, "error": "scan not found"}), 404

            # Beispiel-Seite anlegen
            page_url = scan["domain"] or "https://example.com/"
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
                     %s, %s,
                     %s, %s, %s, %s,
                     %s)
                """,
                (
                    scan_id,
                    page_url,
                    78,
                    72,  # performance_score, seo_score
                    85,
                    80,  # accessibility_score, best_practices_score
                    1200,
                    2200,  # fcp_ms, lcp_ms
                    0.09,
                    180,  # cls, tbt_ms
                    4,  # issues_count
                ),
            )
            page_id = cur.lastrowid

            # Beispiel-Findings für diese Seite
            findings = [
                (
                    page_id,
                    scan_id,
                    "critical",
                    "performance",
                    "render-blocking-js",
                    "Es werden render-blocking JavaScript-Dateien im <head> geladen.",
                    "Mehrere JS-Dateien werden ohne defer/async im Kopf geladen und blockieren das Rendering.",
                    "Verschiebe nicht kritische JS-Dateien ans Ende der Seite oder nutze 'defer'.",
                    None,  # raw_json
                ),
                (
                    page_id,
                    scan_id,
                    "warning",
                    "images",
                    "missing-alt",
                    "Mindestens ein Bild hat kein Alt-Attribut.",
                    "Einige Bilder haben kein beschreibendes alt-Attribut.",
                    "Füge beschreibende Alt-Texte für alle Bilder hinzu.",
                    None,
                ),
                (
                    page_id,
                    scan_id,
                    "info",
                    "seo",
                    "duplicate-title",
                    "Der Seitentitel ist relativ generisch.",
                    "Der Title-Tag ist wenig aussagekräftig und wiederholt sich evtl. auf mehreren Seiten.",
                    "Formuliere einen einzigartigen, beschreibenden Title mit Haupt-Keyword.",
                    None,
                ),
            ]

            cur.executemany(
                """
                INSERT INTO seo_findings
                    (page_id, scan_id, type, category, rule, message, details, suggestion, raw_json)
                VALUES
                    (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                findings,
            )

            # Zähler im Scan aktualisieren
            critical_count = sum(1 for f in findings if f[2] == "critical")
            warning_count = sum(1 for f in findings if f[2] == "warning")
            info_count = sum(1 for f in findings if f[2] == "info")

            cur.execute(
                """
                UPDATE seo_scans
                SET
                    critical_count = critical_count + %s,
                    warning_count  = warning_count  + %s,
                    info_count     = info_count     + %s,
                    pages_total    = pages_total + 1,
                    pages_scanned  = pages_scanned + 1
                WHERE id = %s
                """,
                (critical_count, warning_count, info_count, scan_id),
            )

        return jsonify({"ok": True, "scan_id": scan_id, "page_id": page_id})
    except Exception as e:  # noqa: BLE001
        current_app.logger.exception("seo_scan mock_fill_scan failed")
        return jsonify({"ok": False, "error": str(e)}), 500


@seo_bp.delete("/scans/<int:scan_id>")
@jwt_required(optional=True)
def delete_scan(scan_id: int):
    """
    DELETE /api/seo/scans/<scan_id>?ticket_id=1

    Löscht einen Scan + zugehörige Seiten + Findings (+ optional Raw-Daten).
    Optionaler ticket_id-Parameter sorgt dafür, dass nur Scans
    des erwarteten Tickets gelöscht werden.
    """
    ticket_id_param = request.args.get("ticket_id", type=int)

    try:
        with _db() as conn, conn.cursor() as cur:
            # Scan laden
            cur.execute(
                """
                SELECT id, ticket_id
                FROM seo_scans
                WHERE id = %s
                """,
                (scan_id,),
            )
            scan = cur.fetchone()
            if not scan:
                return jsonify({"ok": False, "error": "scan not found"}), 404

            if ticket_id_param and scan["ticket_id"] != ticket_id_param:
                return (
                    jsonify(
                        {
                            "ok": False,
                            "error": "scan does not belong to given ticket_id",
                        }
                    ),
                    403,
                )

            # Zuerst Findings und Seiten löschen
            cur.execute(
                "DELETE FROM seo_findings WHERE scan_id = %s",
                (scan_id,),
            )
            cur.execute(
                "DELETE FROM seo_pages WHERE scan_id = %s",
                (scan_id,),
            )

            # Optional: Rohdaten-Tabelle, falls vorhanden
            try:
                cur.execute(
                    "DELETE FROM seo_scan_raw WHERE scan_id = %s",
                    (scan_id,),
                )
            except Exception:
                # Tabelle existiert evtl. (noch) nicht – ignorieren
                pass

            # Zuletzt den Scan selbst
            cur.execute(
                "DELETE FROM seo_scans WHERE id = %s",
                (scan_id,),
            )

        return jsonify({"ok": True, "deleted": scan_id})
    except Exception as e:  # noqa: BLE001
        current_app.logger.exception("seo_scan delete_scan failed")
        return jsonify({"ok": False, "error": str(e)}), 500
