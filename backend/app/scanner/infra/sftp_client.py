import paramiko, stat
from ..common.errors import SFTPError, NotFound

class SFTPClient:
    def __init__(self, ssh, sftp):
        self._ssh = ssh
        self._sftp = sftp

    @classmethod
    def connect(cls, host, username, password, port=22, timeout=15):
        try:
            ssh = paramiko.SSHClient()
            ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
            ssh.connect(hostname=host, port=port, username=username, password=password,
                        timeout=timeout, banner_timeout=timeout, auth_timeout=timeout)
            sftp = ssh.open_sftp()
            return cls(ssh, sftp)
        except Exception as e:
            raise SFTPError(str(e))

    def close(self):
        try:
            self._sftp.close()
        finally:
            self._ssh.close()

    def list(self, path="/", limit=500, cursor=None):
        try:
            entries = self._sftp.listdir_attr(path)
        except FileNotFoundError:
            raise NotFound("path")

        off = int(cursor or 0)
        chunk = entries[off:off+limit]
        next_cursor = str(off+limit) if off+limit < len(entries) else None

        out = []
        for a in chunk:
            t = "dir" if stat.S_ISDIR(a.st_mode) else "file"
            out.append({
                "name": a.filename,
                "type": t,
                "size": int(a.st_size),
                "mtime": int(a.st_mtime),
            })
        return {"path": path, "entries": out, "next_cursor": next_cursor}
# in scanner/infra/sftp_client.py, innerhalb class SFTPClient

    def read_file(self, path, max_bytes=5_000_000):
        """Liest bis max_bytes zurück. Liefert bytes (oder raises)."""
        try:
            with self._sftp.open(path, "rb") as fh:
                return fh.read(max_bytes)
        except IOError as e:
            raise SFTPError(str(e))

    def iter_paths(self, root, max_files=10000):
        """Yield relative file paths under root (breitensuche)."""
        stack = [root.rstrip("/")]
        seen = 0
        while stack and seen < max_files:
            cur = stack.pop()
            try:
                entries = self._sftp.listdir_attr(cur)
            except IOError:
                continue
            for a in entries:
                name = a.filename
                path = f"{cur}/{name}" if cur != "/" else f"/{name}"
                if stat.S_ISDIR(a.st_mode):
                    stack.append(path)
                else:
                    yield path
                    seen += 1
                    if seen >= max_files:
                        return
