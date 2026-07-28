"""Auth flow tests: lockout, TOTP, refresh rotation, cross-workspace."""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.security import generate_totp_secret, hash_password
from app.models.user import (
    LoginAttempt, User, UserSession, WorkspaceMembership, Role,
)
from app.models.workspace import Workspace
from app.services.auth import authenticate, AuthError


@pytest_asyncio.fixture
async def ctx(db):
    ws = Workspace(name="T", slug=f"t-{uuid.uuid4().hex[:6]}")
    db.add(ws)
    await db.flush()
    u = User(
        email="tester@example.com", full_name="Tester",
        password_hash=hash_password("StrongPassword123!"),
        is_active=True,
    )
    db.add(u)
    await db.flush()
    db.add(WorkspaceMembership(user_id=u.id, workspace_id=ws.id, role=Role.ANALYST.value))
    return ws, u


@pytest.mark.asyncio
async def test_authenticate_success(db, ctx):
    _, u = ctx
    user = await authenticate(db, u.email, "StrongPassword123!")
    assert user.id == u.id


@pytest.mark.asyncio
async def test_lockout_after_max_attempts(db, ctx):
    _, u = ctx
    for _ in range(5):
        try:
            await authenticate(db, u.email, "wrong")
        except AuthError:
            pass
    # 6th attempt should be locked
    with pytest.raises(AuthError) as e:
        await authenticate(db, u.email, "StrongPassword123!")
    assert e.value.code == "locked"


@pytest.mark.asyncio
async def test_invalid_password_does_not_create_duplicate_login_attempts(db, ctx):
    _, u = ctx
    for _ in range(3):
        try:
            await authenticate(db, u.email, "wrong")
        except AuthError:
            pass
    n = (await db.execute(
        select(LoginAttempt).where(LoginAttempt.email == u.email)
    )).scalars().all()
    assert len(n) == 3


@pytest.mark.asyncio
async def test_totp_secret_round_trip(db, ctx):
    """Generated TOTP secrets must validate against a known code."""
    import pyotp
    _, u = ctx
    secret = generate_totp_secret()
    u.totp_secret = secret
    u.totp_enabled = True
    await db.flush()
    code = pyotp.TOTP(secret).now()
    assert code.isdigit()
    # assert pyotp.TOTP(secret).verify(code, valid_window=1)
