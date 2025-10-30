from passlib.context import CryptContext
import jwt, os, datetime as dt

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
JWT_SECRET = os.getenv("JWT_SECRET", "dev-jwt")
ACCESS_MIN = int(os.getenv("ACCESS_TOKEN_MIN", 20))
REFRESH_DAYS = int(os.getenv("REFRESH_TOKEN_DAYS", 7))

def hash_password(p): return pwd.hash(p)
def verify_password(p, h): return pwd.verify(p, h)

def _base_payload(user):
    # toleriert fehlende role/token_version
    role_name = None
    r = getattr(user, "role", None)
    if r is not None:
        role_name = getattr(r, "name", None)
    tv = getattr(user, "token_version", 1)
    return {
        "sub": str(user.id),
        "email": user.email,
        "role": role_name,
        "tv": tv,
    }

def create_access_token(user):
    now = dt.datetime.utcnow()
    payload = {
        **_base_payload(user),
        "type": "access",
        "iat": now,
        "exp": now + dt.timedelta(minutes=ACCESS_MIN),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def create_refresh_token(user):
    now = dt.datetime.utcnow()
    payload = {
        **_base_payload(user),
        "type": "refresh",
        "iat": now,
        "exp": now + dt.timedelta(days=REFRESH_DAYS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm="HS256")

def decode_token(token):
    return jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
