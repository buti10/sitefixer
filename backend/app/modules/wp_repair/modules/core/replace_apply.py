from __future__ import annotations

import os
import posixpath
from typing import Any, Dict, List, Optional

from ..sftp.connect import sftp_connect
from ..audit.actions import quarantine_move
from .manifest import core_file_abs_path
from .replace_preview import core_replace_preview


def _mkdir_p_remote(sftp, path: str) -> None:
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


def _upload_file(sftp, local_path: str, remote_path: str) -> None:
    rdir = posixpath.dirname(remote_path)
    _mkdir_p_remote(sftp, rdir)
    sftp.put(local_path, remote_path)


def _derive_action_id(action_meta_path: str) -> str:
    """
    action_meta_path:
      .../.sitefixer/quarantine/actions/<ACTION_ID>/meta.json
    """
    return posixpath.basename(posixpath.dirname(posixpath.normpath(action_meta_path)))


def core_replace_apply(
    host: str,
    port: int,
    username: str,
    password: str,
    wp_root: str,
    action_meta_path: str,
    action_moved_dir: str,
    *,
    wp_version: Optional[str] = None,
    core_cache_base: str = "/var/www/sitefixer/core-cache/wordpress",
    max_files: int = 5000,
    max_replace: int = 500,
    policy: Dict[str, Any] | None = None,
    # --- compatibility with endpoints ---
    allow_changed: bool = True,
    allow_missing: bool = False,
    **_ignored: Any,
) -> Dict[str, Any]:
    """
    Executes the replace plan:
    - quarantine current remote file into action_moved_dir (for rollback)
    - upload the cached core file over original
    """

    preview = core_replace_preview(
        host,
        port,
        username,
        password,
        wp_root,
        wp_version=wp_version,
        core_cache_base=core_cache_base,
        max_files=max_files,
        policy=policy,
        allow_changed=allow_changed,
        allow_missing=allow_missing,
        max_replace=max_replace,
    )
    if not preview.get("ok"):
        return {"ok": False, "error": preview.get("error"), "preview": preview}

    wp_root = posixpath.normpath(wp_root)
    wp_version2 = preview.get("wp_version")
    plan = (preview.get("plan") or [])[: int(max_replace)]

    action_id = _derive_action_id(action_meta_path)

    # preflight: ensure all local source files exist BEFORE touching remote
    missing_local: List[Dict[str, Any]] = []
    for it in plan:
        rel = it["rel"]
        local_path = core_file_abs_path(wp_version2, rel, base_dir=core_cache_base)
        if not os.path.isfile(local_path):
            missing_local.append({"rel": rel, "local_path": local_path})

    if missing_local:
        return {
            "ok": False,
            "error": "core-cache missing source files (preflight failed)",
            "missing_local": missing_local[:50],
            "wp_version": wp_version2,
            "wp_root": wp_root,
            "preview": preview,
        }

    client = sftp_connect(host, port, username, password)
    sftp = client.open_sftp()
    try:
        replaced: List[Dict[str, Any]] = []
        errors: List[Dict[str, Any]] = []

        for it in plan:
            rel = it["rel"]
            remote_path = posixpath.join(wp_root, rel)
            local_path = core_file_abs_path(wp_version2, rel, base_dir=core_cache_base)

            # 1) quarantine old remote file
            try:
                qm = quarantine_move(
                    host, port, username, password,
                    wp_root=wp_root,
                    src_path=remote_path,
                    action_id=action_id,
                    kind="FILE",
                )
                backup_path = qm.get("dst_path") if qm.get("ok") else None


            except Exception as e:
                errors.append(
                    {"rel": rel, "path": remote_path, "error": f"quarantine_move failed: {e}"}
                )
                continue

            # 2) upload cached file
            try:
                _upload_file(sftp, local_path, remote_path)
                replaced.append({"rel": rel, "path": remote_path})
            except Exception as e:
                errors.append({"rel": rel, "path": remote_path, "error": str(e)})

        return {
            "ok": len(errors) == 0,
            "wp_root": wp_root,
            "wp_version": wp_version2,
            "replaced": replaced,
            "errors": errors,
            "preview": preview,
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
