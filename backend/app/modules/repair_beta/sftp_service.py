import socket
import paramiko
from contextlib import contextmanager

@contextmanager
def sftp_connect(host: str, user: str, password: str, port: int = 22, timeout: int = 12):
    try:
        transport = paramiko.Transport((host, port))
        transport.banner_timeout = timeout
        transport.connect(username=user, password=password)
        sftp = paramiko.SFTPClient.from_transport(transport)
        try:
            yield sftp
        finally:
            try: sftp.close()
            except: pass
            transport.close()
    except socket.gaierror as e:
        raise RuntimeError(f"DNS/Host-Auflösung fehlgeschlagen für '{host}': {e}") from e

