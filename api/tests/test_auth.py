"""Unit tests for services/auth.py — no DB, no live FastAPI app.

Covers:
- bcrypt round-trips and rejects wrong passwords / empty input
- JWT mint -> decode round-trip with correct claims
- decode_token raises 401 on tampered, expired, or malformed tokens
- require_role enforces the role hierarchy (admin > ops > analyst > viewer)
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt as pyjwt
import pytest
from fastapi import HTTPException

from services.auth import (
    ALGORITHM,
    SECRET_KEY,
    CurrentUser,
    decode_token,
    hash_password,
    mint_access_token,
    require_role,
    verify_password,
)


# ── Password hashing ────────────────────────────────────────────────────

def test_hash_password_roundtrip():
    h = hash_password("hunter2")
    assert h != "hunter2"
    assert verify_password("hunter2", h)
    assert not verify_password("hunter3", h)


def test_hash_password_rejects_empty():
    with pytest.raises(ValueError):
        hash_password("")


def test_verify_password_empty_inputs():
    assert verify_password("", "anything") is False
    assert verify_password("anything", "") is False


def test_verify_password_malformed_hash_does_not_raise():
    assert verify_password("hunter2", "not-a-bcrypt-hash") is False


# ── JWT mint / decode ───────────────────────────────────────────────────

def test_mint_and_decode_token_roundtrip():
    token = mint_access_token(user_id=42, email="x@y.z", role="ops")
    payload = decode_token(token)
    assert payload.sub == "42"
    assert payload.email == "x@y.z"
    assert payload.role == "ops"


def test_decode_token_tampered_signature_401():
    token = mint_access_token(user_id=1, email="a@b.c", role="viewer")
    bad = token[:-2] + ("aa" if not token.endswith("aa") else "bb")
    with pytest.raises(HTTPException) as exc:
        decode_token(bad)
    assert exc.value.status_code == 401


def test_decode_token_expired_401():
    # Sign a token with an already-passed exp using the same secret.
    past = int((datetime.now(UTC) - timedelta(minutes=1)).timestamp())
    token = pyjwt.encode(
        {"sub": "1", "email": "a@b.c", "role": "ops", "exp": past},
        SECRET_KEY,
        algorithm=ALGORITHM,
    )
    with pytest.raises(HTTPException) as exc:
        decode_token(token)
    assert exc.value.status_code == 401
    assert "expired" in exc.value.detail.lower()


# ── require_role hierarchy ──────────────────────────────────────────────

@pytest.mark.parametrize(
    "user_role,min_role,allowed",
    [
        ("admin", "viewer", True),
        ("admin", "admin", True),
        ("ops", "analyst", True),
        ("ops", "ops", True),
        ("ops", "admin", False),
        ("analyst", "ops", False),
        ("viewer", "analyst", False),
        ("viewer", "viewer", True),
    ],
)
def test_require_role_hierarchy(user_role, min_role, allowed):
    dep = require_role(min_role)
    user = CurrentUser(id=1, email="x@y.z", role=user_role)
    if allowed:
        assert dep(user) is user
    else:
        with pytest.raises(HTTPException) as exc:
            dep(user)
        assert exc.value.status_code == 403
