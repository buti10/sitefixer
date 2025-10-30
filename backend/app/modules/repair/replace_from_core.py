# app/modules/repair/replace_from_core.py
from __future__ import annotations

import os, shutil, time, stat, re, json, socket, http.client, urllib.parse
from typing import Any, Set
from pathlib import Path
from contextlib import contextmanager

from flask import Blueprint, request, jsonify, current_app
from app.extensions import db
from app.models_repair import RepairSession

bp_replace = Blueprint("repair_replace", __name__, url_prefix="/api/repair")
CORE_DIR = os.environ.get("SITEFIXER_CORE_DIR", "/var/www/sitefixer/cms-core")

# --- SFTP adapter discovery ---------------------------------------------------
ADAPTER = ""
IMPORT_ERR = ""
get_client_by_sid = None
try:
    from app.modules.repair.sftp_adapter import get_client_by_sid as _gcbs
    get_client_by_sid = _gcbs
    ADAPTER = "app.modules.repair.sftp_adapter"
except Exception as e1:
    try:
        from app.scanner.sftp_adapter import get_client_by_sid as _gcbs2
        get_client_by_sid = _gcbs2
        ADAPTER = "app.scanner.sftp_adapter"
    except Exception as e2:
        IMPORT_ERR = f"{e1!r}; {e2!r}"

# --- Utils --------------------------------------------------------------------
def _sid_from_request():
    sid = request.args.get("sftp_sid") or request.args.get("sid")
    if not sid:
        sid = (request.json or {}).get("sftp_sid") if request.is_json else None
    sess_id = request.args.get("session_id") or ((request.json or {}).get("session_id") if request.is_json else None)
    if not sid and sess_id:
        rs = db.session.get(RepairSession, int(sess_id))
        sid = rs.sid if rs else None
    return sid

def _under_core(p: str) -> str:
    base = os.path.normpath(CORE_DIR)
    if not p:
        return base
    p = os.path.normpath(str(p))
    src = p if p.startswith(base) else os.path.normpath(os.path.join(base, p.lstrip("/")))
    if not src.startswith(base):
        raise ValueError("bad source")
    return src

def _has_sftp_api(x: Any) -> bool:
    return hasattr(x, "stat") and (hasattr(x, "put") or hasattr(x, "open"))

def _unwrap_sftp(obj: Any, max_depth: int = 3):
    visited: Set[int] = set()
    def walk(o: Any, depth: int, path: str):
        oid = id(o)
        if oid in visited or depth > max_depth:
            return None, path
        visited.add(oid)
        if _has_sftp_api(o): return o, path
        if isinstance(o, dict):
            for k in ("sftp","client","sftp_client","handle"):
                if k in o and _has_sftp_api(o[k]): return o[k], f"{path}.{k}" if path else k
            t = o.get("transport") or o.get("t")
            if t is not None:
                try:
                    from paramiko import SFTPClient
                    s = SFTPClient.from_transport(t)
                    if _has_sftp_api(s): return s, (path + ".transport" if path else "transport")
                except Exception: pass
            for k,v in o.items():
                h,p2 = walk(v, depth+1, f"{path}.{k}" if path else k)
                if h is not None: return h,p2
            return None, path
        if isinstance(o, (list, tuple)):
            for i,v in enumerate(o):
                h,p2 = walk(v, depth+1, f"{path}[{i}]")
                if h is not None: return h,p2
            return None, path
        for k in ("sftp","client","sftp_client","handle"):
            if hasattr(o,k):
                v = getattr(o,k)
                if _has_sftp_api(v): return v, f"{path}.{k}" if path else k
        if hasattr(o,"__dict__"):
            try:
                for k,v in vars(o).items():
                    h,p2 = walk(v, depth+1, f"{path}.{k}" if path else k)
                    if h is not None: return h,p2
            except Exception: pass
        return None, path
    h,p = walk(obj, 0, "")
    meta = {"kind":"found" if h else "unsupported","path":p,"raw_type":str(type(obj))}
    if isinstance(obj, dict):
        try: meta["raw_keys"] = sorted(list(obj.keys()))
        except Exception: pass
    return h, meta

def _connect_from_creds(creds: dict):
    import paramiko
    host = creds.get("host") or creds.get("hostname")
    user = creds.get("username") or creds.get("user")
    pw   = creds.get("password") or creds.get("pass") or creds.get("pwd")
    port = int(creds.get("port") or 22)
    if not host or not user or pw is None:
        return None
    t = paramiko.Transport((host, port))
    t.banner_timeout = 10
    t.auth_timeout = 10
    t.set_keepalive(30)
    t.connect(username=user, password=pw)
    return paramiko.SFTPClient.from_transport(t)

def _sftp_exists(sftp, path: str) -> bool:
    try: sftp.stat(path); return True
    except Exception: return False

def _sftp_mkdirs(sftp, path: str) -> None:
    path = (path or "").replace("\\","/")
    if not path: return
    parts, p = [], os.path.normpath(path)
    while p not in ("","/"):
        parts.append(p); p = os.path.dirname(p)
    for d in reversed(parts):
        try: sftp.mkdir(d)
        except Exception: pass

def _sftp_upload_file(sftp, src: str, dst: str) -> None:
    _sftp_mkdirs(sftp, os.path.dirname(dst))
    if hasattr(sftp, "put"):
        sftp.put(src, dst)
    else:
        with open(src, "rb") as fsrc, sftp.open(dst, "wb") as fdst:
            while True:
                chunk = fsrc.read(1024*1024)
                if not chunk: break
                fdst.write(chunk)

def _sftp_upload_tree(sftp, src_dir: str, dst_dir: str) -> None:
    dst_dir = dst_dir.rstrip("/")
    for root, _dirs, files in os.walk(src_dir):
        rel = os.path.relpath(root, src_dir)
        rel = "" if rel == "." else rel
        td = (dst_dir + ("/" + rel if rel else "")).replace("\\","/")
        _sftp_mkdirs(sftp, td)
        for f in files:
            _sftp_upload_file(sftp, os.path.join(root, f), td + "/" + f)

def _looks_binary(chunk: bytes) -> bool:
    if not chunk: return False
    if b"\x00" in chunk: return True
    nontext = sum(1 for b in chunk if b < 9 or (13 < b < 32))
    return nontext > max(32, len(chunk)//3)

def _sftp_from_sid_or_creds(sid: str):
    raw = get_client_by_sid(str(sid))
    sftp, meta = _unwrap_sftp(raw)
    if not sftp and isinstance(raw, dict) and {"host","username","password"}.issubset(raw.keys()):
        sftp = _connect_from_creds(raw)
        meta = {"kind":"built_from_creds","raw_type":"dict"}
    return sftp, meta

@contextmanager
def _open_sftp(sid: str):
    sftp, meta = _sftp_from_sid_or_creds(sid)
    if not sftp:
        raise RuntimeError(("sftp_session_not_usable", meta))
    try:
        yield sftp, meta
    finally:
        # sauber schließen, damit keine toten Kanäle hängen bleiben
        try:
            ch = getattr(sftp, "get_channel", lambda: None)()
            if ch: ch.close()
        except Exception: pass
        try: sftp.close()
        except Exception: pass

# --- Replace from core --------------------------------------------------------
@bp_replace.post("/replace-from-core")
def replace_from_core():
    data = request.get_json(silent=True) or {}

    sftp_sid    = data.get("sftp_sid") or data.get("session_id")
    target_path = str(data.get("target_path") or "").strip()
    core_abs    = data.get("core_abs_path")
    source_rel  = data.get("source_path")

    if not target_path:
        return jsonify({"error": "target_path required"}), 400
    if not sftp_sid:
        return jsonify({"error": "sftp_sid or session_id required"}), 400
    if not (core_abs or source_rel):
        return jsonify({"error": "source_path or core_abs_path required"}), 400
    if get_client_by_sid is None:
        return jsonify({"error": "sftp_not_configured", "adapter": ADAPTER, "detail": IMPORT_ERR}), 500

    try:
        src = _under_core(core_abs or source_rel)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    if not os.path.exists(src):
        return jsonify({"error": "source not found", "core_dir": CORE_DIR,
                        "source": (core_abs or source_rel), "resolved": src}), 404

    try:
        with _open_sftp(sftp_sid) as (sftp, meta):
            day   = time.strftime("%Y%m%d")
            secs  = time.strftime("%H%M%S")
            base  = os.path.dirname(target_path.rstrip("/")) or "/"
            qroot = base.rstrip("/") + f"/.quarantine_{day}"
            _sftp_mkdirs(sftp, qroot)

            moved_to = None
            if _sftp_exists(sftp, target_path):
                name = os.path.basename(target_path.rstrip("/"))
                moved_to = f"{qroot}/{name}_{secs}"
                sftp.rename(target_path, moved_to)

            if os.path.isdir(src):
                _sftp_mkdirs(sftp, target_path.rstrip("/"))
                _sftp_upload_tree(sftp, src, target_path.rstrip("/"))
            else:
                _sftp_upload_file(sftp, src, target_path)

            return jsonify({"ok": True, "mode": "sftp", "quarantine": moved_to,
                            "core_src": src, "adapter": ADAPTER, "unwrap": meta})
    except RuntimeError as e:
        return jsonify({"error": e.args[0][0], "unwrap": e.args[0][1]}), 410
    except Exception as e:
        current_app.logger.exception("replace_from_core failed")
        return jsonify({"error": f"sftp_copy_failed: {e}", "adapter": ADAPTER}), 500

@bp_replace.get("/replace-from-core/_debug-sftp")
def debug_sftp():
    sid = request.args.get("sftp_sid") or request.args.get("session_id", "")
    if not get_client_by_sid:
        return jsonify({"error": "sftp_not_configured", "adapter": ADAPTER, "detail": IMPORT_ERR}), 500
    try:
        raw = get_client_by_sid(str(sid))
        sftp, meta = _unwrap_sftp(raw)
        if not sftp and isinstance(raw, dict) and {"host","username","password"}.issubset(raw.keys()):
            s = _connect_from_creds(raw)
            if s:
                sftp = s
                meta = {"kind": "built_from_creds", "raw_type": "dict"}
        out = {
            "adapter": ADAPTER,
            "raw_type": str(type(raw)),
            "unwrap": meta,
            "usable": bool(sftp),
        }
        if isinstance(raw, dict):
            try: out["raw_keys"] = sorted(list(raw.keys()))
            except Exception: pass
        if sftp:
            out["caps"] = {k: hasattr(sftp, k) for k in ("put", "open", "stat", "mkdir", "rename")}
        try:
            if sftp: sftp.close()
        except Exception: pass
        return jsonify(out)
    except Exception as e:
        return jsonify({"error": repr(e), "adapter": ADAPTER}), 500

# --- File view/save -----------------------------------------------------------
@bp_replace.post("/file/save")
def file_save():
    data = request.get_json(silent=True) or {}
    sftp_sid = data.get("sftp_sid") or data.get("session_id")
    path     = str(data.get("path") or "").strip()
    text     = data.get("text", "")
    if not sftp_sid or not path:
        return jsonify({"error":"missing"}), 400
    try:
        with _open_sftp(sftp_sid) as (sftp, _meta):
            with sftp.open(path, "wb") as f:
                f.write(text.encode("utf-8"))
        return jsonify({"ok": True})
    except RuntimeError as e:
        return jsonify({"error": e.args[0][0], "unwrap": e.args[0][1]}), 410
    except Exception:
        return jsonify({"error":"write_failed"}), 500

@bp_replace.get("/file/view")
def file_view():
    sftp_sid = request.args.get("sftp_sid") or request.args.get("session_id")
    path     = request.args.get("path") or ""
    max_bytes= int(request.args.get("max_bytes") or 400000)
    if not sftp_sid or not path:
        return jsonify({"error":"missing"}), 400
    try:
        with _open_sftp(sftp_sid) as (sftp, _meta):
            try:
                st = sftp.stat(path)
            except Exception:
                return jsonify({"error":"file_not_found"}), 404
            size  = int(getattr(st, "st_size", 0) or 0)
            mtime = int(getattr(st, "st_mtime", 0) or 0)
            with sftp.open(path, "rb") as fh:
                data = fh.read(max_bytes + 1)
            truncated = len(data) > max_bytes
            if truncated: data = data[:max_bytes]
        is_bin = _looks_binary(data)
        out = {"binary": bool(is_bin), "truncated": truncated,
               "size_hint": size or len(data), "mtime": mtime}
        if not is_bin:
            try: out["text"] = data.decode("utf-8")
            except UnicodeDecodeError: out["text"] = data.decode("latin1", "replace")
        return jsonify(out)
    except RuntimeError as e:
        return jsonify({"error": e.args[0][0], "unwrap": e.args[0][1]}), 410
    except Exception:
        return jsonify({"error":"read_failed"}), 500

# --- CMS core index/tree ------------------------------------------------------
from flask import Blueprint as _BP
from pathlib import Path as _P

core_bp = _BP("cms_core", __name__, url_prefix="/api/cms-core")

@core_bp.get("/index")
def core_index():
    items = []
    base = _P(CORE_DIR)
    if base.exists():
        for cms_dir in sorted([p for p in base.iterdir() if p.is_dir()]):
            for ver_dir in sorted([p for p in cms_dir.iterdir() if p.is_dir()]):
                items.append({
                    "key": f"{cms_dir.name}/{ver_dir.name}",
                    "cms": cms_dir.name,
                    "version": ver_dir.name,
                    "path": str(ver_dir),
                })
    return jsonify({"items": items})

@core_bp.get("/tree")
def core_tree():
    rel = (request.args.get("path") or "").strip().strip("/")
    try:
        absdir = _under_core(rel)
    except ValueError:
        return jsonify({"error":"invalid_path"}), 400
    p = _P(absdir)
    if not p.exists():
        return jsonify({"items": []})
    out = []
    for child in sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
        out.append({"name": child.name, "type": "dir" if child.is_dir() else "file"})
    return jsonify({"items": out})

# --- Diagnose + HTTP check + Detect CMS --------------------------------------
@bp_replace.post("/diagnose")
def diagnose():
    data = request.get_json(silent=True) or {}
    sftp_sid = data.get("sftp_sid") or data.get("sid") or _sid_from_request()
    root     = (data.get("root") or "/").rstrip("/") or "/"
    cms_hint = (data.get("cms_hint") or "").lower().strip()
    if not sftp_sid: return jsonify({"error":"missing_session"}), 400
    try:
        with _open_sftp(sftp_sid) as (sftp, meta):
            def _exists(p):
                try: sftp.stat(p); return True
                except: return False

            cms = cms_hint or (
                "wordpress" if _exists(f"{root}/wp-config.php") else
                "joomla"    if _exists(f"{root}/configuration.php") else
                "drupal"    if _exists(f"{root}/core/lib/Drupal.php") or _exists(f"{root}/composer.json") else
                "typo3"     if _exists(f"{root}/typo3conf/LocalConfiguration.php") else
                "unknown"
            )

            findings = []
            def _mode(p):
                try: return stat.S_IMODE(sftp.stat(p).st_mode)
                except: return None

            def _add_perm_finding(p, mode, kind):
                if mode is None: return
                if kind == "dir":
                # erwartet: 0755
                    if mode & 0o002:
                        findings.append({"code":"DIR_WORLD_WRITABLE","title":f"Ordner weltweit beschreibbar","severity":"high","path":p,"mode":oct(mode)})
                    elif mode != 0o755:
                        findings.append({"code":"DIR_MODE_NONSTD","title":"Ordner-Modus abweichend","severity":"low","path":p,"mode":oct(mode),"expect":"0755"})
                else:
                    # erwartet: 0644, Konfigs strenger
                    expect = 0o644
                    if p.endswith(("wp-config.php","configuration.php","settings.php","LocalConfiguration.php")):
                        expect = 0o640
                    if mode & 0o002:
                        findings.append({"code":"FILE_WORLD_WRITABLE","title":"Datei weltweit beschreibbar","severity":"high","path":p,"mode":oct(mode)})
                    elif mode != expect:
                        findings.append({"code":"FILE_MODE_NONSTD","title":"Datei-Modus abweichend","severity":"low","path":p,"mode":oct(mode),"expect":oct(expect)})

            # Index vorhanden?
            try:
                if not ( _exists(f"{root}/index.php") or _exists(f"{root}/index.html") ):
                    findings.append({"code":"IDX_MISSING","title":"index.php/.html fehlt","severity":"med","path":root})
            except: pass

            # Konfigurationen: existieren + Rechte
            for conf in ("wp-config.php","configuration.php","sites/default/settings.php","typo3conf/LocalConfiguration.php"):
                p = f"{root}/{conf}"
                if _exists(p):
                    m = _mode(p)
                    _add_perm_finding(p, m, "file")
                    if m is not None and (m & 0o002):
                        findings.append({"code":"CONF_WORLD_WRITABLE","title":f"{conf} weltweit beschreibbar","severity":"high","path":p,"mode":oct(m)})

            # --- Rechte-Check ausgewählter Bäume ---
            check_dirs = [root, f"{root}/wp-content", f"{root}/wp-includes", f"{root}/wp-admin", f"{root}/administrator"]
            seen = set()
            for d in check_dirs:
                try:
                    for a in sftp.listdir_attr(d):
                        p = f"{d}/{a.filename}"
                        if p in seen: continue
                        seen.add(p)
                        if stat.S_ISDIR(a.st_mode):
                            _add_perm_finding(p, stat.S_IMODE(a.st_mode), "dir")
                        else:
                            _add_perm_finding(p, stat.S_IMODE(a.st_mode), "file")
                except: pass

        # --- Verdächtige Code-Pattern mit Zeilennummern ---
            suspect = re.compile(rb"(base64_decode|gzinflate|eval|assert|system|shell_exec|passthru|exec|popen|proc_open)\s*\(")
            sample_hits = []
            total_hits = 0

            def scan_file_for_suspects(pth: str):
                nonlocal total_hits, sample_hits
                try:
                    # bis 256 KiB lesen, dann in Zeilen splitten
                    with sftp.open(pth, "rb") as fh:
                        data = fh.read(262144)
                        lines = data.splitlines(keepends=True)
                        # Cursor über Zeilen für Offsets
                        off = 0
                        for idx, ln in enumerate(lines, start=1):
                            if suspect.search(ln):
                                total_hits += 1
                                if len(sample_hits) < 20:
                                    snippet = ln[:140].decode("utf-8","replace")
                                    sample_hits.append({"path": pth, "line": idx, "snippet": snippet})
                            off += len(ln)
                            if total_hits >= 400: break
                except: pass

            # nur relevante Bäume oberste Ebene + Unterordner
            for base in (root, f"{root}/wp-admin", f"{root}/wp-includes", f"{root}/administrator"):
                try:
                   for a in sftp.listdir_attr(base):
                       if stat.S_ISREG(a.st_mode) and a.filename.endswith((".php",".phtml",".ico")):
                           scan_file_for_suspects(f"{base}/{a.filename}")
                except: pass

            # --- Zusammenfassung ---
            if total_hits:
                findings.append({
                    "code":"SUSPECT_SNIPPETS",
                    "title":"Auffällige Code-Pattern",
                    "severity":"high",
                    "detail": f"{total_hits} Treffer",
                    "items": sample_hits,   # Liste mit {path,line,snippet}
                })

            return jsonify({"cms": cms, "root": root or "/", "findings": findings})
    except RuntimeError as e:
        return jsonify({"error":"sftp_session_expired","unwrap": e.args[0][1]}), 410

@bp_replace.get("/http_check")
def http_check():
    import ssl, time, datetime
    raw = (request.args.get("domain") or "").strip()
    if not raw: return jsonify({"error":"domain_required"}), 400
    dom = urllib.parse.urlparse(raw).netloc or raw

    results = []
    for scheme, port in (("http",80),("https",443)):
      info = {"scheme":scheme}
      t0 = time.time()
      try:
        if scheme=="https":
          ctx = ssl.create_default_context()
          conn = http.client.HTTPSConnection(dom, port, timeout=8, context=ctx)
        else:
          conn = http.client.HTTPConnection(dom, port, timeout=8)
        path = "/"
        hops = 0
        while hops < 5:
          conn.request("GET", path, headers={"User-Agent":"Sitefixer/repair"})
          resp = conn.getresponse()
          headers = dict(resp.getheaders())
          info.update({"status":resp.status, "reason":resp.reason,
                       "server": headers.get("Server",""),
                       "content_type": headers.get("Content-Type",""),
                       "content_len": int(headers.get("Content-Length","0") or 0)})
          if 300 <= resp.status < 400 and resp.getheader("Location"):
            loc = resp.getheader("Location")
            path = urllib.parse.urlparse(loc).path or "/"
            hops += 1
            continue
          break
        info["redirects"] = hops
        conn.close()
      except Exception as e:
        info["error"] = str(e)
      info["rt_ms"] = int((time.time()-t0)*1000)
      if scheme=="https":
        try:
          s = socket.create_connection((dom, 443), timeout=5)
          ctx = ssl.create_default_context()
          with ctx.wrap_socket(s, server_hostname=dom) as ss:
            cert = ss.getpeercert()
            info["tls"] = {
              "subject": dict(x for ((x,_),) in cert.get("subject", [])[0:1]).get("commonName",""),
              "issuer": dict(x for ((x,_),) in cert.get("issuer", [])[0:1]).get("commonName",""),
              "notAfter": cert.get("notAfter","")
            }
        except Exception: pass
      results.append(info)
    try: ip = socket.gethostbyname(dom)
    except Exception: ip = None
    return jsonify({"domain": dom, "ip": ip, "results": results})

@bp_replace.get("/detect_cms")
def detect_cms():
    sftp_sid = _sid_from_request()
    root     = (request.args.get("root") or "/").rstrip("/") or "/"
    if not sftp_sid: return jsonify({"error":"missing_session"}), 400
    try:
        with _open_sftp(sftp_sid) as (sftp, meta):
            def _exists(p):
                try: sftp.stat(p); return True
                except: return False
            cms = (
                "wordpress" if _exists(f"{root}/wp-config.php") else
                "joomla"    if _exists(f"{root}/configuration.php") else
                "drupal"    if _exists(f"{root}/core/lib/Drupal.php") or _exists(f"{root}/composer.json") else
                "typo3"     if _exists(f"{root}/typo3conf/LocalConfiguration.php") else
                "unknown"
            )
            return jsonify({"cms": cms})
    except RuntimeError as e:
        return jsonify({"error":"sftp_session_expired","unwrap": e.args[0][1]}), 410
    
# ===== FS: chmod einzelner Pfad =====
@bp_replace.post("/fs/chmod")
def fs_chmod():
    data = request.get_json(silent=True) or {}
    sftp_sid = data.get("sftp_sid") or data.get("session_id")
    path = (data.get("path") or "").strip()
    mode_raw = str(data.get("mode") or "").strip()
    if not sftp_sid or not path or not mode_raw:
        return jsonify({"error": "missing"}), 400

    raw = get_client_by_sid(str(sftp_sid))
    sftp, meta = _unwrap_sftp(raw)
    if not sftp and isinstance(raw, dict) and {"host","username","password"}.issubset(raw.keys()):
        sftp = _connect_from_creds(raw)
    if not sftp:
        return jsonify({"error":"sftp_session_not_usable","unwrap":meta}), 410

    # "755", "0755", "0o755" -> int
    mode_raw = mode_raw.lower().lstrip()
    if mode_raw.startswith("0o"): mode = int(mode_raw, 8)
    else:
        mode_raw = mode_raw.lstrip("0") or "0"
        mode = int(mode_raw, 8)
    try:
        sftp.chmod(path, mode)
        return jsonify({"ok": True, "path": path, "mode": oct(mode)})
    except Exception as e:
        return jsonify({"error":"chmod_failed", "detail": str(e)}), 500
# ===== FS: Rechte reparieren (rekursiv) =====
@bp_replace.post("/fs/fix-perms")
def fs_fix_perms():
    data = request.get_json(silent=True) or {}
    sftp_sid = data.get("sftp_sid") or data.get("session_id")
    root = (data.get("root") or "/").rstrip("/") or "/"
    dry = bool(data.get("dry_run", False))
    if not sftp_sid:
        return jsonify({"error":"missing"}), 400

    raw = get_client_by_sid(str(sftp_sid))
    sftp, meta = _unwrap_sftp(raw)
    if not sftp and isinstance(raw, dict) and {"host","username","password"}.issubset(raw.keys()):
        sftp = _connect_from_creds(raw)
    if not sftp:
        return jsonify({"error":"sftp_session_not_usable","unwrap":meta}), 410

    def _expect_mode(p:str, st_mode:int) -> int:
        # Ordner 0755, Dateien 0644, zentrale Konfigs 0640
        import posixpath, stat as _st
        if _st.S_ISDIR(st_mode):
            return 0o755
        fname = posixpath.basename(p)
        if fname in ("wp-config.php","configuration.php","settings.php","LocalConfiguration.php"):
            return 0o640
        return 0o644

    # Iterativ laufen, damit kein Stack-Overflow
    from collections import deque
    q = deque([root])
    changed = 0
    checked = 0
    errors = []

    while q:
        d = q.popleft()
        try:
            for a in sftp.listdir_attr(d):
                checked += 1
                p = f"{d}/{a.filename}"
                mode_now = stat.S_IMODE(a.st_mode)
                exp = _expect_mode(p, a.st_mode)
                if stat.S_ISDIR(a.st_mode):
                    q.append(p)
                    if mode_now != 0o755:
                        try:
                            if not dry: sftp.chmod(p, 0o755)
                            changed += 1
                        except Exception as e:
                            errors.append({"path": p, "error": str(e)})
                else:
                    if mode_now != exp:
                        try:
                            if not dry: sftp.chmod(p, exp)
                            changed += 1
                        except Exception as e:
                            errors.append({"path": p, "error": str(e)})
        except Exception as e:
            errors.append({"path": d, "error": str(e)})

    return jsonify({"ok": True, "root": root, "checked": checked, "changed": changed, "errors": errors, "dry_run": dry})
