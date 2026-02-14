# app/modules/wp_repair/modules/sftp/find_wp_root.py
from __future__ import annotations

from typing import List, Dict, Optional, Tuple
import posixpath

from .connect import sftp_connect


def _is_dir(longname: str) -> bool:
    # paramiko SFTPAttributes.longname starts with 'd' for directories on many servers
    return bool(longname) and longname[0] == "d"


def _stat_exists(sftp, path: str) -> bool:
    try:
        sftp.stat(path)
        return True
    except Exception:
        return False


def _looks_like_wp_root(sftp, p: str) -> bool:
    # WP root indicators
    return (
        _stat_exists(sftp, posixpath.join(p, "wp-config.php"))
        and _stat_exists(sftp, posixpath.join(p, "wp-content"))
        and _stat_exists(sftp, posixpath.join(p, "wp-includes"))
    )


def find_wp_roots(
    host: str,
    port: int,
    username: str,
    password: str,
    project_root: str,
    max_depth: int = 4,
    max_dirs: int = 300,
) -> List[Dict]:
    """
    BFS search within project_root to find WP installations.

    Returns list of candidates:
    [{ "wp_root": "...", "score": 100, "notes": ["..."] }, ...]
    """
    client = sftp_connect(host, port, username, password)
    sftp = client.open_sftp()
    try:
        root = posixpath.normpath(project_root)
        if not root.startswith("/"):
            root = "/" + root

        # quick check: maybe project_root is already WP root
        results: List[Dict] = []
        if _looks_like_wp_root(sftp, root):
            results.append({"wp_root": root, "score": 100, "notes": ["wp-config.php/wp-content/wp-includes present"]})
            return results

        # BFS directory walk with limits
        queue: List[Tuple[str, int]] = [(root, 0)]
        visited = set([root])
        dirs_seen = 0

        # Some common subfolders that often contain the actual webroot
        preferred_names = {"httpdocs", "htdocs", "public_html", "www", "public", "web", "site", "wordpress"}

        while queue:
            cur, depth = queue.pop(0)
            if depth > max_depth:
                continue

            # check current dir
            if _looks_like_wp_root(sftp, cur):
                notes = ["wp-config.php/wp-content/wp-includes present"]
                score = 90
                if posixpath.basename(cur) in preferred_names:
                    score += 5
                    notes.append("folder name suggests webroot")
                results.append({"wp_root": cur, "score": score, "notes": notes})

            # don't descend too deep / too many directories
            if depth == max_depth:
                continue
            if dirs_seen >= max_dirs:
                break

            # list children and enqueue directories
            try:
                for e in sftp.listdir_attr(cur):
                    if dirs_seen >= max_dirs:
                        break
                    if not _is_dir(getattr(e, "longname", "")):
                        continue
                    name = e.filename
                    # skip noisy/huge dirs
                    if name in {".git", ".svn", "node_modules", ".opcache", "cache", "logs"}:
                        continue
                    child = posixpath.normpath(posixpath.join(cur, name))
                    if not child.startswith(root.rstrip("/") + "/") and child != root:
                        # boundary safety
                        continue
                    if child in visited:
                        continue
                    visited.add(child)
                    queue.append((child, depth + 1))
                    dirs_seen += 1
            except Exception:
                continue

        # sort by score then shortest path
        results.sort(key=lambda x: (-x["score"], len(x["wp_root"])))
        # dedupe
        seen = set()
        uniq = []
        for r in results:
            if r["wp_root"] in seen:
                continue
            seen.add(r["wp_root"])
            uniq.append(r)
        return uniq
    finally:
        try:
            sftp.close()
        except Exception:
            pass
        try:
            client.close()
        except Exception:
            pass
