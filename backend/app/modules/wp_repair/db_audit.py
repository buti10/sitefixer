# app/modules/wp_repair/db_audit.py
from __future__ import annotations

from datetime import datetime
from typing import Optional, Iterable, List, Tuple

from flask import current_app
from app.extensions import db
from app.models_wp_repair_audit import RepairFinding, RepairAction, RepairActionFile


# -----------------------------
# Helpers
# -----------------------------
def _utcnow():
    return datetime.utcnow()


def _log_warn(msg: str, *args):
    try:
        current_app.logger.warning(msg, *args)
    except Exception:
        pass


def _safe_commit():
    try:
        db.session.commit()
        return True
    except Exception as e:
        try:
            db.session.rollback()
        except Exception:
            pass
        _log_warn("DB commit failed: %s", e)
        return False


def _safe_rollback():
    try:
        db.session.rollback()
    except Exception:
        pass


def _get_action_ctx(action_id: str) -> Tuple[int, Optional[str]]:
    """
    Best-effort: returns (ticket_id, wp_root) for an action.
    Never raises (DB failures are swallowed).
    """
    try:
        row = RepairAction.query.filter_by(action_id=action_id).first()
        if not row:
            return 0, None
        return int(row.ticket_id or 0), row.wp_root
    except Exception:
        return 0, None


def get_action_ctx(action_id: str) -> Tuple[int, Optional[str]]:
    """Public wrapper for best-effort (ticket_id, wp_root) lookup.

    Never raises; returns (0, None) on any failure.
    """
    return _get_action_ctx(action_id)


# -----------------------------
# Actions
# -----------------------------
def create_action_row(
    *,
    action_id: str,
    ticket_id: int,
    fix_id: str,
    created_by_user_id: int,
    created_by_name: str | None = None,
    wp_root: str | None = None,
    project_root: str | None = None,
    remote_action_dir: str | None = None,
    remote_meta_path: str | None = None,
    remote_moved_dir: str | None = None,
    context_json: dict | None = None,
    meta_json: dict | None = None,
    manifest_json: dict | None = None,
):
    row = RepairAction(
        action_id=action_id,
        ticket_id=ticket_id,
        fix_id=fix_id,
        status="created",
        created_at_utc=_utcnow(),
        updated_at_utc=_utcnow(),
        created_by_user_id=created_by_user_id,
        created_by_name=created_by_name,
        wp_root=wp_root,
        project_root=project_root,
        remote_action_dir=remote_action_dir,
        remote_meta_path=remote_meta_path,
        remote_moved_dir=remote_moved_dir,
        context_json=context_json or {},
        meta_json=meta_json,
        manifest_json=manifest_json,
    )
    db.session.add(row)
    _safe_commit()
    return row


def set_action_status(
    action_id: str,
    status: str,
    *,
    result_json: dict | None = None,
    error_json: dict | None = None,
    meta_json: dict | None = None,
):
    row = RepairAction.query.filter_by(action_id=action_id).first()
    if not row:
        _log_warn("repair action not found in DB: %s", action_id)
        return None

    row.status = status
    row.updated_at_utc = _utcnow()

    if result_json is not None:
        row.result_json = result_json
    if error_json is not None:
        row.error_json = error_json
    if meta_json is not None:
        row.meta_json = meta_json

    _safe_commit()
    return row


# -----------------------------
# File operations
# -----------------------------
def add_file_op(
    action_id: str,
    op: str,
    src_path: str,
    dst_path: str | None = None,
    *,
    payload_json: dict | None = None,
):
    f = RepairActionFile(
        action_id=action_id,
        op=op,
        src_path=src_path,
        dst_path=dst_path,
        ts_utc=_utcnow(),
        payload_json=payload_json or {},
    )
    db.session.add(f)
    _safe_commit()
    return f


# -----------------------------
# Findings (performance-critical)
# -----------------------------
def add_finding(
    action_id: str,
    *,
    path: str | None,
    severity: str,
    kind: str,
    detail_json: dict | None = None,
    commit: bool = True,
):
    """
    Backwards-compatible.
    IMPORTANT: commit=False allows caller to batch commits.
    Auto-fills ticket_id/wp_root from RepairAction (best-effort).
    """
    ticket_id, wp_root = _get_action_ctx(action_id)

    r = RepairFinding(
        action_id=action_id,
        ticket_id=ticket_id,
        wp_root=wp_root,
        ts_utc=_utcnow(),
        path=path,
        severity=severity,
        kind=kind,
        detail_json=detail_json or {},
    )
    db.session.add(r)
    if commit:
        _safe_commit()
    return r


def add_findings_bulk(
    action_id: str,
    items: Iterable[dict],
    *,
    commit: bool = True,
    use_bulk: bool = True,
) -> int:
    """
    High-performance insert for many findings.
    items: iterable of dicts with keys: path, severity, kind, detail_json
    Auto-fills ticket_id/wp_root from RepairAction (best-effort).
    """
    rows: List[RepairFinding] = []
    ts = _utcnow()
    ticket_id, wp_root = _get_action_ctx(action_id)

    for it in items:
        rows.append(
            RepairFinding(
                action_id=action_id,
                ticket_id=ticket_id,
                wp_root=wp_root,
                ts_utc=ts,
                path=it.get("path"),
                severity=it["severity"],
                kind=it["kind"],
                detail_json=it.get("detail_json") or {},
            )
        )

    if not rows:
        return 0

    try:
        if use_bulk:
            db.session.bulk_save_objects(rows)
        else:
            db.session.add_all(rows)
        if commit:
            _safe_commit()
        return len(rows)
    except Exception as e:
        _safe_rollback()
        _log_warn("add_findings_bulk failed: %s", e)
        return 0


def flush_findings(commit: bool = True) -> bool:
    """
    Call this from scan loops every N findings to keep DB fast.
    """
    if commit:
        return _safe_commit()
    try:
        db.session.flush()
        return True
    except Exception as e:
        _safe_rollback()
        _log_warn("DB flush failed: %s", e)
        return False


def delete_findings_for_action(action_id: str) -> int:
    q = RepairFinding.query.filter_by(action_id=action_id)
    n = q.count()
    q.delete(synchronize_session=False)
    _safe_commit()
    return n
