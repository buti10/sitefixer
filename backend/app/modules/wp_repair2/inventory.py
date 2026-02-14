from __future__ import annotations

import os
import re
import posixpath
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Iterable


_MAX_READ_BYTES = 512_000  # hard cap per file read


# ============================================================
# Filesystem Abstraction
# ============================================================

class FSBase:
    """Minimal filesystem interface used by inventory."""
    sep: str = "/"

    def abspath(self, p: str) -> str:
        raise NotImplementedError

    def isabs(self, p: str) -> bool:
        raise NotImplementedError

    def exists(self, p: str) -> bool:
        raise NotImplementedError

    def is_file(self, p: str) -> bool:
        raise NotImplementedError

    def is_dir(self, p: str) -> bool:
        raise NotImplementedError

    def read_bytes(self, p: str, max_bytes: int) -> bytes:
        raise NotImplementedError

    def iterdir(self, p: str) -> List[str]:
        """Return full paths of direct children."""
        raise NotImplementedError

    def glob(self, p: str, pattern: str) -> List[str]:
        """Non-recursive glob inside directory p (pattern like '*.php')."""
        raise NotImplementedError

    def rglob(self, p: str, pattern: str, max_results: int = 25) -> List[str]:
        """Recursive glob with a hard stop."""
        raise NotImplementedError

    def join(self, *parts: str) -> str:
        raise NotImplementedError

    def relpath(self, child: str, parent: str) -> str:
        raise NotImplementedError


class LocalFS(FSBase):
    sep = os.sep

    def abspath(self, p: str) -> str:
        return str(Path(p).expanduser().resolve(strict=False))

    def isabs(self, p: str) -> bool:
        return Path(p).is_absolute()

    def exists(self, p: str) -> bool:
        return Path(p).exists()

    def is_file(self, p: str) -> bool:
        return Path(p).is_file()

    def is_dir(self, p: str) -> bool:
        return Path(p).is_dir()

    def read_bytes(self, p: str, max_bytes: int) -> bytes:
        path = Path(p)
        if not path.exists() or not path.is_file():
            return b""
        return path.read_bytes()[:max_bytes]

    def iterdir(self, p: str) -> List[str]:
        path = Path(p)
        if not path.exists() or not path.is_dir():
            return []
        return [str(x) for x in path.iterdir()]

    def glob(self, p: str, pattern: str) -> List[str]:
        path = Path(p)
        if not path.exists() or not path.is_dir():
            return []
        return [str(x) for x in path.glob(pattern)]

    def rglob(self, p: str, pattern: str, max_results: int = 25) -> List[str]:
        path = Path(p)
        if not path.exists() or not path.is_dir():
            return []
        out = []
        for x in path.rglob(pattern):
            out.append(str(x))
            if len(out) >= max_results:
                break
        return out

    def join(self, *parts: str) -> str:
        return str(Path(*parts))

    def relpath(self, child: str, parent: str) -> str:
        try:
            return str(Path(child).resolve(strict=False).relative_to(Path(parent).resolve(strict=False)))
        except Exception:
            return child


class SftpFS(FSBase):
    """
    Wrap a Paramiko-like SFTP client.

    Required methods on sftp:
      - stat(path)
      - listdir(path)
      - listdir_attr(path) (optional; we don't require)
      - open(path, 'rb')
    """
    sep = "/"

    def __init__(self, sftp):
        self.sftp = sftp

    def abspath(self, p: str) -> str:
        # normalize remote posix path
        if not p:
            return "/"
        if not p.startswith("/"):
            # treat as relative -> make absolute from /
            p = "/" + p
        return posixpath.normpath(p)

    def isabs(self, p: str) -> bool:
        return p.startswith("/")

    def exists(self, p: str) -> bool:
        p = self.abspath(p)
        try:
            self.sftp.stat(p)
            return True
        except Exception:
            return False

    def is_file(self, p: str) -> bool:
        p = self.abspath(p)
        try:
            st = self.sftp.stat(p)
            # paramiko: st_mode available
            import stat
            return stat.S_ISREG(st.st_mode)
        except Exception:
            return False

    def is_dir(self, p: str) -> bool:
        p = self.abspath(p)
        try:
            st = self.sftp.stat(p)
            import stat
            return stat.S_ISDIR(st.st_mode)
        except Exception:
            return False

    def read_bytes(self, p: str, max_bytes: int) -> bytes:
        p = self.abspath(p)
        try:
            with self.sftp.open(p, "rb") as f:
                return f.read(max_bytes)
        except Exception:
            return b""

    def iterdir(self, p: str) -> List[str]:
        p = self.abspath(p)
        if not self.is_dir(p):
            return []
        try:
            names = self.sftp.listdir(p)
            return [self.join(p, n) for n in names if n not in (".", "..")]
        except Exception:
            return []

    def glob(self, p: str, pattern: str) -> List[str]:
        # simple fnmatch in one dir
        import fnmatch
        out = []
        for child in self.iterdir(p):
            name = child.split("/")[-1]
            if fnmatch.fnmatch(name, pattern):
                out.append(child)
        return out

    def rglob(self, p: str, pattern: str, max_results: int = 25) -> List[str]:
        import fnmatch
        out: List[str] = []
        stack = [self.abspath(p)]
        while stack and len(out) < max_results:
            cur = stack.pop()
            if not self.is_dir(cur):
                continue
            for child in self.iterdir(cur):
                if len(out) >= max_results:
                    break
                name = child.split("/")[-1]
                if self.is_dir(child):
                    stack.append(child)
                else:
                    if fnmatch.fnmatch(name, pattern):
                        out.append(child)
        return out

    def join(self, *parts: str) -> str:
        parts2 = []
        for i, x in enumerate(parts):
            if i == 0:
                parts2.append(x.rstrip("/"))
            else:
                parts2.append(x.strip("/"))
        return posixpath.normpath("/".join(parts2)) or "/"

    def relpath(self, child: str, parent: str) -> str:
        child = self.abspath(child)
        parent = self.abspath(parent)
        if child.startswith(parent.rstrip("/") + "/"):
            return child[len(parent.rstrip("/")) + 1 :]
        return child


# ============================================================
# Helpers
# ============================================================

def _read_text(fs: FSBase, path: str, max_bytes: int = _MAX_READ_BYTES) -> str:
    data = fs.read_bytes(path, max_bytes=max_bytes)
    if not data:
        return ""
    try:
        return data.decode("utf-8", errors="replace")
    except Exception:
        return data.decode(errors="replace")


def _parse_php_define(text: str, key: str) -> Optional[str]:
    m = re.search(rf"define\(\s*['\"]{re.escape(key)}['\"]\s*,\s*['\"]([^'\"]*)['\"]\s*\)", text)
    return m.group(1).strip() if m else None


def _parse_table_prefix(text: str) -> Optional[str]:
    m = re.search(r"^\s*\$table_prefix\s*=\s*['\"]([^'\"]+)['\"]\s*;", text, re.MULTILINE)
    return m.group(1).strip() if m else None


def _parse_wp_debug_flags(text: str) -> Dict[str, Optional[str]]:
    keys = ["WP_DEBUG", "WP_DEBUG_LOG", "WP_DEBUG_DISPLAY"]
    return {k: _parse_php_define(text, k) for k in keys}


def _parse_header_value(text: str, header: str) -> Optional[str]:
    pattern = rf"^{re.escape(header)}\s*:\s*(.+)$"
    m = re.search(pattern, text, re.MULTILINE | re.IGNORECASE)
    return m.group(1).strip() if m else None


def _is_wordpress_root(fs: FSBase, root: str) -> bool:
    return fs.exists(fs.join(root, "wp-config.php")) and fs.exists(fs.join(root, "wp-settings.php"))


def _read_wordpress_version(fs: FSBase, root: str) -> Optional[str]:
    vfile = fs.join(root, "wp-includes", "version.php")
    txt = _read_text(fs, vfile, max_bytes=120_000)
    m = re.search(r"\$wp_version\s*=\s*'([^']+)'\s*;", txt)
    return m.group(1).strip() if m else None


def _detect_wp_content_dir(fs: FSBase, root: str) -> str:
    return fs.join(root, "wp-content")


def _path_clamp(fs: FSBase, root_path: str) -> Tuple[bool, str, str]:
    """
    Clamp for BOTH local and SFTP paths.
    - Must be absolute
    - If REPAIR_ALLOWED_ROOTS set (comma-separated), must be within one of them
      (for SFTP: prefix match on normalized posix paths)
    """
    root = fs.abspath(root_path)
    if not fs.isabs(root):
        return False, "root_path must be an absolute path", root

    allowed = os.getenv("REPAIR_ALLOWED_ROOTS", "").strip()
    if not allowed:
        return True, "", root

    allowed_roots = [fs.abspath(x.strip()) for x in allowed.split(",") if x.strip()]
    for ar in allowed_roots:
        # within check: prefix match with boundary
        ar2 = ar.rstrip("/")
        if root == ar2 or root.startswith(ar2 + "/"):
            return True, "", root

    return False, "root_path not allowed (outside REPAIR_ALLOWED_ROOTS)", root


# ============================================================
# Data structures
# ============================================================

@dataclass
class PluginInfo:
    slug: str
    name: Optional[str]
    version: Optional[str]
    author: Optional[str]
    plugin_uri: Optional[str]
    main_file: str
    kind: str  # "folder" | "single-file"
    path: str


@dataclass
class ThemeInfo:
    slug: str
    name: Optional[str]
    version: Optional[str]
    author: Optional[str]
    theme_uri: Optional[str]
    template: Optional[str]
    status: str  # "child" | "parent" | "unknown"
    style_css: str
    path: str


# ============================================================
# Inventory core (FS-based)
# ============================================================

def read_wp_config(fs: FSBase, root: str, redact_secrets: bool = True) -> Dict[str, Any]:
    cfg = fs.join(root, "wp-config.php")
    txt = _read_text(fs, cfg, max_bytes=256_000)
    if not txt:
        return {"found": False}

    db_name = _parse_php_define(txt, "DB_NAME")
    db_user = _parse_php_define(txt, "DB_USER")
    db_pass = _parse_php_define(txt, "DB_PASSWORD")
    db_host = _parse_php_define(txt, "DB_HOST")
    charset = _parse_php_define(txt, "DB_CHARSET")
    collate = _parse_php_define(txt, "DB_COLLATE")

    return {
        "found": True,
        "table_prefix": _parse_table_prefix(txt),
        "db": {
            "name": db_name,
            "user": db_user,
            "password": ("***" if (redact_secrets and db_pass) else db_pass),
            "host": db_host,
            "charset": charset,
            "collate": collate,
        },
        "debug": _parse_wp_debug_flags(txt),
    }


def _find_plugin_main_file_in_folder(fs: FSBase, folder: str) -> Optional[str]:
    slug = folder.rstrip("/").split("/")[-1]
    candidate = fs.join(folder, f"{slug}.php")
    if fs.exists(candidate):
        return candidate

    php_files = fs.glob(folder, "*.php")
    for f in php_files:
        head = _read_text(fs, f, max_bytes=32_000)
        if re.search(r"^\s*Plugin Name\s*:\s*.+$", head, re.MULTILINE | re.IGNORECASE):
            return f

    checked = 0
    for f in fs.rglob(folder, "*.php", max_results=25):
        checked += 1
        if checked > 25:
            break
        head = _read_text(fs, f, max_bytes=32_000)
        if re.search(r"^\s*Plugin Name\s*:\s*.+$", head, re.MULTILINE | re.IGNORECASE):
            return f

    return None


def list_plugins(fs: FSBase, root: str) -> List[PluginInfo]:
    wp_content = _detect_wp_content_dir(fs, root)
    plugins_dir = fs.join(wp_content, "plugins")
    out: List[PluginInfo] = []
    if not fs.exists(plugins_dir) or not fs.is_dir(plugins_dir):
        return out

    entries = fs.iterdir(plugins_dir)
    entries_sorted = sorted(entries, key=lambda p: p.split("/")[-1].lower())

    for entry in entries_sorted:
        name = entry.split("/")[-1]
        if name.startswith("."):
            continue

        # Single-file plugin
        if fs.is_file(entry) and name.lower().endswith(".php"):
            head = _read_text(fs, entry, max_bytes=32_000)
            out.append(
                PluginInfo(
                    slug=name[:-4],
                    name=_parse_header_value(head, "Plugin Name"),
                    version=_parse_header_value(head, "Version"),
                    author=_parse_header_value(head, "Author"),
                    plugin_uri=_parse_header_value(head, "Plugin URI"),
                    main_file=fs.relpath(entry, root),
                    kind="single-file",
                    path=entry,
                )
            )
            continue

        # Folder plugin
        if fs.is_dir(entry):
            main = _find_plugin_main_file_in_folder(fs, entry)
            if not main:
                out.append(
                    PluginInfo(
                        slug=name,
                        name=None,
                        version=None,
                        author=None,
                        plugin_uri=None,
                        main_file="",
                        kind="folder",
                        path=entry,
                    )
                )
                continue

            head = _read_text(fs, main, max_bytes=32_000)
            out.append(
                PluginInfo(
                    slug=name,
                    name=_parse_header_value(head, "Plugin Name"),
                    version=_parse_header_value(head, "Version"),
                    author=_parse_header_value(head, "Author"),
                    plugin_uri=_parse_header_value(head, "Plugin URI"),
                    main_file=fs.relpath(main, root),
                    kind="folder",
                    path=entry,
                )
            )

    return out


def list_mu_plugins(fs: FSBase, root: str) -> List[PluginInfo]:
    wp_content = _detect_wp_content_dir(fs, root)
    mu_dir = fs.join(wp_content, "mu-plugins")
    out: List[PluginInfo] = []
    if not fs.exists(mu_dir) or not fs.is_dir(mu_dir):
        return out

    for entry in sorted(fs.glob(mu_dir, "*.php"), key=lambda p: p.split("/")[-1].lower()):
        head = _read_text(fs, entry, max_bytes=32_000)
        name = entry.split("/")[-1]
        out.append(
            PluginInfo(
                slug=name[:-4],
                name=_parse_header_value(head, "Plugin Name"),
                version=_parse_header_value(head, "Version"),
                author=_parse_header_value(head, "Author"),
                plugin_uri=_parse_header_value(head, "Plugin URI"),
                main_file=fs.relpath(entry, root),
                kind="single-file",
                path=entry,
            )
        )
    return out


def list_themes(fs: FSBase, root: str) -> List[ThemeInfo]:
    wp_content = _detect_wp_content_dir(fs, root)
    themes_dir = fs.join(wp_content, "themes")
    out: List[ThemeInfo] = []
    if not fs.exists(themes_dir) or not fs.is_dir(themes_dir):
        return out

    theme_dirs = [p for p in fs.iterdir(themes_dir) if fs.is_dir(p)]
    theme_dirs = sorted(theme_dirs, key=lambda p: p.split("/")[-1].lower())

    for theme_dir in theme_dirs:
        slug = theme_dir.split("/")[-1]
        style = fs.join(theme_dir, "style.css")
        txt = _read_text(fs, style, max_bytes=80_000)
        name = _parse_header_value(txt, "Theme Name")
        version = _parse_header_value(txt, "Version")
        author = _parse_header_value(txt, "Author")
        uri = _parse_header_value(txt, "Theme URI")
        template = _parse_header_value(txt, "Template")

        status = "child" if template else ("parent" if name else "unknown")

        out.append(
            ThemeInfo(
                slug=slug,
                name=name,
                version=version,
                author=author,
                theme_uri=uri,
                template=template,
                status=status,
                style_css=fs.relpath(style, root) if fs.exists(style) else "",
                path=theme_dir,
            )
        )

    return out


def list_dropins_and_cache_flags(fs: FSBase, root: str) -> Dict[str, Any]:
    wp_content = _detect_wp_content_dir(fs, root)
    checks = {
        "advanced_cache": fs.join(wp_content, "advanced-cache.php"),
        "object_cache": fs.join(wp_content, "object-cache.php"),
        "db_php": fs.join(wp_content, "db.php"),
        "maintenance": fs.join(root, ".maintenance"),
        "cache_dir": fs.join(wp_content, "cache"),
    }
    return {k: (p if fs.exists(p) else None) for k, p in checks.items()}


def build_inventory(
    root_path: str,
    redact_secrets: bool = True,
    fs: Optional[FSBase] = None,
) -> Dict[str, Any]:
    fs = fs or LocalFS()

    ok, err, root = _path_clamp(fs, root_path)

    result: Dict[str, Any] = {
        "ok": ok,
        "error": err or None,
        "root_path": root,
        "wp_detected": False,
        "wp_version": None,
        "wp_content_path": _detect_wp_content_dir(fs, root) if ok else None,
        "wp_config": {},
        "plugins": [],
        "mu_plugins": [],
        "themes": [],
        "dropins": {},
        "errors": [],
        "debug_fs": {
            "mode": fs.__class__.__name__,
            "root_exists": fs.exists(root) if ok else None,
            "root_is_dir": fs.is_dir(root) if ok else None,
            "has_wp_config": fs.exists(fs.join(root, "wp-config.php")) if ok else None,
            "has_wp_settings": fs.exists(fs.join(root, "wp-settings.php")) if ok else None,
            "has_version_php": fs.exists(fs.join(root, "wp-includes", "version.php")) if ok else None,
        },
    }

    if not ok:
        return result

    result["wp_detected"] = _is_wordpress_root(fs, root)
    if not result["wp_detected"]:
        result["errors"].append("WordPress root not detected (missing wp-config.php/wp-settings.php).")
        return result

    result["wp_version"] = _read_wordpress_version(fs, root)
    result["wp_config"] = read_wp_config(fs, root, redact_secrets=redact_secrets)

    try:
        result["plugins"] = [asdict(p) for p in list_plugins(fs, root)]
        result["mu_plugins"] = [asdict(p) for p in list_mu_plugins(fs, root)]
        result["themes"] = [asdict(t) for t in list_themes(fs, root)]
        result["dropins"] = list_dropins_and_cache_flags(fs, root)
    except Exception as e:
        result["errors"].append(f"Inventory scan failed: {type(e).__name__}: {e}")

    return result
