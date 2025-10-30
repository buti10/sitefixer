# ersetzt core_tree() – liefert stabile relative Pfade
from flask import Blueprint, request, jsonify
import os

bp_cmscore = Blueprint("cmscore_tree", __name__, url_prefix="/api/cms-core")

CORE_DIR = os.environ.get("SITEFIXER_CORE_DIR", "/var/www/sitefixer/cms-core")

def _safe_join(rel):
    rel = (rel or "").lstrip("/")
    base = os.path.normpath(CORE_DIR)
    abspath = os.path.normpath(os.path.join(base, rel))
    if not abspath.startswith(base):
        raise ValueError("bad path")
    return base, rel, abspath

@bp_cmscore.get("/tree")
def core_tree():
    try:
        base, rel, root = _safe_join(request.args.get("path",""))
    except ValueError:
        return jsonify({"error":"bad path"}), 400

    try:
        items = []
        with os.scandir(root) as it:
            for e in it:
                n = e.name
                if n in (".", ".."): 
                    continue
                if e.is_symlink():         # Schleifen vermeiden
                    continue
                items.append({
                    "name": n,
                    "path": (f"{rel}/{n}").lstrip("/"),   # stabiler relativer Pfad
                    "type": "dir" if e.is_dir(follow_symlinks=False) else "file"
                })
        items.sort(key=lambda x: (x["type"]!="dir", x["name"].lower()))
        return jsonify({"items": items, "root": base})
    except FileNotFoundError:
        return jsonify({"error":"not found"}), 404
    except PermissionError:
        return jsonify({"error":"permission denied"}), 403
