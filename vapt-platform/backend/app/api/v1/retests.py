"""Retest cycles router."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.core.db import get_session
from app.models.engagement import Engagement
from app.models.retest import RetestCycle
from app.models.user import Role
from app.services.retest import attach_retest_engagement, schedule, summarise

router = APIRouter(prefix="/workspaces/{wid}", tags=["retests"])


def _check_workspace_scope(current: CurrentUser, workspace_id) -> None:
    if current.role == Role.PLATFORM_ADMIN.value:
        return
    if current.workspace_id != workspace_id:
        raise HTTPException(403, "no access")


class RetestIn(BaseModel):
    engagement_id: uuid.UUID
    title: str = Field(min_length=2, max_length=200)
    scheduled_for: date | None = None
    note: str | None = None


@router.post("/retests", status_code=201)
async def create(
    wid: Annotated[uuid.UUID, Path(...)], body: RetestIn,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    _check_workspace_scope(current, wid)
    e = await db.get(Engagement, body.engagement_id)
    if not e or e.workspace_id != wid:
        raise HTTPException(404, "engagement not found")
    rc = await schedule(
        db, workspace_id=wid, engagement_id=body.engagement_id,
        title=body.title, scheduled_for=body.scheduled_for,
        actor_id=current.user.id, note=body.note,
    )
    return {"id": str(rc.id), "status": rc.status.value}


@router.get("/retests")
async def list_all(
    wid: Annotated[uuid.UUID, Path(...)],
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    _check_workspace_scope(current, wid)
    rows = (await db.execute(
        select(RetestCycle).where(RetestCycle.workspace_id == wid)
        .order_by(RetestCycle.scheduled_for.desc())
    )).scalars().all()
    return [
        {
            "id": str(r.id), "engagement_id": str(r.engagement_id),
            "retest_engagement_id": str(r.retest_engagement_id) if r.retest_engagement_id else None,
            "title": r.title, "status": r.status.value,
            "scheduled_for": r.scheduled_for, "started_at": r.started_at,
            "completed_at": r.completed_at, "summary": r.summary, "note": r.note,
        }
        for r in rows
    ]


@router.post("/retests/{rc_id}/attach")
async def attach(
    wid: Annotated[uuid.UUID, Path(...)],
    rc_id: Annotated[uuid.UUID, Path(...)],
    retest_engagement_id: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    _check_workspace_scope(current, wid)
    rc = await db.get(RetestCycle, rc_id)
    if not rc or rc.workspace_id != wid:
        raise HTTPException(404, "retest not found")
    e = await db.get(Engagement, retest_engagement_id)
    if not e or e.workspace_id != wid:
        raise HTTPException(404, "engagement not found")
    await attach_retest_engagement(db, rc_id, retest_engagement_id)
    return {"ok": True}


@router.post("/retests/{rc_id}/summarise")
async def sum_up(
    wid: Annotated[uuid.UUID, Path(...)],
    rc_id: Annotated[uuid.UUID, Path(...)],
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    _check_workspace_scope(current, wid)
    rc = await db.get(RetestCycle, rc_id)
    if not rc or rc.workspace_id != wid:
        raise HTTPException(404, "retest not found")
    summary = await summarise(db, rc_id)
    return summary
