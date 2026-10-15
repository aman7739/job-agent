"""Authentication and session management for single-user dashboard."""

from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import os
import time
from collections import defaultdict
from typing import Dict, List, Optional, Tuple
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import HTTPException, Request, status
from fastapi.responses import RedirectResponse

logger = logging.getLogger(__name__)

# Argon2 password hasher
_ph = PasswordHasher(
    time_cost=3,
    memory_cost=65536,
    parallelism=4,
    hash_len=32,
    salt_len=16,
)

# Secret key for signing session cookies
SECRET_KEY = os.getenv("SESSION_SECRET", os.getenv("SECRET_KEY", "default-job-digest-secret-key-change-in-prod"))

# Rate limiter tracker for login attempts: ip -> list of attempt timestamps
_login_attempts: Dict[str, List[float]] = defaultdict(list)
MAX_LOGIN_ATTEMPTS = 5
RATE_LIMIT_WINDOW_SECONDS = 300  # 5 minutes


def hash_password(plain_password: str) -> str:
    """Hash password using Argon2id."""
    return _ph.hash(plain_password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify plain password against Argon2 hash."""
    try:
        return _ph.verify(hashed_password, plain_password)
    except (VerifyMismatchError, Exception):
        return False


def get_configured_password_hash() -> str:
    """
    Get configured password hash.
    Checks DASHBOARD_PASSWORD_HASH first.
    If not set, hashes DASHBOARD_PASSWORD (defaults to 'changeme123' for dev).
    """
    existing_hash = os.getenv("DASHBOARD_PASSWORD_HASH")
    if existing_hash and existing_hash.strip():
        return existing_hash.strip()

    plain = os.getenv("DASHBOARD_PASSWORD", "changeme123")
    return hash_password(plain)


def check_rate_limit(client_ip: str) -> bool:
    """
    Check if client IP has exceeded login attempt threshold.
    Returns True if allowed, False if rate limited.
    """
    now = time.time()
    cutoff = now - RATE_LIMIT_WINDOW_SECONDS
    # Clean up expired timestamps
    _login_attempts[client_ip] = [t for t in _login_attempts[client_ip] if t > cutoff]
    return len(_login_attempts[client_ip]) < MAX_LOGIN_ATTEMPTS


def record_failed_attempt(client_ip: str) -> None:
    """Record a failed login attempt."""
    _login_attempts[client_ip].append(time.time())


def reset_rate_limit(client_ip: str) -> None:
    """Reset failed attempts for client IP on successful login."""
    _login_attempts.pop(client_ip, None)


def create_session_token(user_identifier: str = "admin", max_age_seconds: int = 604800) -> str:
    """
    Create a tamper-proof signed session token:
    payload = base64(user_identifier:timestamp:signature)
    """
    now = int(time.time())
    expires_at = now + max_age_seconds
    raw_payload = f"{user_identifier}:{expires_at}"
    sig = hmac.new(
        SECRET_KEY.encode("utf-8"),
        raw_payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    token_str = f"{raw_payload}:{sig}"
    return base64.urlsafe_b64encode(token_str.encode("utf-8")).decode("utf-8")


def verify_session_token(token: str) -> Optional[str]:
    """
    Verify HMAC signature and expiration of session token.
    Returns user_identifier if valid, None if invalid or expired.
    """
    try:
        decoded = base64.urlsafe_b64decode(token.encode("utf-8")).decode("utf-8")
        parts = decoded.split(":")
        if len(parts) != 3:
            return None

        user_id, expires_at_str, signature = parts
        expires_at = int(expires_at_str)

        if time.time() > expires_at:
            return None  # Expired

        expected_raw = f"{user_id}:{expires_at_str}"
        expected_sig = hmac.new(
            SECRET_KEY.encode("utf-8"),
            expected_raw.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        if hmac.compare_digest(signature, expected_sig):
            return user_id
    except Exception:
        pass
    return None


def get_current_user_from_request(request: Request) -> Optional[str]:
    """Extract and verify user session from cookie."""
    token = request.cookies.get("session_token")
    if not token:
        return None
    return verify_session_token(token)


async def require_auth(request: Request) -> str:
    """
    FastAPI dependency for protected routes.
    If session is missing or invalid, raises 401 or redirects to /login.
    """
    user = get_current_user_from_request(request)
    if not user:
        if request.headers.get("accept", "").startswith("application/json"):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Authentication required",
            )
        # For browser navigation, redirect to login with next path
        next_path = request.url.path
        raise HTTPException(
            status_code=status.HTTP_307_TEMPORARY_REDIRECT,
            headers={"Location": f"/login?next={next_path}"},
        )
    return user
