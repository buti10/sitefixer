# app/modules/repair_beta/sftp_client.py
from __future__ import annotations
import posixpath
import stat
from dataclasses import dataclass
from typing import Iterable, Optional, Tuple

import paramiko


class RepairError(Exception):
    pass


@dataclass
class SFTPConn:
    host: str
    port: int
    user: str
    password: str


def _norm(p: str) -> str:
    if not p:
        return "/"
    p = p.replace("\\", "/")
    if not p.startswith("/"):
        p = "/" + p
    return posixpath.normpath(p) + ("/" if p.endswith("/") and p != "/" else "")


def clamp_path(root: str, target: str) -> str:
    """
    Clamp target path to be inside root.
    root must be absolute and end with '/' (except '/').
    """
    root_n = _norm(root)
    t_n = _norm(target)
    # Ensure trailing slash on root (except '/')
    if root_n != "/" and not root_n.endswith("/"):
        root_n += "/"

    # Normalize without trailing slash for compare
    root_cmp = root_n if root_n == "/" else root_n.rstrip("/") + "/"
    t_cmp = t_n if t_n == "/" else t_n

    if root_cmp != "/" and not t_cmp.startswith(root_cmp):
        raise RepairError(f"Path outside wp_root: {t_n}")
    return t_n


def connect_sftp(conn: SFTPConn, timeout: int = 20) -> Tuple[paramiko.Transport, paramiko.SFTPClient]:
    try:
        t = paramiko.Transport((conn.host, conn.port))
        t.banner_timeout = timeout
        t.connect(username=conn.user, password=conn.password)
        sftp = paramiko.SFTPClient.from_transport(t)
        return t, sftp
    except Exception as e:
        raise RepairError(f"SFTP connect failed: {e}")


def close_sftp(t: Optional[paramiko.Transport], sftp: Optional[paramiko.SFTPClient]) -> None:
    try:
        if sftp:
            sftp.close()
    finally:
        if t:
            t.close()


def exists(sftp: paramiko.SFTPClient, path: str) -> bool:
    try:
        sftp.stat(path)
        return True
    except FileNotFoundError:
        return False
    except IOError:
        return False


def read_text(sftp: paramiko.SFTPClient, path: str, max_bytes: int = 512_000) -> str:
    f = sftp.open(path, "r")
    try:
        data = f.read(max_bytes)
        if isinstance(data, bytes):
            return data.decode("utf-8", errors="replace")
        return str(data)
    finally:
        f.close()


def listdir(sftp: paramiko.SFTPClient, path: str) -> Iterable[str]:
    try:
        return sftp.listdir(path)
    except Exception:
        return []


def stat_mode(sftp: paramiko.SFTPClient, path: str) -> Optional[str]:
    try:
        st = sftp.stat(path)
        return oct(stat.S_IMODE(st.st_mode)).replace("0o", "0").rjust(4, "0")
    except Exception:
        return None


def is_symlink(sftp: paramiko.SFTPClient, path: str) -> bool:
    try:
        st = sftp.lstat(path)
        return stat.S_ISLNK(st.st_mode)
    except Exception:
        return False


def safe_chmod(sftp: paramiko.SFTPClient, path: str, mode_octal_str: str) -> None:
    # do not chmod symlinks
    if is_symlink(sftp, path):
        return
    mode_int = int(mode_octal_str, 8)
    sftp.chmod(path, mode_int)


def rename_safe(sftp: paramiko.SFTPClient, src: str, dst: str) -> None:
    # If dst exists, add suffix
    if exists(sftp, dst):
        base = dst
        i = 1
        while exists(sftp, f"{base}.{i}"):
            i += 1
        dst = f"{base}.{i}"
    sftp.rename(src, dst)
