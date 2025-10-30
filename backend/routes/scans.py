# backend/routes/scans.py
from flask import Blueprint, request, jsonify
from core.storage.dao import create_scan, get_scan
from jobqueue import enqueue
from scripts.worker import run_scan
import requests, os

bp = Blueprint("scans", __name__)

def load_ticket(ticket_id:int):
    # Falls du schon ein internes Ticket-Model hast, nutze das.
    # Hier Beispiel: hole aus deiner bestehenden API (falls vorhanden)
    # oder aus deiner DB – wichtig ist, dass host/user/pass/domain da sind.
    r = requests.get(f"http://localhost:5000/api/tickets/{ticket_id}", timeout=5)
    r.raise_for_status()
    return r.json()

@bp.post("/api/scans")
def start_scan():
    data = request.get_json(force=True) or {}
    ticket_id = int(data.get("ticket_id", 0))
    scope = data.get("scope", "malware")
    if not ticket_id:
        return jsonify({"error":"ticket_id required"}), 400

    scan_id = create_scan(ticket_id, scope)

    try:
        ticket = load_ticket(ticket_id)
    except Exception as e:
        # Job gar nicht starten, sauber zurückmelden
        return jsonify({"scan_id": scan_id, "warning": f"ticket_load_failed: {e}"}), 202

    enqueue(run_scan, scan_id, ticket)  # Übergibt Domain/SFTP an Worker
    return jsonify({"scan_id": scan_id}), 200

@bp.get("/api/scans/<int:scan_id>")
def get_scan_status(scan_id:int):
    scan, findings = get_scan(scan_id)
    if not scan:
        return jsonify({"error":"not_found"}), 404
    return jsonify({
        "id": scan["id"],
        "ticket_id": scan["ticket_id"],
        "state": scan["state"],
        "progress": {"pct": scan["progress_pct"], "stage": scan["stage"]},
        "summary": scan["summary"],
        "findings": findings
    })
