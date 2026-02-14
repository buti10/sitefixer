from __future__ import annotations

import socket
import paramiko


def sftp_connect(
    host: str,
    port: int,
    username: str,
    password: str,
    *,
    connect_timeout: int = 12,
    banner_timeout: int = 12,
    auth_timeout: int = 12,
    op_timeout: int = 20,
    keepalive: int = 15,
) -> paramiko.SSHClient:
    """
    Establish a robust SSH/SFTP connection with real operation timeouts.

    - connect_timeout: TCP connect timeout
    - banner_timeout/auth_timeout: SSH negotiation
    - op_timeout: timeout for SFTP operations (read/list/stat)
    - keepalive: seconds; prevents idle disconnects
    """

    # --- TCP socket with real timeout ---
    sock = socket.create_connection((host, int(port)), timeout=float(connect_timeout))
    sock.settimeout(float(op_timeout))

    transport = paramiko.Transport(sock)
    transport.banner_timeout = float(banner_timeout)
    transport.auth_timeout = float(auth_timeout)

    transport.connect(username=username, password=password)

    if keepalive and keepalive > 0:
        try:
            transport.set_keepalive(int(keepalive))
        except Exception:
            pass

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    # Attach existing transport (important!)
    client._transport = transport  # type: ignore[attr-defined]

    return client
