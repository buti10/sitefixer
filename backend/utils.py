from passlib.hash import argon2

def hash_password(pw: str) -> str:
    return argon2.hash(pw)

def verify_password(pw: str, hashed: str) -> bool:
    return argon2.verify(pw, hashed)