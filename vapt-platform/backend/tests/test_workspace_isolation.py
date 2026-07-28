"""Cross-workspace access denial test (critical security requirement)."""

from __future__ import annotations

import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.core.db import SessionLocal
from app.core.security import create_access_token, hash_password
from app.main import app
from app.models.asset import Asset
from app.models.engagement import Engagement
from app.models.user import User, WorkspaceMembership, Role
from app.models.workspace import Workspace


@pytest.mark.asyncio
async def test_cross_workspace_finding_access_denied(engine):
    """A user with membership in workspace A must not be able to
    read findings belonging to workspace B."""
    SessionLocal = __import__("sqlalchemy.ext.asyncio", fromlist=["async_sessionmaker"]).async_sessionmaker(
        bind=engine, expire_on_commit=False,
    )
    async with SessionLocal() as db:
        # Two workspaces, two users
        wsA = Workspace(name="A", slug=f"a-{uuid.uuid4().hex[:6]}")
        wsB = Workspace(name="B", slug=f"b-{uuid.uuid4().hex[:6]}")
        db.add_all([wsA, wsB])
        await db.flush()
        userA = User(email="a@x.com", full_name="A", password_hash=hash_password("StrongPassword123!"), is_active=True)
        userB = User(email="b@x.com", full_name="B", password_hash=hash_password("StrongPassword123!"), is_active=True)
        db.add_all([userA, userB])
        await db.flush()
        db.add_all([
            WorkspaceMembership(user_id=userA.id, workspace_id=wsA.id, role=Role.ANALYST.value),
            WorkspaceMembership(user_id=userB.id, workspace_id=wsB.id, role=Role.ANALYST.value),
        ])
        eA = Engagement(workspace_id=wsA.id, code="A1", name="A-eng", client="A", type="webapp", status="active", methodology="OWASP-WSTG")
        eB = Engagement(workspace_id=wsB.id, code="B1", name="B-eng", client="B", type="webapp", status="active", methodology="OWASP-WSTG")
        db.add_all([eA, eB])
        await db.flush()
        aA = Asset(workspace_id=wsA.id, type="ip", value="10.0.0.1", first_seen=__import__("datetime").datetime.utcnow(), last_seen=__import__("datetime").datetime.utcnow())
        aB = Asset(workspace_id=wsB.id, type="ip", value="10.0.0.2", first_seen=__import__("datetime").datetime.utcnow(), last_seen=__import__("datetime").datetime.utcnow())
        db.add_all([aA, aB])
        await db.flush()
        # Token for userA scoped to wsA
        token = create_access_token(
            sub=str(userA.id), workspace_id=str(wsA.id),
            role=Role.ANALYST.value, session_id=str(uuid.uuid4()),
        )
        # Build a one-off client with the override
        async def _override():
            yield db
        app.dependency_overrides[__import__("app.core.db", fromlist=["get_session"]).get_session] = _override
        try:
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as c:
                # userA can list wsA engagements
                r = await c.get(f"/api/v1/workspaces/{wsA.id}/engagements",
                                headers={"Authorization": f"Bearer {token}"})
                assert r.status_code == 200
                # userA CANNOT list wsB engagements
                r = await c.get(f"/api/v1/workspaces/{wsB.id}/engagements",
                                headers={"Authorization": f"Bearer {token}"})
                assert r.status_code in (403, 404)
        finally:
            app.dependency_overrides.clear()
