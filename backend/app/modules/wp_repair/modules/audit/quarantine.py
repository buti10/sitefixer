from __future__ import annotations

import hashlib
import posixpath
from typing import Tuple


def quarantine_root(wp_root: str) -> str:
    return posixpath.join(posixpath.normpath(wp_root), ".sitefixer", "quarantine")


def _relpath(src_path: str, wp_root: str) -> str:
    src = posixpath.normpath(src_path)
    root = posixpath.normpath(wp_root)
    if src.startswith(root + "/"):
        return src[len(root) + 1 :]
    if src == root:
        return "."
    return src.lstrip("/")


def _hash_rel(rel: str) -> str:
    return hashlib.sha1(rel.encode("utf-8", errors="ignore")).hexdigest()[:10]


def quarantine_name(action_id: str, src_path: str, wp_root: str, kind: str) -> Tuple[str, dict]:
    """
    kind: "FILE" or "DIR"
    returns (filename, payload_for_db)
    """
    rel = _relpath(src_path, wp_root)
    key = _hash_rel(rel)
    base = posixpath.basename(posixpath.normpath(src_path))
    fname = f"{action_id}__{kind}__{key}__{base}"
    payload = {"relpath": rel, "key": key, "kind": kind, "basename": base}
    return fname, payload
