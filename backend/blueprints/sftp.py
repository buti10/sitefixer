# blueprints/sftp.py -> list_dir
import stat, pwd, grp, time

def _mode_to_rwx(mode:int)->str:
    bits = [
        (stat.S_IRUSR,'r'),(stat.S_IWUSR,'w'),(stat.S_IXUSR,'x'),
        (stat.S_IRGRP,'r'),(stat.S_IWGRP,'w'),(stat.S_IXGRP,'x'),
        (stat.S_IROTH,'r'),(stat.S_IWOTH,'w'),(stat.S_IXOTH,'x'),
    ]
    t = 'd' if stat.S_ISDIR(mode) else 'l' if stat.S_ISLNK(mode) else '-'
    return t + ''.join(ch if mode & m else '-' for m,ch in bits)

@bp.get("/<sid>/list")
def list_dir(sid):
    sess = _SESS.get(sid)
    if not sess: abort(404, "session not found")
    path = request.args.get("path") or "/"
    sftp = sess["sftp"]
    out = []
    for a in sftp.listdir_attr(path):
        out.append({
            "name": a.filename,
            "path": (path.rstrip("/") + "/" + a.filename) if path != "/" else ("/" + a.filename),
            "type": "dir" if stat.S_ISDIR(a.st_mode) else "file",
            "size": getattr(a, "st_size", 0),
            "mtime": getattr(a, "st_mtime", 0),
            "uid": getattr(a, "st_uid", 0),
            "gid": getattr(a, "st_gid", 0),
            "perms": stat.filemode(a.st_mode),
        })
    sess["ts"] = time.time()
    return jsonify({"items": out})
