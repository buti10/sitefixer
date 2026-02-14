# app/report_routes.py
import os, json, uuid, datetime
from flask import Blueprint, request, jsonify, current_app, send_from_directory, abort

bp = Blueprint("reports", __name__)  # kein url_prefix, wir definieren pro-Route

# Speicherpfade (unter instance/)
def _base_dir():
    base = os.path.join(current_app.instance_path, "reports")
    os.makedirs(base, exist_ok=True)
    return base

def _rid(): return uuid.uuid4().hex
def _now_iso(): return datetime.datetime.utcnow().replace(microsecond=0).isoformat() + "Z"

def _meta_path(rid): return os.path.join(_base_dir(), f"{rid}.json")
def _html_path(rid): return os.path.join(_base_dir(), f"{rid}.html")
def _pdf_path(rid):  return os.path.join(_base_dir(), f"{rid}.pdf")

def _write_meta(meta: dict):
    with open(_meta_path(meta["id"]), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False, indent=2)

def _read_meta(rid: str):
    p = _meta_path(rid)
    if not os.path.exists(p): return None
    with open(p, "r", encoding="utf-8") as f: return json.load(f)

def _list_meta_for_scan(scan_id: str):
    out = []
    for fn in os.listdir(_base_dir()):
        if not fn.endswith(".json"): continue
        try:
            meta = json.load(open(os.path.join(_base_dir(), fn), "r", encoding="utf-8"))
            if meta.get("scan_id") == str(scan_id):
                out.append(meta)
        except Exception:
            continue
    # neueste oben
    out.sort(key=lambda m: m.get("created_at",""), reverse=True)
    return out

def _build_html(title: str, payload: dict) -> str:
    scan = payload.get("scan", {}) or {}
    findings = payload.get("findings", []) or []
    summary  = (scan.get("summary") or {})
    counts   = summary.get("counts") or {}

    def esc(s): 
        return ("" if s is None else str(s)).replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

    rows = []
    for it in findings:
        rows.append(f"""
          <tr>
            <td>{esc(it.get("path"))}</td>
            <td>{esc(it.get("rule") or it.get("type") or "")}</td>
            <td>{esc(it.get("severity") or it.get("level") or "")}</td>
            <td>{esc(it.get("reason") or it.get("msg") or "")}</td>
          </tr>
        """)

    return f"""<!doctype html>
<html lang="de"><meta charset="utf-8" />
<title>{esc(title)}</title>
<style>
  body{{font:14px/1.4 system-ui,-apple-system,Segoe UI,Roboto,Ubuntu; color:#111;}}
  .box{{border:1px solid #e5e7eb; border-radius:12px; padding:16px; margin:12px 0;}}
  table{{width:100%; border-collapse:collapse;}}
  th,td{{border-top:1px solid #eee; padding:8px 10px; text-align:left; font-size:13px;}}
  th{{background:#fafafa;}}
  .kpi{{display:inline-block; margin-right:16px;}}
  .kpi b{{font-size:18px}}
</style>
<h1>{esc(title)}</h1>
<div class="box">
  <div class="kpi">Total: <b>{esc(counts.get('total',0))}</b></div>
  <div class="kpi">Clean: <b>{esc(counts.get('clean',0))}</b></div>
  <div class="kpi">Suspicious: <b>{esc(counts.get('suspicious',0))}</b></div>
  <div class="kpi">Malicious: <b>{esc(counts.get('malicious',0))}</b></div>
</div>

<div class="box">
  <h3>Findings</h3>
  <table>
    <thead><tr><th>Pfad</th><th>Regel</th><th>Schwere</th><th>Hinweis</th></tr></thead>
    <tbody>
      {''.join(rows) if rows else '<tr><td colspan="4">Keine Findings.</td></tr>'}
    </tbody>
  </table>
</div>
</html>"""

# ---------- API ----------

# Anlegen (Front schickt Daten mit – kein DB-Zugriff nötig)
@bp.post("/api/malware/reports")
def create_report():
    data = request.get_json(force=True) or {}
    scan_id = str(data.get("scan_id") or "").strip()
    if not scan_id: return jsonify({"error":"scan_id required"}), 400

    payload = data.get("data") or {}
    title = (data.get("title") or f"Malware-Scan #{scan_id}").strip()

    rid = _rid()
    html = _build_html(title, payload)
    with open(_html_path(rid), "w", encoding="utf-8") as f:
        f.write(html)

    # naive PDF aus HTML → nur Text (reportlab), ohne harte Systemabhängigkeiten
    # Wenn reportlab fehlt, lassen wir PDF aus (url_pdf=None)
    url_pdf = None
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import cm
        # sehr einfache Textversion
        c = canvas.Canvas(_pdf_path(rid), pagesize=A4)
        width, height = A4
        text = c.beginText(2*cm, height-2*cm)
        text.setFont("Helvetica", 12)
        text.textLine(title)
        text.moveCursor(0, 10)
        text.setFont("Helvetica", 9)
        text.textLine(f"Scan-ID: {scan_id}  •  erstellt: {_now_iso()}")
        text.moveCursor(0, 14)
        text.textLine("Hinweis: Dies ist eine vereinfachte PDF-Zusammenfassung. Die vollständigen Details finden Sie in der HTML-Version.")
        c.drawText(text); c.showPage(); c.save()
        url_pdf = f"/api/reports/{rid}/pdf"
    except Exception:
        url_pdf = None

    meta = {
        "id": rid,
        "scan_id": scan_id,
        "title": title,
        "created_at": _now_iso(),
        "url_html": f"/api/reports/{rid}/html",
        "url_pdf":  url_pdf,
    }
    _write_meta(meta)
    return jsonify(meta)

# Liste je Scan
@bp.get("/api/malware/reports/<scan_id>")
def list_reports(scan_id):
    return jsonify(_list_meta_for_scan(str(scan_id)))

# Löschen
@bp.delete("/api/malware/reports/<rid>")
def delete_report(rid):
    meta = _read_meta(rid)
    if not meta: return jsonify({"error":"not found"}), 404
    for p in (_meta_path(rid), _html_path(rid), _pdf_path(rid)):
        try:
            if os.path.exists(p): os.remove(p)
        except Exception: pass
    return jsonify({"ok": True})

# Downloads
@bp.get("/api/reports/<rid>/html")
def get_html(rid):
    meta = _read_meta(rid)
    if not meta: return abort(404)
    return send_from_directory(_base_dir(), f"{rid}.html", as_attachment=True, download_name=f"{rid}.html")

@bp.get("/api/reports/<rid>/pdf")
def get_pdf(rid):
    meta = _read_meta(rid)
    if not meta: return abort(404)
    p = _pdf_path(rid)
    if not os.path.exists(p): return jsonify({"error":"pdf not available"}), 404
    return send_from_directory(_base_dir(), f"{rid}.pdf", as_attachment=True, download_name=f"{rid}.pdf")

# Einzelnen Report löschen
@bp_report.route("/<int:report_id>", methods=["DELETE"])
def delete_report(report_id):
    r = Report.query.get_or_404(report_id)
    db.session.delete(r)
    db.session.commit()
    return jsonify({"ok": True})

# Alle Reports zu einem Ticket löschen
@bp_report.route("/ticket/<int:ticket_id>", methods=["DELETE"])
def delete_reports_for_ticket(ticket_id):
    deleted = Report.query.filter_by(ticket_id=ticket_id).delete()
    db.session.commit()
    return jsonify({"ok": True, "deleted": deleted})

