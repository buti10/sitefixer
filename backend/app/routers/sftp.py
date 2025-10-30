# app/routers/sftp.py
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List
import paramiko
import os

router = APIRouter(prefix="/sftp", tags=["sftp"])

class SFTPConn(BaseModel):
    host: str
    user: str
    password: str | None = None
    port: int = 22

class SFTPListRequest(BaseModel):
    conn: SFTPConn
    path: str = Field("/", description="Ausgangspunkt")

class SFTPItem(BaseModel):
    name: str
    path: str
    is_dir: bool

class SFTPListResponse(BaseModel):
    cwd: str
    items: List[SFTPItem]

def _norm_path(p: str) -> str:
    # Sicherheit: kein relatives Klettern
    if not p:
        return "/"
    p = os.path.normpath(p.replace("\\", "/"))
    if not p.startswith("/"):
        p = "/" + p
    return p

@router.post("/list", response_model=SFTPListResponse)
def sftp_list(payload: SFTPListRequest):
    host = payload.conn.host.strip()
    user = payload.conn.user.strip()
    port = payload.conn.port or 22
    pwd  = payload.conn.password or ""
    path = _norm_path(payload.path)

    if not host or not user:
        raise HTTPException(400, "host und user sind erforderlich")

    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())

    try:
        ssh.connect(
            hostname=host,
            port=port,
            username=user,
            password=pwd,
            look_for_keys=False,
            allow_agent=False,
            timeout=10,
            banner_timeout=10,
            auth_timeout=10,
        )
        sftp = ssh.open_sftp()

        # chdir() wirft bei fehlendem Pfad -> fange ab, falle auf "/" zurück
        try:
            sftp.chdir(path)
        except IOError:
            sftp.chdir("/")
            path = "/"

        # Liste erstellen
        items: list[SFTPItem] = []
        for name in sftp.listdir():
            try:
                st = sftp.stat(os.path.join(path, name))
                is_dir = paramiko.S_ISDIR(st.st_mode)
            except IOError:
                # z.B. broken symlink: zeige als Datei
                is_dir = False
            items.append(SFTPItem(
                name=name,
                path=_norm_path(os.path.join(path, name)),
                is_dir=is_dir,
            ))

        # Verzeichnisse zuerst, case-insensitive
        items.sort(key=lambda i: (not i.is_dir, i.name.lower()))
        return SFTPListResponse(cwd=path, items=items)

    except paramiko.AuthenticationException:
        raise HTTPException(401, "SFTP: Authentication failed")
    except Exception as e:
        raise HTTPException(502, f"SFTP: {e}")
    finally:
        try:
            ssh.close()
        except Exception:
            pass
