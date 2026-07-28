"""Client portal router. The /portal/* endpoints are anonymous —
they validate a token, not a session."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Form, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ADMIN_ROLES, CurrentUser, get_current_user
from app.core.db import get_session
from app.models.portal import PortalShare
from app.models.user import Role
from app.services.portal import access as access_share, create_share, revoke

router = APIRouter(tags=["portal"])


class ShareOut(BaseModel):
    id: uuid.UUID
    report_id: uuid.UUID
    label: str
    expires_at: datetime | None
    max_views: int | None
    current_views: int
    revoked: bool
    last_access_at: datetime | None
    created_at: datetime


class ShareCreate(BaseModel):
    report_id: uuid.UUID
    label: str = Field(min_length=2, max_length=120)
    expires_at: datetime | None = None
    max_views: int | None = None
    require_password: bool = False
    password: str | None = None
    allowed_emails: list[str] = Field(default_factory=list)
    watermark_with_viewer: bool = True
    note: str | None = None


@router.post("/workspaces/{wid}/portal-shares", status_code=201)
async def create(
    wid: uuid.UUID, body: ShareCreate,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    if current.role not in (Role.PLATFORM_ADMIN.value, *ADMIN_ROLES, Role.SENIOR_ANALYST.value) and current.workspace_id != wid:
        raise HTTPException(403, "no access")
    if body.require_password and not body.password:
        raise HTTPException(400, "password required")
    share, raw = await create_share(
        db, workspace_id=wid, report_id=body.report_id,
        label=body.label, actor_id=current.user.id,
        expires_at=body.expires_at, max_views=body.max_views,
        require_password=body.require_password, password=body.password,
        allowed_emails=body.allowed_emails,
        watermark_with_viewer=body.watermark_with_viewer, note=body.note,
    )
    return {
        **ShareOut(
            id=share.id, report_id=share.report_id, label=share.label,
            expires_at=share.expires_at, max_views=share.max_views,
            current_views=share.current_views, revoked=share.revoked_at is not None,
            last_access_at=share.last_access_at, created_at=share.created_at,
        ).model_dump(),
        "url": f"/portal/{raw}",
        "raw_token": raw,
        "warning": "Share URL contains the token. Distribute through a secure channel.",
    }


@router.get("/workspaces/{wid}/portal-shares", response_model=list[ShareOut])
async def list_shares(
    wid: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    if current.role not in (Role.PLATFORM_ADMIN.value, *ADMIN_ROLES, Role.SENIOR_ANALYST.value) and current.workspace_id != wid:
        raise HTTPException(403, "no access")
    rows = (await db.execute(
        select(PortalShare).where(PortalShare.workspace_id == wid)
        .order_by(PortalShare.created_at.desc())
    )).scalars().all()
    return [ShareOut(
        id=s.id, report_id=s.report_id, label=s.label,
        expires_at=s.expires_at, max_views=s.max_views,
        current_views=s.current_views, revoked=s.revoked_at is not None,
        last_access_at=s.last_access_at, created_at=s.created_at,
    ) for s in rows]


@router.delete("/portal-shares/{sid}", status_code=204)
async def revoke_one(
    sid: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    s = await db.get(PortalShare, sid)
    if not s:
        raise HTTPException(404, "not found")
    if current.role not in (Role.PLATFORM_ADMIN.value, *ADMIN_ROLES, Role.SENIOR_ANALYST.value) and current.workspace_id != s.workspace_id:
        raise HTTPException(403, "no access")
    await revoke(db, sid, reason="manual revoke")


# ---------- anonymous portal access ----------

@router.get("/portal/{token}")
async def portal_meta(
    token: str,
    db: Annotated[AsyncSession, Depends(get_session)],
):
    """Public metadata for a share. Used by the client-portal landing page
    to decide whether to show a password prompt or a download button."""
    from app.services.portal import _new_token  # type: ignore
    import hashlib
    from app.core.security import hash_token
    s = await db.scalar(
        select(PortalShare).where(PortalShare.token_hash == hash_token(token))
    )
    if not s:
        raise HTTPException(404, "share not found")
    return {
        "label": s.label,
        "expires_at": s.expires_at,
        "require_password": s.require_password,
        "current_views": s.current_views,
        "max_views": s.max_views,
    }


@router.post("/portal/{token}/download")
async def portal_download(
    token: str,
    db: Annotated[AsyncSession, Depends(get_session)],
    password: str | None = Form(default=None),
    email: str | None = Form(default=None),
):
    share, report, data = await access_share(db, token, email, password)
    return StreamingResponse(
        iter([data]),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="{report.title}.docx"',
            "X-VAPT-Signed-SHA256": report.signed_sha256 or "",
            "X-VAPT-Share": str(share.id),
        },
    )
