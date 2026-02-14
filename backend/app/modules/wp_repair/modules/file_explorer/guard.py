from __future__ import annotations

import posixpath
from typing import Tuple


class PathError(ValueError):
    pass


def _norm(p: str) -> str:
    p = (p or "").strip()
    if not p:
        raise PathError("Missing path")
    if "\\" in p:
        raise PathError("Invalid path separator")
    p = posixpath.normpath(p)
    if not p.startswith("/"):
        raise PathError("Path must be absolute")
    return p


def assert_in_wp_root(path: str, wp_root: str) -> Tuple[str, str]:
    """
    Returns (norm_path, norm_wp_root) if path is within wp_root.
    """
    n_path = _norm(path)
    n_root = _norm(wp_root)

    # allow wp_root itself
    if n_path == n_root:
        return n_path, n_root

    # ensure within root
    prefix = n_root.rstrip("/") + "/"
    if not n_path.startswith(prefix):
        raise PathError("Path outside wp_root")
    return n_path, n_root


def safe_join(wp_root: str, rel: str) -> str:
    """
    Join wp_root with a relative path safely.
    """
    n_root = _norm(wp_root)
    rel = (rel or "").lstrip("/")
    out = posixpath.normpath(posixpath.join(n_root, rel))
    assert_in_wp_root(out, n_root)
    return out
