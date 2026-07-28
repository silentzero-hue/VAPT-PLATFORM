"""Asset CRUD router."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.core.db import get_session
from app.models.asset import Asset
from app.models.user import Role
from app.schemas.asset import AssetCreate, AssetOut, AssetUpdate

router = APIRouter(prefix="/workspaces/{wid}/assets", tags=["assets"])


def _to_out(a: Asset) -> AssetOut:
    return AssetOut(
        id=a.id, type=a.type.value, value=a.value, port=a.port, protocol=a.protocol,
        fqdn=a.fqdn, ip=a.ip, environment=a.environment,
        criticality=a.criticality.value, owner=a.owner, business_unit=a.business_unit,
        tags=a.tags, first_seen=a.first_seen, last_seen=a.last_seen,
    )


@router.post("", response_model=AssetOut, status_code=201)
async def create_asset(
    wid: UUID, body: AssetCreate, request: Request,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    if current.role != Role.PLATFORM_ADMIN.value and current.workspace_id != wid:
        raise HTTPException(403, "no access")
    now = datetime.now(timezone.utc)
    a = Asset(
        workspace_id=wid, type=body.type, value=body.value,
        port=body.port, protocol=body.protocol, fqdn=body.fqdn, ip=body.ip,
        environment=body.environment, criticality=body.criticality,
        owner=body.owner, business_unit=body.business_unit, tags=body.tags,
        first_seen=now, last_seen=now,
    )
    db.add(a)
    await db.flush()
    return _to_out(a)


@router.get("", response_model=list[AssetOut])
async def list_assets(
    wid: UUID,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
    q: str | None = Query(default=None),
    type: str | None = None,
    criticality: str | None = None,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = 0,
):
    if current.role != Role.PLATFORM_ADMIN.value and current.workspace_id != wid:
        raise HTTPException(403, "no access")
    stmt = select(Asset).where(Asset.workspace_id == wid)
    if q:
        stmt = stmt.where(Asset.value.ilike(f"%{q}%") | Asset.fqdn.ilike(f"%{q}%") | Asset.ip.ilike(f"%{q}%"))
    if type:
        stmt = stmt.where(Asset.type == type)
    if criticality:
        stmt = stmt.where(Asset.criticality == criticality)
    stmt = stmt.order_by(Asset.last_seen.desc()).limit(limit).offset(offset)
    rows = (await db.execute(stmt)).scalars().all()
    return [_to_out(a) for a in rows]


@router.get("/{aid}", response_model=AssetOut)
async def get_asset(
    wid: UUID, aid: UUID,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    a = await db.get(Asset, aid)
    if not a or a.workspace_id != wid:
        raise HTTPException(404, "not found")
    if current.role != Role.PLATFORM_ADMIN.value and current.workspace_id != wid:
        raise HTTPException(403, "no access")
    return _to_out(a)


@router.patch("/{aid}", response_model=AssetOut)
async def update_asset(
    wid: UUID, aid: UUID, body: AssetUpdate, request: Request,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    a = await db.get(Asset, aid)
    if not a or a.workspace_id != wid:
        raise HTTPException(404, "not found")
    if current.role != Role.PLATFORM_ADMIN.value and current.workspace_id != wid:
        raise HTTPException(403, "no access")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(a, k, v)
    return _to_out(a)
