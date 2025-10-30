# app/scan_bp.py
from __future__ import annotations
from flask import Blueprint, request, jsonify
from datetime import datetime
from typing import Any, Dict
from .tasks_scan import _open_sftp_from_config, _safe_join

from . import db as _db
from .models import Scan, Finding, ScanLog, Report, Base

bp = Blueprint("scan", __name__, url_prefix="/api/scan")

COUNTS_KEYS = ["malicious","suspicious","clean","total","scanned","bytes","errors"]

def _norm_counts(d: Dict[str, Any] | None) -> Dict[str, int]:
    d = d or {}
    out = {}
    for k in COUNTS_KEYS:
        try: out[k] = int(d.get(k, 0))
        except Exception: out[k] = 0
    return out

def _scan_dict(s: Scan) -> Dict[str, Any]:
    return {
        "id": s.id,
        "ticket_id": s.ticket_id,
        "kind": s.kind,
        "status": s.status,
        "progress": int(s.progress or 0),
        "started_at": s.started_at.isoformat(timespec="seconds") if s.started_at else None,
        "finished_at": s.finished_at.isoformat(timespec="seconds") if s.finished_at else None,
        "cms": s.cms,
        "cms_version": s.cms_version,
        "php_version": s.php_version,
        "score": s.score,
        "counts": _norm_counts(s.counts),
        "config": s.config or {},
    }

def _short_scan(s: Scan) -> Dict[str, Any]:
    d = _scan_dict(s)
    keep = ["id","ticket_id","status","progress","score","started_at","finished_at","counts","cms","cms_version"]
    return {k: d.get(k) for k in keep}

def _guard_running(db, ticket_id: int) -> Scan | None:
    return (
        db.query(Scan)
          .filter(Scan.ticket_id==ticket_id, Scan.status.in_(["queued","running"]))
          .order_by(Scan.id.desc())
          .first()
    )

@bp.post("/init-db")
def init_db():
    Base.metadata.create_all(bind=_db.engine)
    return jsonify({"ok": True})
# app/scan_bp.py
@bp.delete("/<int:scan_id>")
def delete_scan(scan_id:int):
    db = _db.session
    s = db.get(Scan, scan_id)
    if not s: return jsonify({"error":"not found"}),404
    # optional: zugehörige Findings/Logs/Reports ebenfalls löschen
    db.delete(s); db.commit()
    return jsonify({"ok":True})

@bp.post("/start")
def start_scan():
    db = _db.session
    data = request.get_json(force=True) or {}
    ticket_id = int(data.get("ticket_id") or 0)
    kind = (data.get("kind") or "deep").strip().lower()
    cfg = data.get("config") or {}

    if ticket_id <= 0:
        return jsonify({"error":"ticket_id required"}), 400

    r = _guard_running(db, ticket_id)
    if r:
        return jsonify({"guard": True, "scan": _scan_dict(r)}), 200

    if kind == "deep":
        root = (cfg.get("root_path") or "").strip()
        sftp = cfg.get("sftp") or {}
        if not (root and sftp.get("host") and sftp.get("user")):
            return jsonify({"error":"Für deep sind root_path, sftp.host, sftp.user erforderlich."}), 400

    s = Scan(
        ticket_id=ticket_id,
        kind=kind,
        status="queued",
        progress=0,
        counts=_norm_counts({"malicious":0,"suspicious":0,"clean":0,"total":0,"scanned":0,"bytes":0,"errors":0}),
        config=cfg or None,
    )
    db.add(s); db.commit()

    try:
        # Lazy import, damit fehlende rq/paramiko das Backend nicht killen
        from .tasks_scan import enqueue_scan
        job = enqueue_scan(s.id)
        s.job_id = getattr(job, "id", None)
        db.commit()
        return jsonify({"scan": _scan_dict(s)}), 201
    except Exception as e:
        # App läuft weiter; Frontend sieht, warum kein Worker-Job läuft
        return jsonify({"scan": _scan_dict(s), "enqueue_error": str(e)}), 202

@bp.get("/<int:scan_id>")
def get_scan(scan_id: int):
    db = _db.session
    s = db.get(Scan, scan_id)
    if not s: return jsonify({"error":"not_found"}), 404
    return jsonify(_scan_dict(s))

@bp.get("/<int:scan_id>/findings")
def get_findings(scan_id: int):
    db = _db.session
    sev = (request.args.get("severity") or "").strip().lower()
    q = db.query(Finding).filter(Finding.scan_id==scan_id)
    if sev: q = q.filter(Finding.severity==sev)
    rows = q.order_by(Finding.id.desc()).all()
    out = [{
        "id": f.id, "scan_id": f.scan_id, "severity": f.severity,
        "path": f.path, "rule": f.rule,
        "message": getattr(f,"message",None),
        "bytes": getattr(f,"bytes",None),
        "line": getattr(f,"line",None),
        "col": getattr(f,"col",None),
        "snippet": getattr(f,"snippet",None),
        "created_at": f.created_at.isoformat(timespec="seconds") if getattr(f,"created_at",None) else None,
    } for f in rows]
    return jsonify({"items": out, "count": len(out)})

@bp.get("/<int:scan_id>/logs")
def get_logs(scan_id: int):
    db = _db.session
    cursor = int(request.args.get("cursor") or 0)
    limit = max(10, min(int(request.args.get("limit", 200)), 1000))
    rows = (
        db.query(ScanLog)
          .filter(ScanLog.scan_id==scan_id, ScanLog.id > cursor)
          .order_by(ScanLog.id.asc())
          .limit(limit).all()
    )
    new_cursor = rows[-1].id if rows else cursor
    items = [{
        "id": r.id,
        "scan_id": r.scan_id,
        "ts": r.created_at.isoformat(timespec="seconds") if getattr(r,"created_at",None) else None,
        "level": getattr(r,"level",None),
        "message": getattr(r,"message",None) or getattr(r,"text",None),
        "line": getattr(r,"line",None),
    } for r in rows]
    return jsonify({"items": items, "cursor": new_cursor})

@bp.post("/<int:scan_id>/config")
def update_config(scan_id: int):
    db = _db.session
    s = db.get(Scan, scan_id)
    if not s: return jsonify({"error":"not_found"}), 404
    body = request.get_json(force=True) or {}
    cfg = dict(s.config or {})
    if "root_path" in body: cfg["root_path"] = body["root_path"]
    if "target_url" in body: cfg["target_url"] = body["target_url"]
    if isinstance(body.get("sftp"), dict):
        sf = body["sftp"]
        cfg["sftp"] = {
            "host": sf.get("host"),
            "user": sf.get("user"),
            "port": sf.get("port") or 22,
            "password": sf.get("password"),
            "key": sf.get("key"),
            "auth": sf.get("auth") or ("key" if sf.get("key") else "password"),
        }
    s.config = cfg
    db.commit()
    return jsonify({"config": s.config})

@bp.post("/<int:scan_id>/action/<string:action>")
def post_action(scan_id: int, action: str):
    db = _db.session
    s = db.get(Scan, scan_id)
    if not s: return jsonify({"error":"not_found"}), 404
    body = request.get_json(silent=True) or {}
    dry = bool(body.get("dry_run", True))
    try:
        from .tasks_scan import quarantine, core_restore_wp
        if action == "quarantine":
            paths = [f.path for f in db.query(Finding).filter(Finding.scan_id==scan_id, Finding.severity=="malicious")]
            n = quarantine(s, paths, dry_run=dry)
            return jsonify({"queued": False, "processed": n, "action": action, "dry_run": dry})
        if action == "core_restore":
            n = core_restore_wp(s, dry_run=dry)
            return jsonify({"queued": False, "processed": n, "action": action, "dry_run": dry})
        return jsonify({"error":"unsupported_action"}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@bp.get("/<int:scan_id>/reports")
def list_reports(scan_id: int):
    db = _db.session
    rows = db.query(Report).filter(Report.scan_id==scan_id).order_by(Report.id.desc()).all()
    out = [{
        "id": r.id,
        "scan_id": r.scan_id,
        "filename": getattr(r,"filename", None) or getattr(r,"type","Report"),
        "content_type": getattr(r,"content_type", None),
        "size": getattr(r,"size", None),
        "url": getattr(r,"url", None),
        "created_at": r.created_at.isoformat(timespec="seconds") if getattr(r,"created_at",None) else None,
    } for r in rows]
    return jsonify({"items": out, "count": len(out)})

@bp.delete("/<int:scan_id>/reports/<rep_id>")
def delete_report(scan_id: int, rep_id: str):
    db = _db.session
    r = db.get(Report, int(rep_id)) if rep_id.isdigit() else None
    if not r or r.scan_id != scan_id: return jsonify({"error":"not_found"}), 404
    db.delete(r); db.commit()
    return jsonify({"deleted": True})

@bp.get("/by-ticket/<int:ticket_id>")
def list_by_ticket(ticket_id: int):
    db = _db.session
    rows = db.query(Scan).filter(Scan.ticket_id==ticket_id).order_by(Scan.id.desc()).limit(50).all()
    return jsonify({"items": [_short_scan(r) for r in rows]})

@bp.get("/by-ticket/<int:ticket_id>/latest")
def latest_by_ticket(ticket_id: int):
    db = _db.session
    running = _guard_running(db, ticket_id)
    if running:
        return jsonify({"scan": _scan_dict(running), "running": True})
    s = db.query(Scan).filter(Scan.ticket_id==ticket_id).order_by(Scan.id.desc()).first()
    return jsonify({"scan": _scan_dict(s) if s else None, "running": False})
# app/scan_bp.py  (am Ende hinzufügen)
# --- SFTP-Browsing: simple dir listing & optional cwd change ---
# --- SFTP Browse (read-only) ---
# app/scan_bp.py
@bp.post("/sftp/list")
def sftp_list():
    """Listet Inhalte eines Verzeichnisses per SFTP (read-only)."""
    payload = request.get_json(force=True) or {}
    cfg = {"sftp": payload.get("sftp") or {}}
    cwd = payload.get("cwd") or "/"
    sftp = None
    try:
        sftp = _open_sftp_from_config(cfg)  # öffnet SFTP aus config  :contentReference[oaicite:0]{index=0}
        if not sftp:
            return jsonify({"error": "sftp auth failed"}), 400
        out = []
        for it in sftp.listdir_attr(cwd):
            name = it.filename
            path = _safe_join(cwd, name)     # sicheres Join   :contentReference[oaicite:1]{index=1}
            is_dir = (str(it.longname or "").startswith("d")) or (it.st_mode and (it.st_mode & 0o40000))
            out.append({"name": name, "path": path, "is_dir": bool(is_dir), "size": int(it.st_size or 0)})
        return jsonify({"cwd": cwd, "items": sorted(out, key=lambda x: (not x["is_dir"], x["name"].lower()))})
    except Exception as e:
        return jsonify({"error": str(e)}), 400
    finally:
        try: sftp and sftp.close()
        except Exception: pass
@bp.post("/<int:scan_id>/browse")
def browse(scan_id: int):
    """SFTP-Browsing: Verzeichnisse + Dateien unterhalb eines Pfades listen"""
    data = request.get_json(force=True) or {}
    path = data.get("path") or "/"

    db = _db.session
    s = db.get(Scan, scan_id)
    if not s:
        return jsonify({"error": "scan not found"}), 404

    cfg = s.config or {}
    try:
        sftp = _open_sftp_from_config(cfg)
        items = []
        for it in sftp.listdir_attr(path):
            items.append({
                "name": it.filename,
                "path": _safe_join(path, it.filename),
                "is_dir": str(it.longname or "").startswith("d") or (it.st_mode & 0o40000 != 0),
                "size": it.st_size,
            })
        sftp.close()
        return jsonify({"cwd": path, "items": items})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

