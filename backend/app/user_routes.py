# backend/app/user_routes.py
from flask import Blueprint, request, jsonify, current_app, g
from flask_jwt_extended import jwt_required, get_jwt_identity

from .decorators import roles_required
from .extensions import db
from .models import User
from argon2 import PasswordHasher
from sqlalchemy.exc import IntegrityError
from app.modules.comms_woot import services as woot_svc

bp = Blueprint('users', __name__)
ph = PasswordHasher()

@bp.get('/me')
@jwt_required()
def me():
    uid = int(get_jwt_identity())       # cast auf int
    u = User.query.get_or_404(uid)
    return jsonify({
        'id': u.id,
        'email': u.email,
        'name': u.name,
        'role': u.role,
        'woot_user_id': u.woot_user_id,   # optional schon mitliefern
    })

@bp.get('/')
@jwt_required()
@roles_required('admin')
def list_users():
    users = User.query.order_by(User.id.desc()).all()
    return jsonify([
        {
            'id': u.id,
            'email': u.email,
            'name': u.name,
            'role': u.role,
            'active': u.active,
            'created_at': u.created_at.isoformat(),
            'woot_user_id': u.woot_user_id,   # NEU
        } for u in users
    ])

@bp.post('/')
@jwt_required()
@roles_required('admin')
def create_user():
    d = request.get_json(force=True) or {}
    try:
        raw_password = d['password']
        email = d['email'].strip().lower()
        name = (d.get('name') or d['email']).strip()
        role = d.get('role', 'agent')

        u = User(
            email=email,
            name=name,
            role=role,
            password_hash=ph.hash(raw_password),
        )
        db.session.add(u)
        db.session.flush()

        # --- Chatwoot-User automatisch anlegen ---
        try:
            woot_id = woot_svc.create_woot_user(
                email=email,
                name=name,
                password=raw_password,
                role=role,
            )
            u.woot_user_id = woot_id
        except Exception as e:
            current_app.logger.exception(
                "Chatwoot-User konnte nicht erstellt werden für %s: %s",
                email, e
            )
            # wenn du möchtest: hier statt weiterzumachen abbrechen:
            db.session.rollback()
            return jsonify({'msg': 'chatwoot-error', 'detail': str(e)}), 502

        db.session.commit()
        return jsonify({'id': u.id, 'woot_user_id': u.woot_user_id}), 201

    except IntegrityError:
        db.session.rollback()
        return jsonify({'msg': 'email-exists'}), 409

@bp.patch('/<int:uid>')
@jwt_required()
@roles_required('admin')
def update_user(uid):
    u = User.query.get_or_404(uid)
    d = request.get_json(force=True) or {}

    if 'name' in d:
        u.name = (d['name'] or u.email).strip()
    if 'role' in d:
        u.role = d['role']
    if 'active' in d:
        u.active = bool(d['active'])
    if 'woot_user_id' in d:                         # NEU
        val = d['woot_user_id']
        u.woot_user_id = int(val) if val not in (None, '', 0) else None
    if d.get('password'):
        u.password_hash = ph.hash(d['password'])

    db.session.commit()
    return jsonify({'ok': True})

@bp.delete('/<int:uid>')
@jwt_required()
@roles_required('admin')
def delete_user(uid):
    u = User.query.get_or_404(uid)
    db.session.delete(u)
    db.session.commit()
    return jsonify({'ok': True})
