#app/modules/wp_repair/modules/audit/actions.py
from __future__ import annotations

import json
import posixpath
import secrets
import time
import os
import zipfile
import hashlib
from typing import Any, Dict, List, Optional, Tuple
from app.extensions import db
from app.models_wp_repair_audit import RepairAction, RepairActionFile
from app.modules.wp_repair.session_store import get_session



from flask import current_app

from app.modules.wp_repair.db_audit import (
    create_action_row,
    add_file_op,
    set_action_status,
    get_action_ctx,
)

from app.modules.wp_repair.modules.sftp.connect import sftp_connect

# ------------------------------------------------------------------
# Local artifact storage
# ------------------------------------------------------------------
# We keep ALL repair artifacts (backups, manifests) on the Sitefixer
# server, not on the customer's SFTP webspace.
#
# Layout:
#   <STORAGE_ROOT>/quarantine/<ticket_id>/<action_id>/
#       files/   (single file backups)
#       dirs/    (zipped directory backups)
#
# STORAGE_ROOT can be configured via Flask config:
#   WP_REPAIR_STORAGE_ROOT=/var/www/sitefixer/wp-repair-storage


def _storage_root() -> str:
    try:
        root = (current_app.config.get("WP_REPAIR_STORAGE_ROOT") or "").strip()
    except Exception:
        root = ""
    if not root:
        root = "/var/www/sitefixer/wp-repair-storage"
    return os.path.abspath(root)


def _ensure_local_dir(path: str) -> None:
    os.makedirs(path, exist_ok=True)


def _artifact_dir(ticket_id: int, action_id: str) -> str:
    return os.path.join(_storage_root(), "quarantine", str(int(ticket_id or 0)), str(action_id))

def append_log(*args, **kwargs) -> None:
    # kept for backward compatibility; no remote logs anymore
    return


def _relpath(src_path: str, wp_root: str) -> str:
    src = posixpath.normpath(src_path)
    root = posixpath.normpath(wp_root)
    if src.startswith(root + "/"):
        return src[len(root) + 1 :]
    if src == root:
        return "."
    return src.lstrip("/")


def _sha256_bytes(data: bytes) -> str:
    h = hashlib.sha256()
    h.update(data)
    return h.hexdigest()


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()

def _ts() -> int:
    return int(time.time())


def _action_id(fix_id: str) -> str:
    return f"{time.strftime('%Y%m%d_%H%M%S')}_{fix_id}_{secrets.token_urlsafe(6)}"


def _mkdir_p(sftp, path: str) -> None:
    path = posixpath.normpath(path)
    if path in ("", "/"):
        return
    cur = ""
    for part in path.split("/"):
        if not part:
            continue
        cur += "/" + part
        try:
            sftp.stat(cur)
        except Exception:
            try:
                sftp.mkdir(cur)
            except Exception:
                pass


def _write_text(sftp, path: str, text: str) -> None:
    f = sftp.open(path, "w")
    try:
        f.write(text)
    finally:
        f.close()


def _read_text(sftp, path: str, max_bytes: int = 2_000_000) -> str:
    f = sftp.open(path, "r")
    try:
        data = f.read(max_bytes)
        if isinstance(data, bytes):
            return data.decode("utf-8", errors="replace")
        return str(data)
    finally:
        f.close()


def sitefixer_base(wp_root: str) -> str:
    return posixpath.join(posixpath.normpath(wp_root), ".sitefixer")


def ensure_dirs(host, port, username, password, wp_root, *, ticket_id: int | None = None, action_id: str | None = None):
    """Best-effort preflight.

    We *don't* create any `.sitefixer/` folders on the customer host.
    We only verify the SFTP credentials and ensure local artifact dirs exist.
    """
    # verify SFTP works (fast fail)
    client = sftp_connect(host, port, username, password)
    try:
        sftp = client.open_sftp()
        try:
            # simple no-op
            sftp.listdir(".")
        finally:
            try:
                sftp.close()
            except Exception:
                pass
    finally:
        try:
            client.close()
        except Exception:
            pass

    # local dirs
    if ticket_id is not None and action_id is not None:
        adir = _artifact_dir(int(ticket_id or 0), str(action_id))
        _ensure_local_dir(os.path.join(adir, "files"))
        _ensure_local_dir(os.path.join(adir, "dirs"))
        return {"local_action_dir": adir}
    return {"ok": True}


def create_action(
    host: str,
    port: int,
    username: str,
    password: str,
    wp_root: str,
    fix_id: str,
    context: Dict[str, Any],
    *,
    ticket_id: int,
    actor_user_id: int,
    actor_name: Optional[str] = None,
    project_root: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a repair action.

    All artifacts (meta.json, backups, manifests) are stored locally on the
    Sitefixer server under WP_REPAIR_STORAGE_ROOT.
    """
    aid = _action_id(fix_id)

    # local action folder + meta.json
    action_dir = _artifact_dir(int(ticket_id or 0), aid)
    _ensure_local_dir(os.path.join(action_dir, "files"))
    _ensure_local_dir(os.path.join(action_dir, "dirs"))
    meta_path = os.path.join(action_dir, "meta.json")

    # optional: verify SFTP works
    try:
        ensure_dirs(host, port, username, password, wp_root, ticket_id=int(ticket_id or 0), action_id=aid)
    except Exception:
        # don't block action creation
        pass

    meta = {
        "action_id": aid,
        "fix_id": fix_id,
        "ticket_id": int(ticket_id or 0),
        "actor_user_id": int(actor_user_id or 0),
        "actor_name": actor_name,
        "created_ts": _ts(),
        "wp_root": posixpath.normpath(wp_root),
        "project_root": project_root,
        "status": "created",
        "context": context or {},
    }

    # write initial meta.json locally (best-effort)
    try:
        with open(meta_path, "w", encoding="utf-8") as f:
            f.write(json.dumps(meta, ensure_ascii=False, indent=2))
    except Exception:
        pass

    try:
        create_action_row(
            action_id=aid,
            ticket_id=int(ticket_id or 0),
            fix_id=str(fix_id),
            created_by_user_id=int(actor_user_id or 0),
            created_by_name=actor_name,
            wp_root=wp_root,
            project_root=project_root,
            # keep field names for backwards-compatibility; values are local paths now
            remote_action_dir=action_dir,
            remote_meta_path=meta_path,
            remote_moved_dir=action_dir,
            context_json=context or {},
            meta_json=meta,
            manifest_json=None,
        )
    except Exception:
        try:
            current_app.logger.exception("create_action_row failed (non-fatal)")
        except Exception:
            pass

    return {
        "action_id": aid,
        "wp_root": posixpath.normpath(wp_root),
        "action_dir": action_dir,
        "meta_path": meta_path,
        "moved_dir": action_dir,
    }





def _get_sftp_from_session(session_id: str):
    sess = get_session(session_id)
    if not isinstance(sess, dict):
        raise Exception("Invalid or expired session_id")

    client = sftp_connect(sess["host"], int(sess.get("port", 22)), sess["username"], sess["password"])
    return client, client.open_sftp()









def quarantine_move(
    host: str,
    port: int,
    username: str,
    password: str,
    *,
    wp_root: str,
    src_path: str,
    action_id: str,
    kind: str = "FILE",  # "FILE" oder "DIR"
) -> Dict[str, Any]:
    """Create a local backup of src_path (file or directory).

    IMPORTANT:
    - We do NOT create backup folders on the customer's host.
    - We do NOT rename/move the remote file here.
    - Callers may overwrite/delete/rename the remote path afterwards.

    Stored under:
      <WP_REPAIR_STORAGE_ROOT>/quarantine/<ticket_id>/<action_id>/

    Returns dst_path as *local* filesystem path.
    """
    src_path = posixpath.normpath(src_path)

    # best-effort action context (ticket_id + wp_root)
    try:
        ticket_id, wp_root_db = get_action_ctx(str(action_id))
    except Exception:
        ticket_id, wp_root_db = 0, None

    wp_root = posixpath.normpath(wp_root_db or wp_root)
    rel = _relpath(src_path, wp_root)
    key = hashlib.sha1(rel.encode("utf-8", errors="ignore")).hexdigest()[:10]
    base = posixpath.basename(src_path.rstrip("/")) or "item"

    action_dir = _artifact_dir(int(ticket_id or 0), str(action_id))
    files_dir = os.path.join(action_dir, "files")
    dirs_dir = os.path.join(action_dir, "dirs")
    _ensure_local_dir(files_dir)
    _ensure_local_dir(dirs_dir)

    payload: Dict[str, Any] = {
        "storage": "local",
        "ticket_id": int(ticket_id or 0),
        "action_id": str(action_id),
        "wp_root": wp_root,
        "relpath": rel,
        "key": key,
        "kind": str(kind),
        "basename": base,
    }

    client = sftp_connect(host, port, username, password)
    sftp = client.open_sftp()
    try:
        if str(kind).upper() == "DIR":
            # Zip directory recursively into a single local file
            zip_path = os.path.join(dirs_dir, f"{key}__{base}.zip")
            n_files = 0
            total = 0

            def walk_dir(rpath: str) -> List[Tuple[str, bool]]:
                out: List[Tuple[str, bool]] = []
                for a in sftp.listdir_attr(rpath):
                    name = getattr(a, "filename", None) or getattr(a, "longname", "")
                    name = str(name)
                    if not name or name in (".", ".."):
                        continue
                    full = posixpath.join(rpath, name)
                    mode = int(getattr(a, "st_mode", 0))
                    is_dir = (mode & 0o040000) == 0o040000
                    out.append((full, is_dir))
                return out

            with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                stack = [src_path]
                while stack:
                    cur = stack.pop()
                    for child, is_dir in walk_dir(cur):
                        arc = _relpath(child, src_path)
                        if is_dir:
                            stack.append(child)
                            # directory entries optional
                            continue
                        # stream file into zip
                        with sftp.open(child, "rb") as rf:
                            with zf.open(arc, "w") as wf:
                                while True:
                                    chunk = rf.read(1024 * 1024)
                                    if not chunk:
                                        break
                                    wf.write(chunk)
                                    total += len(chunk)
                        n_files += 1

            payload.update({"zip_files": n_files, "zip_bytes": int(total), "sha256": _sha256_file(zip_path)})

            # DB file-op (non-fatal)
            try:
                add_file_op(
                    action_id=str(action_id),
                    op="backup",
                    src_path=src_path,
                    dst_path=zip_path,
                    payload_json=payload,
                )
            except Exception:
                pass

            return {"ok": True, "src_path": src_path, "dst_path": zip_path, "payload": payload}

        # FILE backup
        dst_path = os.path.join(files_dir, f"{key}__{base}")
        sha = hashlib.sha256()
        size = 0
        with sftp.open(src_path, "rb") as rf:
            with open(dst_path, "wb") as wf:
                while True:
                    chunk = rf.read(1024 * 1024)
                    if not chunk:
                        break
                    if isinstance(chunk, str):
                        chunk = chunk.encode("utf-8", errors="replace")
                    wf.write(chunk)
                    sha.update(chunk)
                    size += len(chunk)

        payload.update({"bytes": int(size), "sha256": sha.hexdigest()})

        try:
            add_file_op(
                action_id=str(action_id),
                op="backup",
                src_path=src_path,
                dst_path=dst_path,
                payload_json=payload,
            )
        except Exception:
            pass

        return {"ok": True, "src_path": src_path, "dst_path": dst_path, "payload": payload}

    finally:
        try:
            sftp.close()
        except Exception:
            pass
        try:
            client.close()
        except Exception:
            pass


def rollback(
    session_id: str,
    action_id: str,
    wp_root: Optional[str] = None,
    dry_run: bool = False,
    *args,
    **kwargs,
) -> Dict[str, Any]:
    """
    DB-based rollback:
    - accepts action_id OR a local meta.json path (legacy route calls)
    - loads RepairAction + RepairActionFile ops
    - replays in reverse order
    - restores from local backups (dst_path points to local backup)
    """

    def _looks_like_path(v: str) -> bool:
        if not v:
            return False
        s = str(v)
        return ("/" in s or "\\" in s) and (s.endswith("meta.json") or "/quarantine/" in s or "\\quarantine\\" in s)

    def _extract_action_id_from_path(p: str) -> Optional[str]:
        try:
            s = str(p).replace("\\", "/")
            # .../quarantine/<ticket>/<action_id>/meta.json
            if s.endswith("/meta.json"):
                return s.split("/")[-2]
            # maybe .../<action_id>
            return s.split("/")[-1] or None
        except Exception:
            return None

    def _read_meta_action_id(meta_path: str) -> Optional[str]:
        try:
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)
            aid = meta.get("action_id")
            if aid:
                return str(aid)
        except Exception:
            pass
        return None

    # -------------------------------------------------
    # Normalize inputs from various legacy route calls
    # -------------------------------------------------
    # keyword action_id always wins
    if kwargs.get("action_id"):
        action_id = kwargs["action_id"]

    # If second arg is actually ticket_id (digits) and real action_id is in args[0]
    if action_id is not None and str(action_id).isdigit() and len(args) >= 1 and args[0]:
        action_id = args[0]
        if wp_root is None and len(args) >= 2 and args[1]:
            wp_root = args[1]
        if len(args) >= 3:
            try:
                dry_run = bool(args[2])
            except Exception:
                pass

    # If action_id is actually a meta.json path, extract real action_id from meta.json or folder name
    raw_action_id = str(action_id)
    if _looks_like_path(raw_action_id):
        meta_path = raw_action_id
        # try meta.json first
        aid = _read_meta_action_id(meta_path)
        if not aid:
            # fallback: parse folder name
            aid = _extract_action_id_from_path(meta_path)
        if not aid:
            return {"ok": False, "error": f"Could not extract action_id from meta_path: {meta_path}"}
        action_id = aid

    action_id = str(action_id)

    # 1) load action from DB
    action: RepairAction | None = (
        db.session.query(RepairAction)
        .filter(RepairAction.action_id == action_id)
        .first()
    )
    if not action:
        return {"ok": False, "error": f"Unknown action_id: {action_id}"}

    # determine wp_root boundary (prefer DB)
    boundary = getattr(action, "wp_root", None) or wp_root or ""
    if not boundary:
        ctx = getattr(action, "context_json", None) or {}
        boundary = ctx.get("wp_root") or ""
    if not boundary:
        return {"ok": False, "error": "Missing wp_root boundary for rollback."}

    # 2) connect sftp from session
    client, sftp = _get_sftp_from_session(session_id)

    try:
        # 3) load file ops DESC
        ops: List[RepairActionFile] = (
            db.session.query(RepairActionFile)
            .filter(RepairActionFile.action_id == action_id)
            .order_by(RepairActionFile.id.desc())
            .all()
        )

        if not ops:
            return {"ok": False, "error": "No file ops recorded for this action (nothing to rollback)."}

        executed: List[Dict[str, Any]] = []
        skipped: List[Dict[str, Any]] = []
        errors: List[Dict[str, Any]] = []

        def clamp(path: str) -> bool:
            return _is_within(boundary, path)

        for op in ops:
            op_name = getattr(op, "op", "") or ""
            src = getattr(op, "src_path", None)
            dst = getattr(op, "dst_path", None)
            payload = getattr(op, "payload_json", None) or {}

            try:
                # rename undo
                if op_name in ("renamed", "moved"):
                    if not src or not dst:
                        skipped.append({"id": op.id, "op": op_name, "reason": "missing src/dst"})
                        continue
                    if not clamp(src) or not clamp(dst):
                        skipped.append({"id": op.id, "op": op_name, "reason": "path outside wp_root"})
                        continue
                    if _sftp_exists(sftp, dst):
                        if not dry_run:
                            _sftp_rename(sftp, dst, src)
                        executed.append({"id": op.id, "op": op_name, "undo": f"{dst} -> {src}"})
                    else:
                        skipped.append({"id": op.id, "op": op_name, "reason": "dst missing"})
                    continue

                # delete/unlink undo
                if op_name in ("delete", "unlink"):
                    if not src:
                        skipped.append({"id": op.id, "op": op_name, "reason": "missing src"})
                        continue
                    if not clamp(src):
                        skipped.append({"id": op.id, "op": op_name, "reason": "path outside wp_root"})
                        continue
                    backup_dst = payload.get("backup_dst") or dst
                    if not backup_dst or not os.path.exists(str(backup_dst)):
                        skipped.append({"id": op.id, "op": op_name, "reason": "no local backup to restore"})
                        continue
                    if not dry_run:
                        _sftp_put_file(sftp, str(backup_dst), src)
                    executed.append({"id": op.id, "op": op_name, "restore": f"{backup_dst} -> {src}"})
                    continue

                # write undo
                if op_name == "write":
                    if not src:
                        skipped.append({"id": op.id, "op": op_name, "reason": "missing src"})
                        continue
                    if not clamp(src):
                        skipped.append({"id": op.id, "op": op_name, "reason": "path outside wp_root"})
                        continue
                    created = bool(payload.get("created", False))
                    backup_dst = payload.get("backup_dst") or payload.get("backup_path")
                    if created and (not backup_dst):
                        if _sftp_exists(sftp, src):
                            if not dry_run:
                                _sftp_remove_file(sftp, src)
                            executed.append({"id": op.id, "op": op_name, "undo": f"remove created {src}"})
                        else:
                            skipped.append({"id": op.id, "op": op_name, "reason": "created file missing"})
                        continue
                    if backup_dst and os.path.exists(str(backup_dst)):
                        if not dry_run:
                            _sftp_put_file(sftp, str(backup_dst), src)
                        executed.append({"id": op.id, "op": op_name, "restore": f"{backup_dst} -> {src}"})
                    else:
                        skipped.append({"id": op.id, "op": op_name, "reason": "no backup for write"})
                    continue

                # backup ops are not rolled back directly
                if op_name == "backup":
                    skipped.append({"id": op.id, "op": op_name, "reason": "backup op"})
                    continue

                skipped.append({"id": op.id, "op": op_name, "reason": "unsupported op"})

            except Exception as e:
                errors.append({"id": getattr(op, "id", None), "op": op_name, "error": str(e)})

        # status update
        try:
            if not dry_run and not errors:
                action.status = "rolled_back"
                db.session.commit()
        except Exception:
            try:
                db.session.rollback()
            except Exception:
                pass

        return {
            "ok": (len(errors) == 0),
            "action_id": action_id,
            "ticket_id": getattr(action, "ticket_id", None),
            "wp_root": boundary,
            "executed": executed,
            "skipped": skipped,
            "errors": errors,
            "dry_run": dry_run,
        }

    finally:
        try:
            sftp.close()
        except Exception:
            pass
        try:
            client.close()
        except Exception:
            pass





def read_text_remote(host, port, username, password, path, max_bytes=2_000_000) -> str:
    # Backwards compatible helper:
    # - If path points into our local WP_REPAIR_STORAGE_ROOT, read from disk.
    # - Otherwise treat it as remote SFTP path.
    try:
        sp = os.path.abspath(str(path))
        if sp.startswith(_storage_root() + os.sep):
            with open(sp, "rb") as f:
                data = f.read(int(max_bytes or 2_000_000))
            try:
                return data.decode("utf-8", errors="replace")
            except Exception:
                return str(data)
    except Exception:
        pass

    client = sftp_connect(host, port, username, password)
    sftp = client.open_sftp()
    try:
        return _read_text(sftp, path, max_bytes=max_bytes)
    finally:
        try:
            sftp.close()
        except Exception:
            pass
        try:
            client.close()
        except Exception:
            pass


def write_text_remote(host, port, username, password, path, text: str) -> None:
    # Backwards compatible helper:
    # - If path points into our local WP_REPAIR_STORAGE_ROOT, write to disk.
    # - Otherwise treat it as remote SFTP path.
    try:
        sp = os.path.abspath(str(path))
        if sp.startswith(_storage_root() + os.sep):
            _ensure_local_dir(os.path.dirname(sp))
            with open(sp, "w", encoding="utf-8") as f:
                f.write(str(text))
            return
    except Exception:
        pass

    client = sftp_connect(host, port, username, password)
    sftp = client.open_sftp()
    try:
        _write_text(sftp, path, text)
    finally:
        try:
            sftp.close()
        except Exception:
            pass
        try:
            client.close()
        except Exception:
            pass


def _parse_mode(mode_val) -> int:
    """
    Accepts: int, "0o755", "755", "0644"
    Returns: int suitable for sftp.chmod
    """
    if mode_val is None:
        raise ValueError("mode is None")
    if isinstance(mode_val, int):
        return mode_val

    s = str(mode_val).strip().lower()
    if s.startswith("0o"):
        return int(s, 8)
    if all(ch in "01234567" for ch in s):
        return int(s, 8)
    raise ValueError(f"Unsupported mode format: {mode_val}")

def meta_ensure(meta: dict) -> dict:
    # notes: string
    notes = meta.get("notes")
    if isinstance(notes, list):
        # legacy -> events
        meta.setdefault("events", [])
        meta["events"].extend([str(x) for x in notes if x is not None])
        meta["notes"] = ""
    elif notes is None:
        meta["notes"] = ""
    else:
        meta["notes"] = str(notes)

    # events: list
    if not isinstance(meta.get("events"), list):
        meta["events"] = []
    return meta


def meta_event(meta: dict, line: str) -> None:
    meta_ensure(meta)
    meta["events"].append(str(line))


def meta_note(meta: dict, note: str) -> None:
    meta_ensure(meta)
    meta["notes"] = str(note)
