from __future__ import annotations

import posixpath
import stat
from typing import Any, Dict, Optional

from app.modules.wp_repair.modules.audit.actions import create_action, quarantine_move
from app.modules.wp_repair.modules.sftp.connect import sftp_connect
from .guard import assert_in_wp_root, PathError

_ALLOWED_WRITE_SUFFIXES = (
    "wp-config.php",
    ".htaccess",
    "php.ini",
    "user.ini",
    ".ini",
    ".php",
    ".txt",
    ".log",
    ".json",
    ".md",
)

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


def explorer_write(
    host: str,
    port: int,
    username: str,
    password: str,
    wp_root: str,
    path: str,
    text: str,
    *,
    reason: str,
    ticket_id: int,
    actor_user_id: int,
    actor_name: Optional[str] = None,
    project_root: Optional[str] = None,
    max_bytes: int = 500_000,
    create_parents: bool = True,
) -> Dict[str, Any]:
    path, wp_root = assert_in_wp_root(path, wp_root)

    if text is None:
        raise PathError("Missing text")
    if not isinstance(text, str):
        text = str(text)

    if len(text.encode("utf-8", errors="replace")) > max_bytes:
        return {"ok": False, "error": f"Text too large (>{max_bytes} bytes)", "path": path}
    
    lp = path.lower()
    if not lp.endswith(_ALLOWED_WRITE_SUFFIXES):
        return {"ok": False, "error": "Write not allowed for this file type", "path": path}

    action = create_action(
        host, port, username, password, wp_root,
        fix_id="explorer_write",
        context={"path": path, "reason": reason},
        ticket_id=int(ticket_id or 0),
        actor_user_id=int(actor_user_id or 0),
        actor_name=actor_name,
        project_root=project_root,
    )

    client = sftp_connect(host, port, username, password)
    sftp = client.open_sftp()
    try:
        # create parent directories if requested
        if create_parents:
            parent = posixpath.dirname(path)
            _mkdir_p(sftp, parent)

        existed = False
        try:
            st = sftp.stat(path)
            existed = True
            if stat.S_ISDIR(getattr(st, "st_mode", 0)):
                return {"ok": False, "error": "Path is a directory", "path": path, "action_id": action["action_id"]}
        except Exception:
            existed = False

        backup_path = None
        if existed:
            qm = quarantine_move(
                host, port, username, password,
                wp_root=wp_root,
                src_path=path,
                action_id=action["action_id"],
                kind="FILE",
            )
            backup_path = qm.get("dst_path") if qm.get("ok") else None


        # write new content
        f = sftp.open(path, "wb")
        try:
            f.write(text.encode("utf-8", errors="replace"))
        finally:
            f.close()

        return {
            "ok": True,
            "action_id": action["action_id"],
            "wp_root": wp_root,
            "path": path,
            "backup_path": backup_path,
            "written": True,
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
