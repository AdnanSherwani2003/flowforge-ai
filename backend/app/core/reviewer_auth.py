"""Single local reviewer; Argon2 password verification and expiring signed sessions."""
import secrets
import time
import threading
from fastapi import Depends, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from pwdlib import PasswordHash
from app.core.config import settings

PASSWORDS = PasswordHash.recommended()
BEARER = HTTPBearer(auto_error=False)
_ATTEMPTS = []
_LOCK = threading.Lock()


def configured():
    return bool(settings.REVIEWER_USERNAME and settings.REVIEWER_PASSWORD_HASH and len(settings.REVIEWER_SESSION_SECRET) >= 32)


def serializer():
    return URLSafeTimedSerializer(settings.REVIEWER_SESSION_SECRET, salt="flowforge-reviewer-v1")


def authenticate(username, password):
    if not configured():
        raise HTTPException(503, "Reviewer authentication is not configured")
    now = time.monotonic()
    with _LOCK:
        _ATTEMPTS[:] = [v for v in _ATTEMPTS if v > now - 60]
        if len(_ATTEMPTS) >= 5:
            raise HTTPException(429, "Too many sign-in attempts; retry in one minute", headers={"Retry-After": "60"})
        _ATTEMPTS.append(now)
    try:
        valid = PASSWORDS.verify(password, settings.REVIEWER_PASSWORD_HASH)
    except Exception:
        valid = False
    if not (valid and secrets.compare_digest(username.encode(), settings.REVIEWER_USERNAME.encode())):
        raise HTTPException(401, "Invalid reviewer credentials")
    with _LOCK:
        _ATTEMPTS.clear()
    return serializer().dumps({"sub": settings.REVIEWER_USERNAME})


def reviewer(credentials: HTTPAuthorizationCredentials | None = Depends(BEARER)):
    if not configured() or credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(401, "Reviewer session required", headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = serializer().loads(credentials.credentials, max_age=settings.REVIEWER_SESSION_SECONDS)
        if payload != {"sub": settings.REVIEWER_USERNAME}:
            raise BadSignature("Invalid subject")
    except (BadSignature, SignatureExpired):
        raise HTTPException(401, "Reviewer session expired or invalid") from None
    return settings.REVIEWER_USERNAME
