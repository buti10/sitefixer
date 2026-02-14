# app/corecache_versions.py
from __future__ import annotations
import hashlib, json, os, time
from pathlib import Path
from typing import Dict, List, Tuple
from flask import Blueprint, request, jsonify, current_app, abort

bp_corecache_versions = Blueprint("corecache_versions", __name__)

CORE_CACHE_ROOT = Path(os.getenv("CORE_CACHE_ROOT", "/var/www/sitefixer/cms-cache")).resolve()

def _ensure_root():
    CORE_CACHE_ROOT.mkdir(parents=True, exist_ok=True)

def _clean_rel(p: str) -> str:
    p = (p or "/").strip()
    if not p.startswith("/"):
        p = "/" + p
    return p

def _fs_path(rel: str) -> Path:
    rel = _clean_rel(rel)
    p = (CORE_CACHE_ROOT / rel.lstrip("/")).resolve()
    if CORE_CACHE_ROOT not in p.parents and p != CORE_CACHE_ROOT:
        abort(400, "invalid path")
    return p

def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def _build_manifest(root: Path, cms: str|None, version: str|None) -> Dict:
    files, total = [], 0
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        rel = p.relative_to(root).as_posix()
        if rel in (".manifest.json", ".meta.json"):
            continue
        size = p.stat().st_size
        total += size
        files.append({
            "path": rel,
            "size": size,
            "sha256": _sha256_file(p),
        })
    manifest = {
        "schema": 1,
        "cms": cms,
        "version": version,
        "root_rel": "/" + root.relative_to(CORE_CACHE_ROOT).as_posix(),
        "file_count": len(files),
        "total_bytes": total,
        "created_at": int(time.time()),
        "files": files,
    }
    (root / ".manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2))
    return manifest

def _read_json_if(path: Path) -> Dict|None:
    try:
        if path.exists():
            return json.loads(path.read_text() or "{}")
    except Exception:
        pass
    return None

def _discover_versions() -> List[Dict]:
    _ensure_root()
    items: List[Dict] = []
    for manifest in CORE_CACHE_ROOT.rglob(".manifest.json"):
        meta = _read_json_if(manifest.parent / ".meta.json") or {}
        man  = _read_json_if(manifest) or {}
        cms = meta.get("cms") or man.get("cms")
        ver = meta.get("version") or man.get("version")
        rel = "/" + manifest.parent.relative_to(CORE_CACHE_ROOT).as_posix()
        items.append({
            "cms": cms or None,
            "version": ver or None,
            "path": rel,
            "file_count": man.get("file_count"),
            "total_bytes": man.get("total_bytes"),
            "created_at": man.get("created_at"),
            "has_manifest": True,
        })
    return sorted(items, key=lambda x: (x.get("cms") or "", x.get("version") or "", x["path"]))

@bp_corecache_versions.get("/core-cache/versions")
def list_versions():
    """Liste aller Versionen (erkannt anhand .manifest.json)."""
    return jsonify({"items": _discover_versions(), "root": "/"})

@bp_corecache_versions.get("/core-cache/manifest")
def get_manifest():
    """Manifest für Pfad ODER (cms, version) holen."""
    path = request.args.get("path")
    cms = request.args.get("cms")
    version = request.args.get("version")
    if path:
        root = _fs_path(path)
    elif cms and version:
        root = CORE_CACHE_ROOT / cms / version
    else:
        abort(400, "either path or (cms & version) required")
    man = _read_json_if(root / ".manifest.json")
    if not man:
        abort(404, "manifest not found")
    return jsonify(man)

@bp_corecache_versions.post("/core-cache/mark-version")
def mark_version():
    """
    Markiert einen bestehenden Ordner als CMS-Version und baut Manifest.
    Body JSON: { "path": "/wordpress/6.5.4", "cms": "wordpress", "version": "6.5.4" }
    """
    data = request.get_json(silent=True) or {}
    path = data.get("path")
    cms = (data.get("cms") or "").strip() or None
    version = (data.get("version") or "").strip() or None
    if not path:
        abort(400, "path required")
    root = _fs_path(path)
    if not root.exists() or not root.is_dir():
        abort(400, "path must be an existing directory")
    # Default: aus Pfad ableiten, wenn nicht angegeben: /<cms>/<version>
    if not cms or not version:
        parts = Path(path.strip("/")).parts
        if len(parts) >= 2:
            cms = cms or parts[-2]
            version = version or parts[-1]
    (root / ".meta.json").write_text(json.dumps({"cms": cms, "version": version}, ensure_ascii=False, indent=2))
    manifest = _build_manifest(root, cms, version)
    return jsonify({"ok": True, "manifest": manifest})

@bp_corecache_versions.post("/core-cache/reindex")
def reindex():
    """
    Rebuild Manifest(e).
    Body JSON:
      - { "path": "/wordpress/6.5.4" }  -> nur diesen Pfad
      - {}                              -> alle Ordner mit .meta.json ODER .manifest.json
    """
    data = request.get_json(silent=True) or {}
    path = data.get("path")
    rebuilt = []
    if path:
        root = _fs_path(path)
        meta = _read_json_if(root / ".meta.json") or {}
        cms, version = meta.get("cms"), meta.get("version")
        rebuilt.append(_build_manifest(root, cms, version))
    else:
        # alle vorhandenen „Versionen“ neu bauen
        _ensure_root()
        for candidate in CORE_CACHE_ROOT.rglob(".meta.json"):
            root = candidate.parent
            meta = _read_json_if(candidate) or {}
            cms, version = meta.get("cms"), meta.get("version")
            rebuilt.append(_build_manifest(root, cms, version))
    return jsonify({"ok": True, "rebuilt": rebuilt})
