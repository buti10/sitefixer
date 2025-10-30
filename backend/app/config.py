import os
from dotenv import load_dotenv
load_dotenv()  # liest /var/www/sitefixer/backend/.env ein

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'change-me')
    SQLALCHEMY_DATABASE_URI = os.getenv('SQLALCHEMY_DATABASE_URI')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'change-me')
    JWT_TOKEN_LOCATION = ["cookies"]
    JWT_COOKIE_SECURE = True
    JWT_COOKIE_SAMESITE = "Lax"
    JWT_COOKIE_CSRF_PROTECT = True
    JWT_ACCESS_COOKIE_NAME = "sf_access"
    JWT_REFRESH_COOKIE_NAME = "sf_refresh"

    FRONTEND_ORIGIN = os.getenv('FRONTEND_ORIGIN', '')
