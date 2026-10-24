"""US-01 — password hashing (plansTracker-compatible pbkdf2_sha256) and signed session tokens."""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time

SCHEME = "pbkdf2_sha256"
ITERATIONS = 310_000
SESSION_TTL = 30 * 24 * 3600


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def hash_password(password: str, iterations: int = ITERATIONS) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, iterations)
    return f"{SCHEME}${iterations}${_b64(salt)}${_b64(digest)}"


def verify_password(password: str, encoded: str) -> bool:
    """AT-01.1"""
    try:
        scheme, it, salt, digest = encoded.split("$", 3)
        if scheme != SCHEME:
            return False
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), _unb64(salt), int(it))
        return hmac.compare_digest(actual, _unb64(digest))
    except (ValueError, TypeError):
        return False


def _sign(secret: str, payload: str) -> str:
    return _b64(hmac.new(secret.encode(), payload.encode(), hashlib.sha256).digest())


def make_token(secret: str, user_id: str) -> str:
    payload = f"{user_id}.{int(time.time()) + SESSION_TTL}"
    return f"{payload}.{_sign(secret, payload)}"


def read_token(secret: str, token: str) -> str | None:
    try:
        user_id, exp, sig = token.split(".", 2)
        if int(exp) < time.time():
            return None
    except (ValueError, AttributeError):
        return None
    return user_id if hmac.compare_digest(sig, _sign(secret, f"{user_id}.{exp}")) else None
