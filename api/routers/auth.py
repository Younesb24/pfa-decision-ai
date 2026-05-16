"""Auth router — login + /me.

POST /auth/login accepts JSON or OAuth2 form (so it works with both the
dashboard's fetch() flow and the Swagger UI's built-in auth button).
"""

from __future__ import annotations

from datetime import UTC, datetime

from db import get_db
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel, Field
from services.auth import (
    CurrentUser,
    Role,
    get_current_user,
    mint_access_token,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["Auth"])


class LoginRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: dict


def _authenticate(email: str, password: str) -> dict:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT id, email, password_hash, display_name, role
                FROM governance.users
                WHERE lower(email) = lower(%s)
                """,
                (email,),
            )
            row = cur.fetchone()
    if not row or not verify_password(password, row["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE governance.users SET last_login_at = %s WHERE id = %s",
                (datetime.now(UTC), row["id"]),
            )
            conn.commit()
    return row


@router.post("/login", response_model=TokenResponse)
def login_json(body: LoginRequest) -> TokenResponse:
    row = _authenticate(body.email, body.password)
    token = mint_access_token(user_id=row["id"], email=row["email"], role=row["role"])
    return TokenResponse(
        access_token=token,
        user={
            "id": row["id"],
            "email": row["email"],
            "display_name": row["display_name"],
            "role": row["role"],
        },
    )


@router.post("/token", response_model=TokenResponse, include_in_schema=False)
def login_oauth_form(form: OAuth2PasswordRequestForm = Depends()) -> TokenResponse:
    """OAuth2 password-flow form variant — lets Swagger UI's Authorize button work."""
    row = _authenticate(form.username, form.password)
    token = mint_access_token(user_id=row["id"], email=row["email"], role=row["role"])
    return TokenResponse(
        access_token=token,
        user={
            "id": row["id"],
            "email": row["email"],
            "display_name": row["display_name"],
            "role": row["role"],
        },
    )


@router.get("/me")
def me(user: CurrentUser = Depends(get_current_user)) -> dict:
    return {"id": user.id, "email": user.email, "role": user.role}
