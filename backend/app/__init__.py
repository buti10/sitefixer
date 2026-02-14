import os
from flask import Flask, jsonify
from argon2 import PasswordHasher

from app.config import Config
from app.extensions import db, migrate, jwt
from flask_cors import CORS
from app.modules.seo_scan.routes import seo_bp
ph = PasswordHasher()


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Defaults für Scanner
    app.config["BUDIBASE_API_KEY"] = os.getenv("BUDIBASE_API_KEY", "")
    app.config.setdefault("SCANNER_BASE", os.environ.get("SCANNER_URL", "http://127.0.0.1:8001"))
    app.config.setdefault("DEFAULT_PATTERNS_QUICK", ["<?php", r"eval\(", r"base64_decode\("])
    app.config.setdefault(
        "DEFAULT_PATTERNS_FULL",
        ["<?php", r"eval\(", r"base64_decode\(", r"assert\(", r"shell_exec\(", r"gzinflate\("],
    )
 
    # Extensions
    db.init_app(app)
    migrate.init_app(app, db)

    # CORS
    frontend_origin = app.config.get("FRONTEND_ORIGIN", "https://scann.sitefixer.de")

    live_origins = [
        frontend_origin,
        "https://vs.sitefixer.de",
        "https://sitefixer.de",
    ]

    CORS(
    	app,
    	resources={
            r"/api/*": {
            	"origins": live_origins,
            	"allow_headers": [
                    "Content-Type",
                    "Authorization",        # 🔴 WICHTIG
                    "X-Requested-With",
                ],
            	"methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
             },
             r"/api/live/*": {
            	 "origins": live_origins,
            	 "allow_headers": [
                     "Content-Type",
                     "Authorization",
                     "X-Requested-With",
                 ],
                 "methods": ["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
             },
        },
        supports_credentials=True,
)

    # JWT
    jwt.init_app(app)

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

    # Blueprints (Imports nur hier, keine doppelten settings-Imports!)
    from app.auth_routes import bp as auth_bp
    from app.user_routes import bp as users_bp
    from app.settings_routes import bp as settings_bp  # unser sf_settings-Blueprint
    from app.wp_routes import bp as wp_bp

    from .core_cache_routes import bp as core_cache_bp
    from .corecache_versions import bp_corecache_versions

    from .patterns_routes import bp as patterns_bp
    from .scanner.routes.sftp_routes import bp as sftp_bp
    from app.malware_routes import bp as malware_bp
    from app.malware_reports import bp as reports_bp, bp2 as reports_legacy_bp
    from app.modules.repair import bp as repair_bp
    from .auth_api import bp_api as auth_api_bp
    from app.modules.cms_core.bp import bp_core_cache
    from app.modules.cms_core.tree_bp import bp_cmscore
    from app.modules.repair.replace_from_core import core_bp, bp_replace
    from app.modules.comms_woot import bp as woot_bp
    from app.modules.cooms_visitors.routes import bp_live
    from app.modules.wp_uploads.routes import bp_wp_uploads
    from app.modules.repair_beta import repair_beta_bp
    from app.modules.repair_beta.routes_wp import bp as repair_beta_wp_bp
    #from app.modules.wp_repair.routes import bp as wp_repair_bp
    from app.modules.wp_repair.wp_repair import bp as wp_repair_bp
    from app.modules.budibase_bridge import bp as budibase_bp
    from app.modules.repair.routes_opslog import bp_opslog
    from app.scanner.routes.sftp_debug import bp as sftp_debug_bp
    from app.modules.tickets_public.routes import bp_public_tickets
    from app.modules.tickets_internal.routes import bp_tickets_internal

    app.register_blueprint(sftp_debug_bp)

    # Blueprint-Registrierung – GENAU EINMAL pro Blueprint
    app.register_blueprint(auth_bp, url_prefix="/api/auth")
    app.register_blueprint(users_bp, url_prefix="/api/users")
    app.register_blueprint(auth_api_bp, url_prefix="/api/auth")

    # Settings-API (liefert /api/settings)
    app.register_blueprint(settings_bp)

    # WordPress / Tickets / Payment
    app.register_blueprint(wp_bp, url_prefix="/api/wp")

    # Legacy Core-Cache
    app.register_blueprint(core_cache_bp, name="core_cache_legacy", url_prefix="/api/core-cache-legacy")
    app.register_blueprint(bp_corecache_versions)

    app.register_blueprint(patterns_bp)
    app.register_blueprint(sftp_bp)
    app.register_blueprint(malware_bp)
    app.register_blueprint(reports_bp)
    app.register_blueprint(reports_legacy_bp)
    app.register_blueprint(bp_opslog)
    #app.register_blueprint(repair_bp, url_prefix="/api/repair")
    app.register_blueprint(repair_bp)
    # Neue Blueprints
    app.register_blueprint(bp_core_cache, name="core_cache_new")  # /api/core-cache
    app.register_blueprint(bp_cmscore, name="cms_core_tree")                          # nur wenn aktiv nötig
    app.register_blueprint(core_bp)
    app.register_blueprint(bp_replace)
    app.register_blueprint(woot_bp)
    app.register_blueprint(bp_live)
    app.register_blueprint(seo_bp, url_prefix="/api/seo")
    app.register_blueprint(bp_wp_uploads)
    app.register_blueprint(repair_beta_bp)
    app.register_blueprint(repair_beta_wp_bp)
    #app.register_blueprint(wp_repair_bp)
    app.register_blueprint(wp_repair_bp)
    app.register_blueprint(budibase_bp)
    app.register_blueprint(bp_public_tickets)
    app.register_blueprint(bp_tickets_internal)

    # Health
    @app.get("/api/health")
    def health():
        return jsonify({"ok": True})

    # DB-Init, Admin-Erzeugung
    with app.app_context():
        from . import models, models_scan, models_repair
        from app.modules.tickets_public import models as models_tickets_public
        admin_email = os.getenv("ADMIN_EMAIL")
        admin_pass = os.getenv("ADMIN_PASSWORD")
        if admin_email and admin_pass:
            from sqlalchemy.exc import IntegrityError
            from .models import User

            if not db.session.query(User.id).filter_by(email=admin_email).first():
                try:
                    u = User(
                        email=admin_email,
                        name="Administrator",
                        password_hash=ph.hash(admin_pass),
                        role="admin",
                    )
                    db.session.add(u)
                    db.session.commit()
                except IntegrityError:
                    db.session.rollback()

    return app
