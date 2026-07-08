"""
JWT token management — access + refresh tokens.
"""
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
from config import settings

ALGORITHM       = "HS256"
ACCESS_EXPIRE   = timedelta(hours=24)
REFRESH_EXPIRE  = timedelta(days=30)


def create_access_token(user_id: int, phone: str) -> str:
    payload = {
        "sub":   str(user_id),
        "phone": phone,
        "type":  "access",
        "exp":   datetime.utcnow() + ACCESS_EXPIRE,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def create_refresh_token(user_id: int) -> str:
    payload = {
        "sub":  str(user_id),
        "type": "refresh",
        "exp":  datetime.utcnow() + REFRESH_EXPIRE,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(token, settings.SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        return None
