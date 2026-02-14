import os
from datetime import timedelta
from dotenv import load_dotenv
if not os.getenv("SF_TICKET_ENC_KEY_B64"):
    load_dotenv(override=False)

class Config:
    SECRET_KEY = os.getenv('SECRET_KEY', 'change-me')
    SQLALCHEMY_DATABASE_URI = os.getenv('SQLALCHEMY_DATABASE_URI')
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'change-me')
    JWT_TOKEN_LOCATION = ["headers", "cookies"]
    JWT_HEADER_NAME = "Authorization"
    JWT_HEADER_TYPE = "Bearer"

    JWT_COOKIE_SECURE = True
    JWT_COOKIE_SAMESITE = "Lax"
    JWT_COOKIE_CSRF_PROTECT = True
    JWT_ACCESS_COOKIE_NAME = "sf_access"
    JWT_REFRESH_COOKIE_NAME = "sf_refresh"
    JWT_ACCESS_TOKEN_EXPIRES = timedelta(hours=1)
    # Chatwoot / Woot Konfiguration
    # Erst WOOT_BASE, sonst WOOT_BASE_URL, sonst Default
    WOOT_BASE = os.getenv("WOOT_BASE") or os.getenv("WOOT_BASE_URL", "https://chat.sitefixer.de")
    WOOT_ACCOUNT_ID = os.getenv("WOOT_ACCOUNT_ID", "1")
    WOOT_API_TOKEN = os.getenv("WOOT_API_TOKEN")
    WOOT_PLATFORM_TOKEN = os.getenv("WOOT_PLATFORM_TOKEN")
    FRONTEND_ORIGIN = os.getenv('FRONTEND_ORIGIN', '')
    
    
    
    # SMTP Konfiguration
    SMTP_HOST = os.getenv("SMTP_HOST", "smtp.ionos.de")
    SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
    SMTP_USER = os.getenv("SMTP_USER", "support@sitefixer.de")
    SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "Lura2025/")
    SMTP_USE_TLS = True
    MAIL_FROM = os.getenv("MAIL_FROM", "support@sitefixer.de")
