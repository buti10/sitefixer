
# app/core_cache_routes.py
from flask import Blueprint, request, jsonify
from pathlib import Path
import shutil, os, tarfile, zipfile

bp = Blueprint("core_cache", __name__, url_prefix="/core-cache")
ROOT = Path("/var/www/sitefixer/core-cache").resolve()

def safe(p: str) -> Path:
    q = (ROOT / p.lstrip("/")).resolve()
    if ROOT not in q.parents and q != ROOT: raise ValueError("bad path")
    return q

@bp.get("/tree")
def tree():
    p = safe(request.args.get("path","/"))
    items=[]
    if p.exists():
        for e in sorted(p.iterdir(), key=lambda x:(x.is_file(), x.name.lower())):
            items.append({"name":e.name,"path":"/"+e.relative_to(ROOT).as_posix(),"type":"dir" if e.is_dir() else "file"})
    return jsonify({"root": "/"+p.relative_to(ROOT).as_posix() if p!=ROOT else "/", "items": items})

@bp.post("/mkdir")
def mkdir():
    data = request.get_json(force=True)
    (safe(data["path"]) / data["name"]).mkdir(parents=True, exist_ok=True)
    return jsonify(ok=True)

@bp.post("/rename")
def rename():
    data = request.get_json(force=True)
    shutil.move(str(safe(data["src"])), str(safe(data["dst"])))
    return jsonify(ok=True)

@bp.delete("/rm")
def rm():
    p = safe(request.args["path"])
    shutil.rmtree(p) if p.is_dir() else p.unlink(missing_ok=True)
    return jsonify(ok=True)

@bp.post("/upload")
def upload():
    path = safe(request.form.get("path","/"))
    extract = request.form.get("extract","0") == "1"
    files = request.files.getlist("files") or request.files.getlist("file")
    path.mkdir(parents=True, exist_ok=True)

    for f in files:
        dst = path / f.filename
        f.save(dst)

        if extract:
            extracted = False
            try:
                if dst.suffix.lower() == ".zip":
                    with zipfile.ZipFile(dst) as z:
                        z.extractall(path)
                    extracted = True
                elif dst.suffixes[-2:] == [".tar", ".gz"] or dst.suffix.lower() == ".tgz":
                    with tarfile.open(dst) as t:
                        t.extractall(path)
                    extracted = True
            except Exception:
                extracted = False
            if extracted:
                dst.unlink(missing_ok=True)

    return jsonify(ok=True)

