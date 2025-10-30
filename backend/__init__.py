import os
from flask import Flask, jsonify
from .config import Config
from .extensions import db, migrate, jwt, CORS
from argon2 import PasswordHasher

ph = PasswordHasher()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Defaults für Scanner
    app.config.setdefault("SCANNER_BASE", os.environ.get("SCANNER_URL", "http://127.0.0.1:8001"))
    app.config.setdefault("DEFAULT_PATTERNS_QUICK", ["<?php", r"eval\(", r"base64_decode\("])
    app.config.setdefault("DEFAULT_PATTERNS_FULL", ["<?php", r"eval\(", r"base64_decode\(", r"assert\(", r"shell_exec\(", r"gzinflate\("])

    # Extensions
    db.init_app(app)
    migrate.init_app(app, db)

    origin = app.config.get("FRONTEND_ORIGIN")
    CORS(app, resources={r"/api/*": {"origins": origin}}, supports_credentials=True)
    jwt.init_app(app)

    # JWT callbacks
    @jwt.additional_claims_loader
    def add_claims(identity):
        from .models import User
        u = db.session.get(User, int(identity)) if identity else None
        return {"role": (u.role if u else "viewer"), "email": (u.email if u else None)}

    @jwt.token_in_blocklist_loader
    def check_if_revoked(jwt_header, jwt_payload):
        from .models import RefreshBlocklist
        if jwt_payload.get("type") == "refresh":
            jti = jwt_payload.get("jti")
            return db.session.query(RefreshBlocklist.id).filter_by(jti=jti).first() is not None
        return False

    # Blueprints (Imports)
    from app.auth_routes import bp as auth_bp
    from app.user_routes import bp as users_bp
    from app.settings_routes import bp as settings_bp
    from app.wp_routes import bp as wp_bp

    # Legacy Core-Cache Upload (Settings-Seite)
    from .core_cache_routes import bp as core_cache_bp
    from .corecache_versions import bp_corecache_versions

    from .patterns_routes import bp as patterns_bp
    from .scanner.routes.sftp_routes import bp as sftp_bp
    from app.malware_routes import bp as malware_bp
    from app.malware_reports import bp as reports_bp, bp2 as reports_legacy_bp
    from app.modules.repair import bp as repair_bp
    from modules.comms_chat.routes import bp as bp_comms_chat

    # Neue CMS-Core Endpunkte
    # /api/core-cache   -> app.modules.cms_core.bp: bp_core_cache
    # /api/cms-core     -> app.modules.cms_core.tree_bp: bp_cmscore
    from app.modules.cms_core.bp import bp_core_cache
    from app.modules.cms_core.tree_bp import bp_cmscore
    from app.modules.repair.replace_from_core import core_bp
    # Replace-Endpoint
    from app.modules.repair.replace_from_core import bp_replace
    
    

    # Blueprints (Registrierung)
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(users_bp, url_prefix="/api/users")
    app.register_blueprint(settings_bp, url_prefix="/api/settings")
    app.register_blueprint(wp_bp, url_prefix="/api/wp")

    # Legacy unter eigenem Prefix und Namen, damit kein Namenskonflikt
    app.register_blueprint(core_cache_bp, name="core_cache_legacy", url_prefix="/api/core-cache-legacy")
    app.register_blueprint(bp_corecache_versions)
    
    app.register_blueprint(patterns_bp)
    app.register_blueprint(sftp_bp)
    app.register_blueprint(malware_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(reports_legacy_bp)
    app.register_blueprint(bp_comms_chat, url_prefix="/api/comms/chat")
    app.register_blueprint(repair_bp, url_prefix="/api/repair")

    # Neue Blueprints. Die Objekte bringen ihre eigenen url_prefix mit.
    # Falls dein bp_core_cache intern bereits url_prefix="/api/core-cache" setzt, KEIN weiteres url_prefix hier angeben.
    app.register_blueprint(bp_core_cache, name="core_cache_new")  # /api/core-cache
    #app.register_blueprint(bp_cmscore)                            # /api/cms-core
    app.register_blueprint(core_bp)
    app.register_blueprint(bp_replace)                           # /api/repair/replace-from-core o.ä.
    
    # Health
    @app.get("/api/health")
    def health():
        return jsonify({"ok": True})

    # DB-Init, Admin-Erzeugung
    with app.app_context():
        from . import models, models_scan, models_repair  # registriert Tabellen
        admin_email = os.getenv("ADMIN_EMAIL")
        admin_pass = os.getenv("ADMIN_PASSWORD")
        if admin_email and admin_pass:
            from sqlalchemy.exc import IntegrityError
            from .models import User
            if not db.session.query(User.id).filter_by(email=admin_email).first():
                try:
                    u = User(email=admin_email, name="Administrator",
                             password_hash=ph.hash(admin_pass), role="admin")
                    db.session.add(u)
                    db.session.commit()
                except IntegrityError:
                    db.session.rollback()

    return app
