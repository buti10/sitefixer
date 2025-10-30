from dotenv import load_dotenv
load_dotenv()

import os
from flask import Flask, jsonify
from flask_cors import CORS

# eigene Module
from modules.common.db import init_db, Base
from modules.roles.models import seed_roles_permissions
from modules.auth.routes import bp as auth_bp
from modules.users.routes import bp as users_bp
from modules.roles.routes import bp as roles_bp
from modules.settings.routes import bp as settings_bp

# NEU: Scanner-API
from routes.scans import bp as scans_bp


app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", "dev-secret")

CORS(app, supports_credentials=True,
     resources={r"/*": {"origins": os.getenv("FRONTEND_ORIGIN", "http://localhost:5173")}})

# Blueprints

#app.register_blueprint(auth_bp,     url_prefix="/api/auth")
#app.register_blueprint(users_bp,    url_prefix="/api/users")
#app.register_blueprint(roles_bp,    url_prefix="/api/roles")
#app.register_blueprint(settings_bp, url_prefix="/api/settings")
app.register_blueprint(scans_bp)    # stellt /api/scans & /api/scans/:id bereit

# Health für Docker Compose
@app.get("/api/health")
def api_health():
    return jsonify({"ok": True})
#@app.get("/health")
#def health():
#   return {"status": "ok"}, 200

if __name__ == "__main__":
    engine, session = init_db()
    Base.metadata.create_all(bind=engine)
    seed_roles_permissions(session)
    app.run(host=os.getenv("BACKEND_HOST", "0.0.0.0"),
            port=int(os.getenv("BACKEND_PORT", 5000)), debug=False)
