# app/modules/cms_core/tree_bp.py
from flask import Blueprint, request, jsonify, abort
from pathlib import Path
import os, shutil, tarfile, zipfile

# Wird unter /api/cms-core registriert
bp_cmscore = Blueprint("cmscore_tree", __name__, url_prefix="/api/cms-core")

# Physischer Core-Ordner
CORE_DIR = Path(os.environ.get("SITEFIXER_CORE_DIR", "/var/www/sitefixer/cms-core")).resolve()


def safe_fs_path(rel: str) -> Path:
    """
    rel = "", "Hallo", "wordpress/6.6"
    -> echter Pfad unter CORE_DIR, niemals außerhalb.
    """
    rel = (rel or "").strip("/")           # "" oder "Hallo" oder "wordpress/6.6"
    p = CORE_DIR if rel == "" else (CORE_DIR / rel)

    try:
        p = p.resolve()
    except FileNotFoundError:
        abort(404, "path not found")

    if CORE_DIR not in p.parents and p != CORE_DIR:
        abort(400, "invalid path")

    return p


@bp_cmscore.get("/tree")
def tree():
    # relativer Pfad aus Query
    rel = (request.args.get("path") or "").strip("/")
    p = safe_fs_path(rel)

    items = []
    if p.exists():
        for e in sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name.lower())):
            item_rel = e.relative_to(CORE_DIR).as_posix()  # z.B. "Hallo" oder "wordpress/6.6"
            items.append({
                "name": e.name,
                "path": item_rel,                           # relativer Pfad fürs Frontend
                "type": "dir" if e.is_dir() else "file",
            })

    root_rel = "" if p == CORE_DIR else p.relative_to(CORE_DIR).as_posix()
    return jsonify({
        "root": "/" + root_rel if root_rel else "/",       # Label im Explorer
        "items": items,
    })


@bp_cmscore.post("/mkdir")
def mkdir():
    data = request.get_json(force=True) or {}
    parent_rel = (data.get("path") or "").strip("/")
    name = (data.get("name") or "").strip()
    if not name:
        abort(400, "name required")

    base = safe_fs_path(parent_rel)
    (base / name).mkdir(parents=True, exist_ok=True)
    return jsonify(ok=True)


@bp_cmscore.post("/rename")
def rename():
    data = request.get_json(force=True) or {}
    src_rel = (data.get("src") or "").strip("/")
    dst_rel = (data.get("dst") or "").strip("/")

    src = safe_fs_path(src_rel)
    dst = safe_fs_path(dst_rel)

    shutil.move(str(src), str(dst))
    return jsonify(ok=True)


@bp_cmscore.delete("/rm")
def rm():
    rel = (request.args.get("path") or "").strip("/")
    p = safe_fs_path(rel)
    if p.is_dir():
        shutil.rmtree(p)
    else:
        p.unlink(missing_ok=True)
    return jsonify(ok=True)


@bp_cmscore.post("/upload")
def upload():
    rel = (request.form.get("path") or "").strip("/")
    target = safe_fs_path(rel)
    extract = request.form.get("extract", "0") == "1"
    files = request.files.getlist("files") or request.files.getlist("file")

    target.mkdir(parents=True, exist_ok=True)

    for f in files:
        dst = target / f.filename
        f.save(dst)

        if extract:
            extracted = False
            try:
                if dst.suffix.lower() == ".zip":
                    with zipfile.ZipFile(dst) as zf:
                        zf.extractall(target)
                    extracted = True
                elif dst.suffixes[-2:] == [".tar", ".gz"] or dst.suffix.lower() == ".tgz":
                    with tarfile.open(dst) as tf:
                        tf.extractall(target)
                    extracted = True
            except Exception:
                extracted = False

            if extracted:
                dst.unlink(missing_ok=True)

    return jsonify(ok=True)
