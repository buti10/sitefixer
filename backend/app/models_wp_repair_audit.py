# app/models_wp_repair_audit.py
from __future__ import annotations

from datetime import datetime
from app.extensions import db


class RepairAction(db.Model):
    __tablename__ = "repair_action"

    id = db.Column(db.Integer, primary_key=True)
    action_id = db.Column(db.String(128), unique=True, nullable=False, index=True)

    ticket_id = db.Column(db.Integer, nullable=False, index=True)
    fix_id = db.Column(db.String(64), nullable=False, index=True)
    status = db.Column(db.String(32), nullable=False, default="created", index=True)

    created_at_utc = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at_utc = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    created_by_user_id = db.Column(db.Integer, nullable=False, index=True)
    created_by_name = db.Column(db.String(128), nullable=True)

    wp_root = db.Column(db.Text, nullable=True)
    project_root = db.Column(db.Text, nullable=True)

    remote_action_dir = db.Column(db.Text, nullable=True)
    remote_meta_path = db.Column(db.Text, nullable=True)
    remote_moved_dir = db.Column(db.Text, nullable=True)

    context_json = db.Column(db.JSON, nullable=True)
    meta_json = db.Column(db.JSON, nullable=True)
    manifest_json = db.Column(db.JSON, nullable=True)
    result_json = db.Column(db.JSON, nullable=True)
    error_json = db.Column(db.JSON, nullable=True)


class RepairActionFile(db.Model):
    __tablename__ = "repair_action_files"

    id = db.Column(db.Integer, primary_key=True)

    # align with RepairAction.action_id length
    action_id = db.Column(db.String(128), nullable=False, index=True)

    op = db.Column(db.String(24), nullable=False)
    src_path = db.Column(db.Text, nullable=False)
    dst_path = db.Column(db.Text, nullable=True)

    sha256_before = db.Column(db.String(64), nullable=True)
    sha256_after = db.Column(db.String(64), nullable=True)

    size_before = db.Column(db.Integer, nullable=True)
    size_after = db.Column(db.Integer, nullable=True)

    ts_utc = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
    payload_json = db.Column(db.JSON, nullable=True)


class RepairFinding(db.Model):
    __tablename__ = "repair_findings"

    id = db.Column(db.BigInteger, primary_key=True)

    # IMPORTANT: action_id must not truncate your generated IDs
    action_id = db.Column(db.String(128), nullable=False, index=True)

    # Keep ticket_id for filtering; default 0 ok, but we will also fill it from action row
    ticket_id = db.Column(db.Integer, nullable=False, default=0, index=True)

    wp_root = db.Column(db.Text, nullable=True)

    # allow None (your code allows path=None)
    path = db.Column(db.Text, nullable=True)

    severity = db.Column(db.String(10), nullable=False, index=True)   # low/medium/high
    kind = db.Column(db.String(64), nullable=False, index=True)

    line = db.Column(db.Integer, nullable=True)
    snippet = db.Column(db.Text, nullable=True)

    sha256 = db.Column(db.String(64), nullable=True, index=True)
    score = db.Column(db.Integer, nullable=True)

    detail_json = db.Column(db.JSON, nullable=True)

    # default helps if any code path forgets to pass ts_utc
    ts_utc = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, index=True)
