#var/www/sitefixer/backend/app/modules/wp_repair/sftp.py
from __future__ import annotations
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple
import posixpath

import paramiko

@dataclass
class SftpCreds:
    host: str
    username: str
    password: str
    port: int = 22

def connect_sftp(creds: SftpCreds) -> Tuple[paramiko.SSHClient, paramiko.SFTPClient]:
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(
        hostname=creds.host,
        port=int(creds.port or 22),
        username=creds.username,
        password=creds.password,
        timeout=12,
        banner_timeout=12,
        auth_timeout=12,
    )
    sftp = client.open_sftp()
    return client, sftp

def sftp_ls(sftp: paramiko.SFTPClient, path: str) -> List[Dict[str, Any]]:
    out = []
    for attr in sftp.listdir_attr(path):
        name = attr.filename
        mode = attr.st_mode
        is_dir = (mode & 0o040000) == 0o040000
        out.append({
            "name": name,
            "type": "dir" if is_dir else "file",
            "size": None if is_dir else attr.st_size,
        })
    # sort: dirs first
    out.sort(key=lambda x: (0 if x["type"] == "dir" else 1, x["name"].lower()))
    return out

def exists(sftp: paramiko.SFTPClient, p: str) -> bool:
    try:
        sftp.stat(p)
        return True
    except Exception:
        return False

def find_wp_roots(sftp: paramiko.SFTPClient, start: str = "/", max_depth: int = 6, max_nodes: int = 6000) -> List[Dict[str, Any]]:
    """
    Find WP roots by locating wp-config.php (simple heuristic).
    """
    roots = []
    seen = 0
    stack = [(start, 0)]
    while stack:
        path, depth = stack.pop()
        if depth > max_depth:
            continue
        seen += 1
        if seen > max_nodes:
            break

        wp_config = posixpath.join(path, "wp-config.php")
        if exists(sftp, wp_config):
            roots.append({"root_path": path, "label": path})
            continue

        # scan children
        try:
            for item in sftp.listdir_attr(path):
                name = item.filename
                mode = item.st_mode
                is_dir = (mode & 0o040000) == 0o040000
                if not is_dir:
                    continue
                if name in (".", ".."):
                    continue
                if name.startswith(".") and name not in (".well-known",):
                    continue
                child = posixpath.join(path, name)
                stack.append((child, depth + 1))
        except Exception:
            continue
    return roots
