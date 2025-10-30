# app/scanner/sftp_adapter.py
from __future__ import annotations
from typing import Any, Optional, List
import paramiko, os, stat

# Quelle deiner Sessions
from app.scanner.routes import sftp_routes as R

class SFTPProxy:
    """Leichter Proxy. Öffnet SSH/SFTP pro Operation und schließt wieder."""
    def __init__(self, sess: dict):
        self.sess = sess

    def _connect(self):
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c.connect(
            hostname=self.sess["host"].strip(),
            port=int(self.sess.get("port", 22)),
            username=self.sess["username"],
            password=self.sess.get("password", "") or "",
            look_for_keys=False, allow_agent=False,
            timeout=15, banner_timeout=15, auth_timeout=15,
        )
        return c, c.open_sftp()

    def listdir_attr(self, path: str):
        client = sftp = None
        try:
            client, sftp = self._connect()
            try:
                return sftp.listdir_attr(path if path != "/" else ".")
            except FileNotFoundError:
                alt = path.lstrip("/") or "."
                return sftp.listdir_attr(alt)
        finally:
            try:
                if sftp: sftp.close()
            except: pass
            try:
                if client: client.close()
            except: pass

    def stat(self, path: str):
        client = sftp = None
        try:
            client, sftp = self._connect()
            try:
                return sftp.stat(path)
            except FileNotFoundError:
                alt = path.lstrip("/") or "."
                return sftp.stat(alt)
        finally:
            try:
                if sftp: sftp.close()
            except: pass
            try:
                if client: client.close()
            except: pass

    def read_bytes(self, path: str, limit: int) -> bytes:
        client = sftp = None
        try:
            client, sftp = self._connect()
            try:
                f = sftp.file(path, "rb")
            except FileNotFoundError:
                alt = path.lstrip("/") or "."
                f = sftp.file(alt, "rb")
            try:
                return f.read(limit)
            finally:
                try: f.close()
                except: pass
        finally:
            try:
                if sftp: sftp.close()
            except: pass
            try:
                if client: client.close()
            except: pass

def get_client_by_sid(sid: str) -> Optional[Any]:
    sess = R.SESSIONS.get(sid)
    if not sess:
        return None
    return SFTPProxy(sess)
