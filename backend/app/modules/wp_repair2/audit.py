# /var/www/sitefixer/backend/app/modules/wp_repair/audit.py
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, Dict, Optional


DEFAULT_AUDIT_DIR = os.getenv("WP_REPAIR_AUDIT_DIR", "/var/www/sitefixer/core-cache/repair-audit")
DEFAULT_AUDIT_FILE = os.getenv("WP_REPAIR_AUDIT_FILE", "wp-repair-audit.jsonl")


def _safe_realpath(p: str) -> Path:
    return Path(p).expanduser().resolve(strict=False)


def _ensure_dir(p: Path) -> None:
    p.mkdir(parents=True, exist_ok=True)


def _now_ts() -> int:
    return int(time.time())


@dataclass
class AuditEvent:
    ts: int
    actor: str  # user id / username / system
    root_path: str
    action_id: str
    status: str  # "started"|"success"|"failed"
    message: str
    params: Dict[str, Any]
    result: Optional[Dict[str, Any]] = None
    backup: Optional[Dict[str, Any]] = None
    meta: Optional[Dict[str, Any]] = None


def _audit_path() -> Path:
    base = _safe_realpath(DEFAULT_AUDIT_DIR)
    _ensure_dir(base)
    return base / DEFAULT_AUDIT_FILE


def write_event(event: AuditEvent) -> Dict[str, Any]:
    """
    Append-only JSONL.
    Returns {ok, path, bytes_written}
    """
    path = _audit_path()
    line = json.dumps(asdict(event), ensure_ascii=False)
    try:
        with path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
        return {"ok": True, "path": str(path), "bytes_written": len(line) + 1}
    except Exception as e:
        return {"ok": False, "path": str(path), "error": f"{type(e).__name__}: {e}"}


def audit_started(
    *,
    actor: str,
    root_path: str,
    action_id: str,
    params: Dict[str, Any],
    message: str = "Action started",
    backup: Optional[Dict[str, Any]] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return write_event(
        AuditEvent(
            ts=_now_ts(),
            actor=actor or "system",
            root_path=root_path,
            action_id=action_id,
            status="started",
            message=message,
            params=params or {},
            backup=backup,
            meta=meta,
        )
    )


def audit_success(
    *,
    actor: str,
    root_path: str,
    action_id: str,
    params: Dict[str, Any],
    result: Optional[Dict[str, Any]] = None,
    message: str = "Action success",
    backup: Optional[Dict[str, Any]] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return write_event(
        AuditEvent(
            ts=_now_ts(),
            actor=actor or "system",
            root_path=root_path,
            action_id=action_id,
            status="success",
            message=message,
            params=params or {},
            result=result,
            backup=backup,
            meta=meta,
        )
    )


def audit_failed(
    *,
    actor: str,
    root_path: str,
    action_id: str,
    params: Dict[str, Any],
    error: str,
    result: Optional[Dict[str, Any]] = None,
    message: str = "Action failed",
    backup: Optional[Dict[str, Any]] = None,
    meta: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    return write_event(
        AuditEvent(
            ts=_now_ts(),
            actor=actor or "system",
            root_path=root_path,
            action_id=action_id,
            status="failed",
            message=f"{message}: {error}",
            params=params or {},
            result=result,
            backup=backup,
            meta=meta,
        )
    )

def read_audit_events(
    *,
    limit: int = 50,
    root_path: str | None = None,
    ticket_id: int | None = None,
) -> list[dict[str, Any]]:
    path = _audit_path()
    if not path.exists():
        return []

    items: list[dict[str, Any]] = []
    try:
        # read tail (simple): file is usually small. If it grows, tail it later.
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    obj = json.loads(line)
                except Exception:
                    continue

                if root_path and obj.get("root_path") != root_path:
                    continue

                # ticket_id liegt bei dir aktuell nicht in AuditEvent.
                # Wir filtern nur, wenn du es in meta/params ablegst.
                if ticket_id is not None:
                    meta = obj.get("meta") or {}
                    params = obj.get("params") or {}
                    tid = meta.get("ticket_id") or params.get("ticket_id")
                    if tid is None or int(tid) != int(ticket_id):
                        continue

                items.append(obj)

        # newest first
        items = items[-limit:][::-1]
        return items
    except Exception:
        return []
