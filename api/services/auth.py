"""JWT auth service.

Single source of truth for password hashing, token mint/verify, and the
FastAPI dependency that gates protected routes.

Why bcrypt + PyJWT (not passlib + python-jose)?
    bcrypt 5.x ships its own wheels on Windows, no compiler dance. PyJWT
    is the smaller dependency surface and is already in many deployments.
    Passlib's "passlib[bcrypt]" still works but its bcrypt detection broke
    on bcrypt 4.x and the friction wasn't worth keeping.

Why a fallback SECRET_KEY?
    The dev key lets contributors run the full stack without setting an env
    var. In production, JWT_SECRET MUST be set to a real secret — the
    fallback prints a one-time warning at import time so the omission is
    visible in CI logs.
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime, timedelta
from typing import Literal

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel

Role = Literal["admin", "ops", "analyst", "viewer"]

_DEV_SECRET = "pfa-dev-only-not-for-prod-2026"
SECRET_KEY = os.getenv("JWT_SECRET", _DEV_SECRET)
ALGORITHM = "HS256"
ACCESS_TOKEN_TTL_MIN = int(os.getenv("JWT_TTL_MIN", "480"))  # 8h

if SECRET_KEY == _DEV_SECRET:
    print(
        "[auth] WARNING: JWT_SECRET is using the dev fallback. "
        "Set JWT_SECRET in production.",
        file=sys.stderr,
    )

# tokenUrl is informational — it tells OpenAPI where the login endpoint lives.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)


# ── Password hashing ────────────────────────────────────────────────────

def hash_password(plain: str) -> str:
    """Hash a password with bcrypt. Salt is embedded in the returned string."""
    if not plain:
        raise ValueError("password must be non-empty")
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(plain.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    """Constant-time bcrypt verify. Returns False on any error (don't leak why)."""
    if not plain or not hashed:
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ── Token mint / verify ─────────────────────────────────────────────────

class TokenPayload(BaseModel):
    sub: str           # user id as string (JWT convention)
    email: str
    role: Role
    exp: int           # unix seconds


def mint_access_token(*, user_id: int, email: str, role: Role) -> str:
    """Create a signed JWT for the given user. Returns the encoded string."""
    expire = datetime.now(UTC) + timedelta(minutes=ACCESS_TOKEN_TTL_MIN)
    claims = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "exp": int(expire.timestamp()),
    }
    return jwt.encode(claims, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> TokenPayload:
    """Decode + validate a JWT. Raises HTTPException(401) on any failure."""
    try:
        raw = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    except jwt.InvalidTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from None
    try:
        return TokenPayload(**raw)
    except Exception as exc:  # pydantic ValidationError or KeyError
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Malformed token",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


# ── FastAPI dependencies ────────────────────────────────────────────────

class CurrentUser(BaseModel):
    id: int
    email: str
    role: Role


def get_current_user(token: str | None = Depends(oauth2_scheme)) -> CurrentUser:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(token)
    return CurrentUser(id=int(payload.sub), email=payload.email, role=payload.role)


# Role hierarchy: a higher-tier role satisfies a lower-tier requirement.
# Admin can do anything; ops can do analyst/viewer work; etc.
_ROLE_LEVEL: dict[str, int] = {"viewer": 0, "analyst": 1, "ops": 2, "admin": 3}


def require_role(min_role: Role):
    """Return a FastAPI dep that 403s unless the user is at or above min_role."""

    def _dep(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if _ROLE_LEVEL.get(user.role, -1) < _ROLE_LEVEL[min_role]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role >= {min_role}, have {user.role}",
            )
        return user

    return _dep
