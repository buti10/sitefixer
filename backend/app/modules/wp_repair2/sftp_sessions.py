from __future__ import annotations

from typing import Tuple
import paramiko

from .session_store import store
from .sftp import SftpCreds, connect_sftp


def get_sftp_client(session_id: str) -> Tuple[paramiko.SSHClient, paramiko.SFTPClient]:
    s = store.get(session_id)
    if not s:
        raise ValueError("SFTP Session ungültig oder abgelaufen.")

    creds = SftpCreds(
        host=s.data["host"],
        username=s.data["user"],
        password=s.data["pass"],
        port=int(s.data.get("port", 22)),
    )
    return connect_sftp(creds)
