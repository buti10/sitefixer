from __future__ import annotations

import os
import time
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from sqlalchemy import desc
import requests

from app import create_app
from app.extensions import db
from app.modules.tickets_public.models import Ticket, TicketScan, TicketAccess
from app.core.crypto import decrypt_from_b64

log = logging.getLogger("tickets_worker")


def _utcnow():
    return datetime.now(timezone.utc)


def _normalize_url(url: str) -> str:
    u = (url or "").strip()
    if not u:
        return u
    if not (u.startswith("http://") or u.startswith("https://")):
        u = "https://" + u
    return u


def _looks_like_wordpress(resp: requests.Response, body_snippet: str) -> bool:
    h = {k.lower(): v for k, v in (resp.headers or {}).items()}
    xgen = (h.get("x-generator") or "").lower()
    ct = (h.get("content-type") or "").lower()

    if "wordpress" in xgen:
        return True
    if "wp-content" in body_snippet or "wp-includes" in body_snippet:
        return True
    if "xmlrpc.php" in body_snippet:
        return True
    if "text/html" in ct and "wp-json" in body_snippet:
        return True
    return False


def _do_preflight(site_url: str, timeout: int = 20) -> Dict[str, Any]:
    url = _normalize_url(site_url)
    started = time.time()

    sess = requests.Session()
    sess.headers.update(
        {
            "User-Agent": "SitefixerPreflight/1.0 (+https://sitefixer.de)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        }
    )

    resp = sess.get(url, allow_redirects=True, timeout=timeout, verify=True)
    elapsed_ms = int((time.time() - started) * 1000)

    final_url = str(resp.url)
    status_code = int(resp.status_code)

    try:
        text = resp.text or ""
    except Exception:
        text = ""
    snippet = text[:4000]

    wp_likely = _looks_like_wordpress(resp, snippet)

    return {
        "status_code": status_code,
        "final_url": final_url,
        "elapsed_ms": elapsed_ms,
        "headers": dict(resp.headers) if resp.headers else {},
        "wp": {"is_wordpress_likely": bool(wp_likely)},
        "body_snippet": snippet[:2000],
    }


def _do_access_verify(ticket: Ticket, timeout: int = 20) -> Dict[str, Any]:
    """
    Prüft SFTP Zugang (minimal).
    Ergebnis:
      ok: bool
      method: "sftp"
      notes: str|null
    """
    acc = (TicketAccess.query
       .filter_by(ticket_id=ticket.id)
       .order_by(desc(TicketAccess.id))
       .first())
    if not acc:
        return {"ok": False, "method": "sftp", "notes": "no access record"}

    host = (acc.sftp_host or "").strip()
    user = (acc.sftp_user or "").strip()
    port = int(acc.sftp_port or 22)
    try:
        pw = decrypt_from_b64(acc.sftp_pass_enc)
    except Exception as e:
        return {"ok": False, "method": "sftp", "notes": f"decrypt failed: {type(e).__name__}"}


    if not host or not user or not pw:
        return {"ok": False, "method": "sftp", "notes": "missing sftp credentials"}

    # Paramiko nur laden, wenn nötig (sauber für Umgebungen)
    import paramiko

    started = time.time()
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        ssh.connect(
            hostname=host,
            port=port,
            username=user,
            password=pw,
            look_for_keys=False,
            allow_agent=False,
            timeout=timeout,
            banner_timeout=timeout,
            auth_timeout=timeout,
        )
        sftp = ssh.open_sftp()
        try:
            _ = sftp.listdir(".")  # minimaler read-test
        finally:
            try:
                sftp.close()
            except Exception:
                pass

        elapsed_ms = int((time.time() - started) * 1000)

        # markieren als verified
        acc.verified = True
        db.session.commit()

        return {"ok": True, "method": "sftp", "elapsed_ms": elapsed_ms, "notes": None}

    except Exception as e:
        return {"ok": False, "method": "sftp", "notes": str(e)[:300]}

    finally:
        try:
            ssh.close()
        except Exception:
            pass


def _claim_next_scan() -> Optional[TicketScan]:
    """
    Holt den nächsten queued Scan (preflight oder access_verify) und setzt running.
    """
    scan = (
        TicketScan.query.filter(TicketScan.status == "queued")
        .filter(TicketScan.scan_type.in_(["preflight", "access_verify"]))
        .order_by(TicketScan.id.asc())
        .first()
    )
    if not scan:
        return None

    scan.status = "running"
    scan.started_at = _utcnow()
    scan.error_message = None
    db.session.commit()

    log.info("claimed scan_id=%s ticket_id=%s type=%s", scan.id, scan.ticket_id, scan.scan_type)
    return scan


def _enqueue_scan(ticket_id: int, scan_type: str) -> None:
    db.session.add(TicketScan(ticket_id=ticket_id, scan_type=scan_type, status="queued"))
    db.session.commit()


def _process_scan(scan: TicketScan) -> None:
    ticket = Ticket.query.get(scan.ticket_id)
    if not ticket:
        scan.status = "error"
        scan.error_message = "ticket not found"
        scan.finished_at = _utcnow()
        db.session.commit()
        return

    try:
        if scan.scan_type == "preflight":
            result = _do_preflight(ticket.site_url or "")
            scan.result_json = result
            scan.status = "done"
            scan.finished_at = _utcnow()

            sc = int(result.get("status_code") or 0)
            wp_likely = bool((result.get("wp") or {}).get("is_wordpress_likely"))

            if sc <= 0 or sc >= 400:
                ticket.status = "failed"
            else:
                # erreichbar:
                if wp_likely:
                    # Wenn Zugangsdaten vorhanden -> direkt access_verify queue
                    acc = TicketAccess.query.filter_by(ticket_id=ticket.id).first()
                    has_sftp = bool(acc and acc.sftp_host and acc.sftp_user and acc.sftp_pass_enc)
                    if has_sftp:
                        ticket.status = "scanning"
                        db.session.commit()
                        _enqueue_scan(ticket.id, "access_verify")
                    else:
                        ticket.status = "needs_access"
                else:
                    # Für jetzt: trotzdem weiter als "scanning" (du kannst später "manual_review" machen)
                    ticket.status = "scanning"

            db.session.commit()
            log.info(
                "done preflight scan_id=%s ticket_id=%s status_code=%s wp=%s",
                scan.id, scan.ticket_id, result.get("status_code"), wp_likely
            )
            return

        if scan.scan_type == "access_verify":
            result = _do_access_verify(ticket)
            scan.result_json = result
            scan.status = "done"
            scan.finished_at = _utcnow()

            if result.get("ok") is True:
                # Zugang OK -> bereit für nächste Phase (malware/reparatur)
                ticket.status = "ready"
            else:
                ticket.status = "needs_access"

            db.session.commit()
            log.info("done access_verify scan_id=%s ticket_id=%s ok=%s", scan.id, scan.ticket_id, result.get("ok"))
            return

        # unbekannter scan type
        scan.status = "error"
        scan.error_message = f"unknown scan_type {scan.scan_type}"
        scan.finished_at = _utcnow()
        db.session.commit()

    except Exception as e:
        db.session.rollback()
        scan.status = "error"
        scan.error_message = str(e)[:500]
        scan.finished_at = _utcnow()
        db.session.commit()
        log.exception("scan failed scan_id=%s ticket_id=%s type=%s", scan.id, scan.ticket_id, scan.scan_type)


def run_once(idle_sleep: float = 2.0) -> None:
    # Wichtig: sicherstellen, dass wir keinen offenen Snapshot halten
    try:
        scan = _claim_next_scan()
        if not scan:
            db.session.rollback()   # Transaktion schließen -> neue Rows werden sichtbar
            time.sleep(idle_sleep)
            return

        _process_scan(scan)

    except Exception:
        db.session.rollback()
        raise
    finally:
        # Session/Connection aufräumen (wichtig für Worker-Loops)
        try:
            db.session.remove()
        except Exception:
            pass



def run_forever() -> None:
    logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))

    app = create_app()
    db_uri = app.config.get("SQLALCHEMY_DATABASE_URI")
    log.info("tickets worker started pid=%s db=%s", os.getpid(), db_uri)

    idle_sleep = float(os.getenv("PREFLIGHT_IDLE_SLEEP", "2.0"))
    loop_sleep = float(os.getenv("PREFLIGHT_LOOP_SLEEP", "0.2"))

    with app.app_context():
        while True:
            try:
                run_once(idle_sleep=idle_sleep)
            except Exception:
                log.exception("worker loop error")
                time.sleep(2.0)
            time.sleep(loop_sleep)
