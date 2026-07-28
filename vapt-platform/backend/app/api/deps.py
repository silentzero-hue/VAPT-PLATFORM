"""Common API dependencies: auth, RBAC, workspace context."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_session
from app.core.security import decode_token, hash_token
from app.models.user import Role, User, UserSession, WorkspaceMembership

bearer = HTTPBearer(auto_error=False)

ACCESS_COOKIE = "vapt_access"


@dataclass
class CurrentUser:
    user: User
    role: str  # role inside the active workspace (or platform_admin marker)
    workspace_id: UUID | None
    session_id: UUID | None


async def get_current_user(
    request: Request,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[AsyncSession, Depends(get_session)],
) -> CurrentUser:
    # Accept the access token from either the Authorization header
    # OR the vapt_access cookie (sent by the SPA frontend).
    token: str | None = None
    if creds and creds.credentials:
        token = creds.credentials
    elif request.cookies.get(ACCESS_COOKIE):
        token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="missing bearer token"
        )
    try:
        payload = decode_token(token)
    except JWTError:
        # SECURITY: do not leak the JWT reason (e.g. "Signature verification failed",
        # "Expired at ...") back to the caller. Log it server-side, return generic.
        from app.core.logging import get_logger
        get_logger(__name__).info("jwt_decode_failed", token_prefix=token[:8])
        raise HTTPException(status_code=401, detail="invalid token") from None

    if payload.get("typ") != "access":
        raise HTTPException(status_code=401, detail="invalid token")

    user_id = payload.get("sub")
    session_id = payload.get("sid")
    wid = payload.get("wid")
    if not user_id or not session_id:
        raise HTTPException(status_code=401, detail="malformed token")

    user = await db.get(User, UUID(user_id))
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="user not found or disabled")

    # Confirm session still valid (not revoked)
    sess = await db.get(UserSession, UUID(session_id))
    if not sess or sess.revoked_at is not None:
        raise HTTPException(status_code=401, detail="session revoked")

    # Determine active role
    role: str = "viewer"
    if user.is_platform_admin:
        role = Role.PLATFORM_ADMIN.value
    elif wid:
        mem = await db.scalar(
            select(WorkspaceMembership).where(
                WorkspaceMembership.user_id == user.id,
                WorkspaceMembership.workspace_id == UUID(wid),
            )
        )
        if not mem:
            # Token references a workspace the user no longer belongs to.
            raise HTTPException(status_code=403, detail="no workspace access")
        role = mem.role

    return CurrentUser(
        user=user,
        role=role,
        workspace_id=UUID(wid) if wid else None,
        session_id=UUID(session_id),
    )


def require_role(*allowed: str):
    """Factory: dependency that checks the user's role."""

    async def _checker(
        current: Annotated[CurrentUser, Depends(get_current_user)],
    ) -> CurrentUser:
        if current.role not in allowed and current.role != Role.PLATFORM_ADMIN.value:
            raise HTTPException(
                status_code=403,
                detail=f"role '{current.role}' not in {list(allowed)}",
            )
        return current

    return _checker


def require_workspace(
    workspace_id: UUID,
    current: CurrentUser,
) -> CurrentUser:
    """Use inside a route to confirm workspace_id is in the user's scope."""
    if current.role == Role.PLATFORM_ADMIN.value:
        return current
    if current.workspace_id != workspace_id:
        raise HTTPException(status_code=403, detail="cross-workspace access denied")
    return current


# Permissions matrix — small & explicit on purpose.
ANALYST_ROLES = {Role.PLATFORM_ADMIN.value, Role.ADMIN.value, Role.SENIOR_ANALYST.value, Role.ANALYST.value}
APPROVE_ROLES = {Role.PLATFORM_ADMIN.value, Role.ADMIN.value, Role.SENIOR_ANALYST.value}
ADMIN_ROLES = {Role.PLATFORM_ADMIN.value, Role.ADMIN.value}


def can_triage(role: str) -> bool:
    return role in ANALYST_ROLES


def can_approve_report(role: str) -> bool:
    return role in APPROVE_ROLES


def can_admin(role: str) -> bool:
    return role in ADMIN_ROLES
