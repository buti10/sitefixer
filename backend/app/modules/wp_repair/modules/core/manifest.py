from __future__ import annotations

import json
import os
import posixpath
from dataclasses import dataclass
from typing import Dict, Any, Optional


DEFAULT_CORE_CACHE_BASE = "/var/www/sitefixer/core-cache/wordpress"


class ManifestError(RuntimeError):
    pass


@dataclass
class CoreManifest:
    wp_version: str
    base_dir: str
    # rel -> sha256
    files: Dict[str, str]
    # optional metadata
    meta: Dict[str, Any]


def _norm_ver(v: str) -> str:
    return (v or "").strip().lstrip("v")


def _read_json(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        raise ManifestError(f"Core manifest not found: {path}")
    except Exception as e:
        raise ManifestError(f"Failed to read manifest: {path}: {e}")


def _validate_files_map(files_obj: Any) -> Dict[str, str]:
    # must be map[str, str]
    if not isinstance(files_obj, dict):
        raise ManifestError("manifest.json 'files' must be map[str,str]")
    out: Dict[str, str] = {}
    for k, v in files_obj.items():
        if not isinstance(k, str) or not isinstance(v, str):
            raise ManifestError("manifest.json 'files' must be map[str,str]")
        kk = k.lstrip("/").replace("\\", "/")
        vv = v.strip().lower()
        out[kk] = vv
    return out


def manifest_dir_for_version(wp_version: str, base_dir: str = DEFAULT_CORE_CACHE_BASE) -> str:
    """
    Supports both layouts:

    A) /core-cache/wordpress/<ver>/manifest.json
       /core-cache/wordpress/<ver>/<rel>

    B) /core-cache/wordpress/<ver>/core/manifest.json
       /core-cache/wordpress/<ver>/core/<rel>

    We return the directory that actually contains the manifest.json.
    """
    v = _norm_ver(wp_version)
    cand_a = os.path.join(base_dir, v)
    cand_b = os.path.join(base_dir, v, "core")

    if os.path.isfile(os.path.join(cand_a, "manifest.json")):
        return cand_a
    if os.path.isfile(os.path.join(cand_b, "manifest.json")):
        return cand_b

    # default: prefer A (caller will error on load)
    return cand_a


def load_core_manifest(wp_version: str, base_dir: str = DEFAULT_CORE_CACHE_BASE) -> CoreManifest:
    v = _norm_ver(wp_version)
    mdir = manifest_dir_for_version(v, base_dir=base_dir)
    mpath = os.path.join(mdir, "manifest.json")

    raw = _read_json(mpath)
    files = _validate_files_map(raw.get("files"))

    meta = {}
    for k in ("wp_version", "created_ts", "source", "notes"):
        if k in raw:
            meta[k] = raw[k]

    # manifest may store a different wp_version; we keep requested v
    return CoreManifest(wp_version=v, base_dir=mdir, files=files, meta=meta)


def core_file_abs_path(wp_version: str, rel_path: str, base_dir: str = DEFAULT_CORE_CACHE_BASE) -> str:
    """
    Returns absolute local path in core-cache for a given core rel file.

    It uses the detected manifest folder (with or without /core).
    """
    v = _norm_ver(wp_version)
    mdir = manifest_dir_for_version(v, base_dir=base_dir)
    rel = rel_path.lstrip("/").replace("\\", "/")
    return os.path.join(mdir, rel)


def remote_abs_path(wp_root: str, rel_path: str) -> str:
    """
    WP remote path join (posix)
    """
    wp_root = posixpath.normpath(wp_root)
    rel = rel_path.lstrip("/").replace("\\", "/")
    return posixpath.join(wp_root, rel)
