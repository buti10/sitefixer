# scanner/services/sftp_service.py
from ..infra.storage import Sessions
from ..infra.sftp_client import SFTPClient

def create_session(host, username, password) -> str:
    # Credentials einmal validieren
    c = SFTPClient.connect(host, username, password)
    c.close()
    return Sessions.put(host, username, password)

def list_dir(sid, path, limit, cursor):
    creds = Sessions.get(sid)
    c = SFTPClient.connect(creds["host"], creds["username"], creds["password"])
    try:
        return c.list(path, limit=limit, cursor=cursor)
    finally:
        c.close()

def close_session(sid):
    Sessions.pop(sid)
    return True
