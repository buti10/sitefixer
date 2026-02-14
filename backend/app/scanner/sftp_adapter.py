# app/scanner/sftp_adapter.py
from __future__ import annotations

from typing import Any, Optional
import paramiko

# Quelle deiner Sessions (SID -> Session-Objekt/Dict)
from app.scanner.routes import sftp_routes as R


class SFTPProxy:
    """
    Leichter Proxy: öffnet SSH/SFTP pro Operation und schließt wieder.
    Implementiert die wichtigsten Paramiko-SFTPClient-Methoden.
    """

    def __init__(self, sess: dict):
        self.sess = sess

    def _connect(self):
        c = paramiko.SSHClient()
        c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        c.connect(
            hostname=str(self.sess["host"]).strip(),
            port=int(self.sess.get("port", 22)),
            username=self.sess["username"],
            password=self.sess.get("password", "") or "",
            look_for_keys=False,
            allow_agent=False,
            timeout=15,
            banner_timeout=15,
            auth_timeout=15,
        )
        return c, c.open_sftp()

    @staticmethod
    def _alt_path(path: str) -> str:
        return (path or ".").lstrip("/") or "."

    class _RemoteFile:
        def __init__(self, ssh_client, sftp_client, file_obj):
            self._ssh = ssh_client
            self._sftp = sftp_client
            self._f = file_obj

        def close(self):
            try:
                if self._f:
                    self._f.close()
            finally:
                try:
                    if self._sftp:
                        self._sftp.close()
                except Exception:
                    pass
                try:
                    if self._ssh:
                        self._ssh.close()
                except Exception:
                    pass
                self._f = None
                self._sftp = None
                self._ssh = None

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            self.close()
            return False

        def read(self, *a, **kw):
            return self._f.read(*a, **kw)

        def write(self, *a, **kw):
            return self._f.write(*a, **kw)

        def flush(self):
            return self._f.flush()

        def seek(self, *a, **kw):
            return self._f.seek(*a, **kw)

        def tell(self):
            return self._f.tell()

        def __getattr__(self, name):
            return getattr(self._f, name)

    # --- SFTP ops ---

    def listdir_attr(self, path: str):
        ssh = sftp = None
        try:
            ssh, sftp = self._connect()
            try:
                return sftp.listdir_attr(path if path != "/" else ".")
            except FileNotFoundError:
                return sftp.listdir_attr(self._alt_path(path))
        finally:
            try:
                if sftp:
                    sftp.close()
            except Exception:
                pass
            try:
                if ssh:
                    ssh.close()
            except Exception:
                pass

    def stat(self, path: str):
        ssh = sftp = None
        try:
            ssh, sftp = self._connect()
            try:
                return sftp.stat(path)
            except FileNotFoundError:
                return sftp.stat(self._alt_path(path))
        finally:
            try:
                if sftp:
                    sftp.close()
            except Exception:
                pass
            try:
                if ssh:
                    ssh.close()
            except Exception:
                pass

    def open(self, path: str, mode: str = "rb"):
        ssh = sftp = None
        try:
            ssh, sftp = self._connect()
            try:
                f = sftp.open(path, mode)
            except FileNotFoundError:
                f = sftp.open(self._alt_path(path), mode)
            return self._RemoteFile(ssh, sftp, f)
        except Exception:
            try:
                if sftp:
                    sftp.close()
            except Exception:
                pass
            try:
                if ssh:
                    ssh.close()
            except Exception:
                pass
            raise

    def file(self, path: str, mode: str = "rb"):
        return self.open(path, mode)

    def rename(self, src: str, dst: str):
        ssh = sftp = None
        try:
            ssh, sftp = self._connect()
            try:
                return sftp.rename(src, dst)
            except FileNotFoundError:
                return sftp.rename(self._alt_path(src), self._alt_path(dst))
        finally:
            try:
                if sftp:
                    sftp.close()
            except Exception:
                pass
            try:
                if ssh:
                    ssh.close()
            except Exception:
                pass

    def posix_rename(self, src: str, dst: str):
        ssh = sftp = None
        try:
            ssh, sftp = self._connect()
            fn = getattr(sftp, "posix_rename", None)
            if callable(fn):
                try:
                    return fn(src, dst)
                except FileNotFoundError:
                    return fn(self._alt_path(src), self._alt_path(dst))
            return self.rename(src, dst)
        finally:
            try:
                if sftp:
                    sftp.close()
            except Exception:
                pass
            try:
                if ssh:
                    ssh.close()
            except Exception:
                pass

    def mkdir(self, path: str, mode: int = 0o777):
        ssh = sftp = None
        try:
            ssh, sftp = self._connect()
            try:
                return sftp.mkdir(path, mode=mode)
            except FileNotFoundError:
                return sftp.mkdir(self._alt_path(path), mode=mode)
        finally:
            try:
                if sftp:
                    sftp.close()
            except Exception:
                pass
            try:
                if ssh:
                    ssh.close()
            except Exception:
                pass

    def rmdir(self, path: str):
        ssh = sftp = None
        try:
            ssh, sftp = self._connect()
            try:
                return sftp.rmdir(path)
            except FileNotFoundError:
                return sftp.rmdir(self._alt_path(path))
        finally:
            try:
                if sftp:
                    sftp.close()
            except Exception:
                pass
            try:
                if ssh:
                    ssh.close()
            except Exception:
                pass

    def remove(self, path: str):
        ssh = sftp = None
        try:
            ssh, sftp = self._connect()
            try:
                return sftp.remove(path)
            except FileNotFoundError:
                return sftp.remove(self._alt_path(path))
        finally:
            try:
                if sftp:
                    sftp.close()
            except Exception:
                pass
            try:
                if ssh:
                    ssh.close()
            except Exception:
                pass

    def chmod(self, path: str, mode: int):
        ssh = sftp = None
        try:
            ssh, sftp = self._connect()
            try:
                return sftp.chmod(path, mode)
            except FileNotFoundError:
                return sftp.chmod(self._alt_path(path), mode)
        finally:
            try:
                if sftp:
                    sftp.close()
            except Exception:
                pass
            try:
                if ssh:
                    ssh.close()
            except Exception:
                pass


def _from_dict(obj: dict) -> Optional[Any]:
    """
    Deine Registry liefert oft dicts. Wir extrahieren daraus:
      - vorhandenen SFTPClient/Proxy (keys wie sftp/client/...)
      - oder bauen einen SFTPProxy aus Credentials (host/username/password/port)
    """
    # 1) Wenn dict bereits einen Client/Proxy enthält
    for k in ("sftp", "sftp_client", "client", "proxy", "_sftp", "_client"):
        v = obj.get(k)
        if v is not None:
            return v

    # 2) Wenn dict Credentials enthält -> Proxy bauen
    if "host" in obj and "username" in obj:
        # Passwort kann fehlen (key auth) -> aber in deinem System offenbar passwort-basiert
        sess = {
            "host": obj.get("host"),
            "port": obj.get("port", 22),
            "username": obj.get("username"),
            "password": obj.get("password", "") or "",
        }
        # Defensive: host/username müssen valide sein
        if sess["host"] and sess["username"]:
            return SFTPProxy(sess)

    return None


def get_client_by_sid(sid: str) -> Optional[Any]:
    """
    Liefert IMMER ein Objekt zurück, das listdir_attr kann:
      - Paramiko SFTPClient
      - oder SFTPProxy
    """
    # 1) expliziter Getter?
    fn = getattr(R, "get_client_by_sid", None)
    if callable(fn):
        raw = fn(sid)
        if isinstance(raw, dict):
            return _from_dict(raw)
        return raw

    # 2) bekannte Registry-Namen durchsuchen
    for name in ("SFTP_SESSIONS", "SESSIONS", "POOL", "CLIENTS"):
        reg = getattr(R, name, None)
        if isinstance(reg, dict) and sid in reg:
            raw = reg[sid]
            if isinstance(raw, dict):
                return _from_dict(raw)
            return raw

    return None
