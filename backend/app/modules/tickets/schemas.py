from typing import Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, HttpUrl

TicketStatus = Literal["new","queued","scanning","needs_access","fix_ready","fixed","failed"]

class PublicAccessIn(BaseModel):
    sftp_host: Optional[str] = None
    sftp_port: Optional[int] = 22
    sftp_user: Optional[str] = None
    sftp_pass: Optional[str] = None
    wp_admin_user: Optional[str] = None
    wp_admin_pass: Optional[str] = None
    notes: Optional[str] = None

class PublicTicketCreateIn(BaseModel):
    site_url: HttpUrl
    email: Optional[str] = None
    name: Optional[str] = None
    phone: Optional[str] = None
    consent: bool = Field(...)

    access: Optional[PublicAccessIn] = None

class PublicTicketCreateOut(BaseModel):
    public_id: str
    status: TicketStatus

class PublicTicketStatusOut(BaseModel):
    public_id: str
    status: TicketStatus
    last_scan_summary: Optional[Dict[str, Any]] = None
    next_action: Optional[str] = None
