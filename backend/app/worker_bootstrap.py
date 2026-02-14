from flask import Flask
from app.config import Config
from app.extensions import db

def create_worker_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    db.init_app(app)
    return app
