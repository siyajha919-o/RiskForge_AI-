"""
Authentication for the RiskForge API.

Users live in outputs/users.json (created on first run from env vars) rather
than a database — the engine has no persistence layer of its own and adding one
for a handful of accounts would be disproportionate. Passwords are stored as
PBKDF2-SHA256 hashes; the plaintext is never written or logged.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import base64
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, Optional

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .models import Role, UserOut

BASE_DIR = Path(__file__).resolve().parent.parent
USERS_PATH = BASE_DIR / "outputs" / "users.json"

# A generated secret means tokens are invalidated on restart. That is a safe
# default; set JWT_SECRET to keep sessions across restarts.
JWT_SECRET = os.environ.get("JWT_SECRET") or secrets.token_urlsafe(64)
JWT_ALGORITHM = "HS256"
TOKEN_MINUTES = int(os.environ.get("JWT_EXPIRATION_MINUTES", "60"))
REMEMBER_ME_MINUTES = int(os.environ.get("JWT_REMEMBER_ME_MINUTES", str(60 * 24 * 14)))

_PBKDF2_ROUNDS = 240_000
bearer = HTTPBearer(auto_error=False)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ROUNDS)
    return f"pbkdf2_sha256${_PBKDF2_ROUNDS}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        algorithm, rounds, salt_b64, digest_b64 = stored.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        expected = base64.b64decode(digest_b64)
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), base64.b64decode(salt_b64), int(rounds)
        )
        return hmac.compare_digest(expected, actual)
    except (ValueError, TypeError):
        return False


def _read_users() -> Dict[str, Dict]:
    if not USERS_PATH.exists():
        return {}
    try:
        with open(USERS_PATH) as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _write_users(users: Dict[str, Dict]) -> None:
    USERS_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(USERS_PATH, "w") as f:
        json.dump(users, f, indent=2)
    try:
        USERS_PATH.chmod(0o600)
    except OSError:
        pass


def bootstrap_admin() -> Optional[str]:
    """
    Ensures an admin account exists. Returns a message describing what happened
    so start-up logging can be explicit about it.
    """
    users = _read_users()
    if any(u.get("role") == Role.ADMIN.value for u in users.values()):
        return None

    email = os.environ.get("ADMIN_BOOTSTRAP_EMAIL", "").strip().lower()
    password = os.environ.get("ADMIN_BOOTSTRAP_PASSWORD", "")

    if not email or not password:
        return ("No admin account exists. Set ADMIN_BOOTSTRAP_EMAIL and "
                "ADMIN_BOOTSTRAP_PASSWORD and restart to create one.")
    if len(password) < 12:
        return "ADMIN_BOOTSTRAP_PASSWORD must be at least 12 characters — admin not created."

    users[email] = {
        "email": email,
        "name": os.environ.get("ADMIN_BOOTSTRAP_NAME", "Administrator"),
        "role": Role.ADMIN.value,
        "password_hash": hash_password(password),
    }
    _write_users(users)
    return f"Created admin account: {email}"


def authenticate(email: str, password: str) -> Optional[UserOut]:
    user = _read_users().get(email.strip().lower())
    if not user or not verify_password(password, user.get("password_hash", "")):
        return None
    return UserOut(email=user["email"], name=user.get("name", user["email"]), role=user["role"])


def create_token(user: UserOut, remember_me: bool = False) -> tuple[str, int]:
    minutes = REMEMBER_ME_MINUTES if remember_me else TOKEN_MINUTES
    payload = {
        "sub": user.email,
        "name": user.name,
        "role": user.role.value,
        "iat": datetime.now(timezone.utc),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=minutes),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM), minutes


def current_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer),
) -> UserOut:
    if creds is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = jwt.decode(creds.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Session expired. Please sign in again.")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid token.")

    return UserOut(email=payload["sub"], name=payload.get("name", ""), role=payload.get("role", Role.VIEWER))


def require_roles(*roles: Role):
    """Route guard for actions that shouldn't be open to every signed-in user."""
    allowed = {r.value for r in roles}

    def guard(user: UserOut = Depends(current_user)) -> UserOut:
        if user.role.value not in allowed:
            raise HTTPException(status_code=403, detail="Your role does not permit this action.")
        return user

    return guard
