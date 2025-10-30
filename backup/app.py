from flask import Flask, redirect, url_for, render_template, jsonify, request
import threading
import mysql.connector
from malware_scan_worker import malware_scan_worker
from config import WP_DB_CONFIG
from wp_customers import get_wp_customers, get_kundendetails

app = Flask(__name__)
DB_CONFIG = dict(
    host='localhost',
    user='scanner_user',
    password='Sitefixerscanner2025/',
    database='sitefixer_scanner'
)

@app.route('/', methods=['GET'])
def dashboard():
    search = request.args.get('search', '').lower()
    kunden = get_wp_customers()
    if search:
        filtered = [k for k in kunden if search in k['name'].lower() or search in k['domain'].lower()]
    else:
        filtered = kunden
    return render_template('dashboard.html', kunden=filtered, search=search)

@app.route('/kunde/<int:ticket_id>')
def kunde_details(ticket_id):
    kunden = get_wp_customers()
    kunde = next((k for k in kunden if k['ticket_id'] == ticket_id), None)
    if not kunde:
        return "Kunde nicht gefunden", 404

    zugang = get_kundendetails(ticket_id)

    geplante_scans = {}   # TODO: aus DB holen
    scanhistory = []      # TODO: aus DB holen
    return render_template(
        'kundendetails.html',
        kunde=kunde,
        zugang=zugang,
        geplante_scans=geplante_scans,
        scanhistory=scanhistory
    )

@app.route('/scan/start/<int:kunden_id>', methods=['POST'])
def scan_start(kunden_id):
    zugang = get_kundendetails(kunden_id)
    if not zugang or not zugang.get('ftp_host'):
        return "Keine Zugangsdaten für diesen Kunden gefunden!", 404

    ftp_host = zugang['ftp_host']
    ftp_user = zugang['ftp_user']
    ftp_pass = zugang['ftp_pass']

    db = mysql.connector.connect(**DB_CONFIG)
    cursor = db.cursor()

    # 1. Job anlegen
    cursor.execute(
        "INSERT INTO scan_jobs (kunden_id, status, type) VALUES (%s, 'pending', 'malware')", (kunden_id,)
    )
    db.commit()
    scan_id = cursor.lastrowid

    # 2. DIREKT Fortschritt anlegen
    cursor.execute(
        "INSERT INTO scan_progress (scan_id, checked_files, total_files, current_file, rot, orange, gruen, updated_at) VALUES (%s, 0, 0, '', 0, 0, 0, NOW())",
        (scan_id,)
    )
    db.commit()
    cursor.close()
    db.close()

    # 3. Worker starten
    t = threading.Thread(target=malware_scan_worker, args=(scan_id, ftp_host, ftp_user, ftp_pass, DB_CONFIG))
    t.daemon = True
    t.start()

    return redirect(url_for('scan_status_page', scan_id=scan_id))

@app.route("/scan/findings/<int:scan_id>")
def scan_findings(scan_id):
    import mysql.connector
    db = mysql.connector.connect(**DB_CONFIG)
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT file, level, desc_text, line, snippet FROM scan_results WHERE scan_id=%s", (scan_id,))
    results = [
        {
            "file": row["file"],
            "level": row["level"],
            "pattern": row["desc_text"],
            "line": row["line"],
            "snippet": row["snippet"]
        }
        for row in cur.fetchall()
    ]
    cur.close()
    db.close()
    return jsonify(results)


@app.route('/scan/status/<int:scan_id>')
def scan_status_page(scan_id):
    db = mysql.connector.connect(**DB_CONFIG)
    cursor = db.cursor(dictionary=True)
    cursor.execute("SELECT *, TIMESTAMPDIFF(SECOND, started_at, updated_at) as duration, IF(total_files > 0, ROUND(checked_files/total_files*100), 0) as percent FROM scan_progress WHERE scan_id=%s", (scan_id,))
    scan = cursor.fetchone()
    cursor.close()
    db.close()
    # Hier:
    return render_template('scan_status.html', scan_id=scan_id, scan=scan)


@app.route("/scan/progress/<int:scan_id>")
def scan_progress(scan_id):
    import mysql.connector
    db = mysql.connector.connect(**DB_CONFIG)
    cur = db.cursor(dictionary=True)
    cur.execute("SELECT * FROM scan_progress WHERE scan_id=%s", (scan_id,))
    data = cur.fetchone() or {}
    cur.close()
    db.close()
    # Fallback-Werte, falls noch kein Eintrag existiert
    for key in ["checked_files", "total_files", "current_file", "rot", "orange", "gruen"]:
        data.setdefault(key, 0)
    return jsonify(data)


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
