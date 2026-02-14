#scan_routes.py
import os, json, datetime
from flask import Blueprint, request, jsonify
import mysql.connector
from redis import Redis
from rq import Queue
from scan_worker import perform_scan  # worker entrypoint


bp = Blueprint("scan", __name__, url_prefix="/api/scan")
redis_conn = Redis(host=os.getenv("REDIS_HOST","localhost"), port=int(os.getenv("REDIS_PORT",6379)))
q = Queue('scans', connection=redis_conn)

def get_db():
    return mysql.connector.connect(
        host=os.getenv("DB_HOST","localhost"),
        user=os.getenv("DB_USER","root"),
        password=os.getenv("DB_PASS",""),
        database=os.getenv("DB_NAME","sitefixer")
    )

@bp.post("/start")
def start_scan():
    data = request.get_json(force=True)
    ticket_id = int(data.get("ticket_id"))
    sid = data.get("sid")
    sftp_root = data.get("sftp_root", "/")
    meta = {"sid": sid, "root": sftp_root}
    db = get_db()
    cur = db.cursor()
    cur.execute("INSERT INTO scans (ticket_id, meta, status) VALUES (%s, %s, %s)",
                (ticket_id, json.dumps(meta), "PENDING"))
    scan_id = cur.lastrowid
    db.commit(); cur.close(); db.close()
    q.enqueue(perform_scan, scan_id, job_timeout=60*60*4)  # up to 4h
    return jsonify({"scan_id": scan_id}), 202

@bp.get("/status/<int:scan_id>")
def scan_status(scan_id):
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT id, ticket_id, status, progress, meta, started_at, finished_at, created_at FROM scans WHERE id=%s", (scan_id,))
    scan = cur.fetchone()
    cur.close(); db.close()
    if scan and scan.get("meta"):
        try:
            scan["meta"] = json.loads(scan["meta"])
        except: pass
    return jsonify(scan or {}), 200

@bp.get("/findings/<int:scan_id>")
def get_findings(scan_id):
    db = get_db()
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT id, path, severity, type, detail, detected_at FROM findings WHERE scan_id=%s ORDER BY detected_at DESC", (scan_id,))
    rows = cur.fetchall()
    cur.close(); db.close()
    for r in rows:
        if r.get("detail"):
            try: r["detail"] = json.loads(r["detail"])
            except: pass
    return jsonify(rows), 200
