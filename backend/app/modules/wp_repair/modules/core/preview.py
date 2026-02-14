from __future__ import annotations

import hashlib
import posixpath
import re
from typing import Any, Dict, List, Optional

from ..sftp.connect import sftp_connect
from .manifest import (
    load_core_manifest,
    core_file_abs_path,
    DEFAULT_CORE_CACHE_BASE,
    ManifestError,
)

_VERSION_RE = re.compile(r"""\$wp_version\s*=\s*['"]([^'"]+)['"]\s*;""")


def _read_remote_text(sftp, path: str, max_bytes: int = 512_000) -> str:
    f = sftp.open(path, "r")
    try:
        data = f.read(max_bytes)
        if isinstance(data, bytes):
            return data.decode("utf-8", errors="replace")
        return str(data)
    finally:
        f.close()


def detect_wp_version_remote(host: str, port: int, username: str, password: str, wp_root: str) -> str:
    wp_root = posixpath.normpath(wp_root)
    version_php = posixpath.join(wp_root, "wp-includes", "version.php")

    client = sftp_connect(host, port, username, password)
    sftp = client.open_sftp()
    try:
        txt = _read_remote_text(sftp, version_php, max_bytes=512_000)
        m = _VERSION_RE.search(txt)
        if not m:
            raise RuntimeError("Could not detect WP version from wp-includes/version.php")
        return m.group(1).strip()
    finally:
        try:
            sftp.close()
        except Exception:
            pass
        try:
            client.close()
        except Exception:
            pass


def sha256_remote_file(sftp, path: str, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    f = sftp.open(path, "rb")
    try:
        while True:
            b = f.read(chunk_size)
            if not b:
                break
            if isinstance(b, str):
                b = b.encode("utf-8", errors="replace")
            h.update(b)
    finally:
        f.close()
    return h.hexdigest()


def sha256_local_file(path: str, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            b = f.read(chunk_size)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def core_integrity_preview(
    host: str,
    port: int,
    username: str,
    password: str,
    wp_root: str,
    *,
    wp_version: Optional[str] = None,
    core_cache_base: str = DEFAULT_CORE_CACHE_BASE,
    max_files: int = 2500,
    include_ok: bool = False,
) -> Dict[str, Any]:
    wp_root = posixpath.normpath(wp_root)

    if not wp_version:
        wp_version = detect_wp_version_remote(host, port, username, password, wp_root)

    try:
        manifest = load_core_manifest(wp_version, base_dir=core_cache_base)
    except ManifestError as e:
        return {"ok": False, "error": f"manifest error: {e}", "wp_root": wp_root, "wp_version": wp_version}

    files = list(manifest.files.items())
    total_manifest = len(files)

    if max_files <= 0:
        max_files = 1
    files = files[:max_files]

    client = sftp_connect(host, port, username, password)
    sftp = client.open_sftp()
    try:
        ok_files: List[Dict[str, Any]] = []
        changed_files: List[Dict[str, Any]] = []
        missing_files: List[Dict[str, Any]] = []
        unreadable_files: List[Dict[str, Any]] = []

        for rel, want_sha in files:
            remote_path = posixpath.join(wp_root, rel)

            try:
                sftp.stat(remote_path)
            except Exception as e:
                missing_files.append({"rel": rel, "path": remote_path, "error": str(e)})
                continue

            try:
                got_sha = sha256_remote_file(sftp, remote_path)
            except Exception as e:
                unreadable_files.append({"rel": rel, "path": remote_path, "error": str(e)})
                continue

            if got_sha == want_sha:
                if include_ok:
                    ok_files.append({"rel": rel, "path": remote_path})
            else:
                local_path = core_file_abs_path(wp_version, rel, base_dir=core_cache_base)
                local_sha = None
                try:
                    local_sha = sha256_local_file(local_path)
                except Exception:
                    pass

                changed_files.append(
                    {"rel": rel, "path": remote_path, "expected": want_sha, "remote": got_sha, "cache": local_sha}
                )

        res: Dict[str, Any] = {
            "ok": True,
            "wp_root": wp_root,
            "wp_version": wp_version,
            "core_cache_base": core_cache_base,
            "manifest_file_count": total_manifest,
            "checked": len(files),
            "max_files": max_files,
            "counts": {
                "ok": len(ok_files) if include_ok else None,
                "changed": len(changed_files),
                "missing": len(missing_files),
                "unreadable": len(unreadable_files),
            },
            "changed_files": changed_files[:200],
            "missing_files": missing_files[:200],
            "unreadable_files": unreadable_files[:200],
        }

        if include_ok:
            res["ok_files"] = ok_files[:200]

        res["integrity_ok"] = (
            (len(changed_files) == 0)
            and (len(missing_files) == 0)
            and (len(unreadable_files) == 0)
            and (total_manifest <= max_files)
        )

        if total_manifest > max_files:
            res["notes"] = [f"manifest has {total_manifest} files; preview checked only first {max_files}. Increase max_files for full integrity."]

        return res
    finally:
        try:
            sftp.close()
        except Exception:
            pass
        try:
            client.close()
        except Exception:
            pass
