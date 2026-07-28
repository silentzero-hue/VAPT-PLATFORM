"""Nessus live-server router: per-workspace config, scan list, ingest."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ADMIN_ROLES, CurrentUser, get_current_user
from app.core.db import get_session
from app.models.engagement import Engagement
from app.models.nessus import NessusScanCache, NessusServer
from app.models.user import Role
from app.services.nessus_api.client import (
    client_for, export_and_ingest, refresh_scan_cache,
)
from app.services.ldap_sync import encrypt_password

router = APIRouter(prefix="/workspaces/{wid}/nessus", tags=["nessus"])


class ServerOut(BaseModel):
    id: uuid.UUID
    name: str
    base_url: str
    verify_ssl: bool
    request_timeout: int
    max_concurrency: int
    only_completed_scans: bool
    last_sync_at: datetime | None
    last_sync_status: str | None
    last_sync_error: str | None
    active: bool


class ServerIn(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    base_url: str = Field(min_length=10, max_length=500)
    access_key: str = Field(min_length=8)
    secret_key: str = Field(min_length=8)
    verify_ssl: bool = False
    request_timeout: int = Field(default=30, ge=5, le=300)
    max_concurrency: int = Field(default=5, ge=1, le=20)
    only_completed_scans: bool = True


class ServerUp(BaseModel):
    name: str | None = None
    base_url: str | None = None
    access_key: str | None = None
    secret_key: str | None = None
    verify_ssl: bool | None = None
    request_timeout: int | None = None
    max_concurrency: int | None = None
    only_completed_scans: bool | None = None
    active: bool | None = None


@router.get("/server", response_model=ServerOut | None)
async def get_server(
    wid: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    if current.role not in (Role.PLATFORM_ADMIN.value, *ADMIN_ROLES) and current.workspace_id != wid:
        raise HTTPException(403, "no access")
    s = await db.scalar(select(NessusServer).where(NessusServer.workspace_id == wid))
    if not s:
        return None
    return _to_out(s)


@router.put("/server", response_model=ServerOut)
async def upsert(
    wid: uuid.UUID, body: ServerIn,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    if current.role not in (Role.PLATFORM_ADMIN.value, *ADMIN_ROLES) and current.workspace_id != wid:
        raise HTTPException(403, "no access")
    s = await db.scalar(select(NessusServer).where(NessusServer.workspace_id == wid))
    if not s:
        s = NessusServer(workspace_id=wid, created_by=current.user.id)
        db.add(s)
    s.name = body.name
    s.base_url = body.base_url
    s.access_key_ciphertext = encrypt_password(body.access_key)
    s.secret_key_ciphertext = encrypt_password(body.secret_key)
    s.verify_ssl = body.verify_ssl
    s.request_timeout = body.request_timeout
    s.max_concurrency = body.max_concurrency
    s.only_completed_scans = body.only_completed_scans
    await db.flush()
    return _to_out(s)


@router.patch("/server", response_model=ServerOut)
async def update(
    wid: uuid.UUID, body: ServerUp,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    if current.role not in (Role.PLATFORM_ADMIN.value, *ADMIN_ROLES) and current.workspace_id != wid:
        raise HTTPException(403, "no access")
    s = await db.scalar(select(NessusServer).where(NessusServer.workspace_id == wid))
    if not s:
        raise HTTPException(404, "not configured")
    for k, v in body.model_dump(exclude_unset=True).items():
        if v is None:
            continue
        if k == "access_key":
            s.access_key_ciphertext = encrypt_password(v)
        elif k == "secret_key":
            s.secret_key_ciphertext = encrypt_password(v)
        else:
            setattr(s, k, v)
    await db.flush()
    return _to_out(s)


@router.post("/sync")
async def sync(
    wid: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    if current.role not in (Role.PLATFORM_ADMIN.value, *ADMIN_ROLES) and current.workspace_id != wid:
        raise HTTPException(403, "no access")
    s = await db.scalar(select(NessusServer).where(NessusServer.workspace_id == wid))
    if not s:
        raise HTTPException(404, "not configured")
    try:
        n = await refresh_scan_cache(db, s)
        return {"ok": True, "scans": n}
    except Exception as e:  # noqa: BLE001
        s.last_sync_status = "error"
        s.last_sync_error = str(e)[:500]
        raise HTTPException(502, f"nessus error: {e}")


@router.get("/scans")
async def list_cached_scans(
    wid: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
    limit: int = Query(default=200, le=1000),
):
    if current.workspace_id != wid and current.role != Role.PLATFORM_ADMIN.value:
        raise HTTPException(403, "no access")
    rows = (await db.execute(
        select(NessusScanCache)
        .where(NessusScanCache.server_id.in_(
            select(NessusServer.id).where(NessusServer.workspace_id == wid)
        ))
        .order_by(NessusScanCache.completed_at.desc().nullslast())
        .limit(limit)
    )).scalars().all()
    return [
        {
            "id": str(r.id), "scan_id": r.scan_id, "name": r.name,
            "status": r.status, "policy": r.policy, "scan_type": r.scan_type,
            "target": r.target, "created_at": r.created_at,
            "completed_at": r.completed_at, "last_fetched_at": r.last_fetched_at,
        }
        for r in rows
    ]


@router.post("/ingest/{scan_id}")
async def ingest(
    wid: uuid.UUID, scan_id: int,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
    engagement_id: uuid.UUID = Query(...),
):
    if current.role not in (Role.PLATFORM_ADMIN.value, *ADMIN_ROLES) and current.workspace_id != wid:
        raise HTTPException(403, "no access")
    s = await db.scalar(select(NessusServer).where(NessusServer.workspace_id == wid))
    if not s:
        raise HTTPException(404, "not configured")
    e = await db.get(Engagement, engagement_id)
    if not e or e.workspace_id != wid:
        raise HTTPException(404, "engagement not found")
    n = await export_and_ingest(db, s, scan_id, engagement_id)
    return {"ok": True, "new_findings": n, "scan_id": scan_id}


def _to_out(s: NessusServer) -> ServerOut:
    return ServerOut(
        id=s.id, name=s.name, base_url=s.base_url, verify_ssl=s.verify_ssl,
        request_timeout=s.request_timeout, max_concurrency=s.max_concurrency,
        only_completed_scans=s.only_completed_scans,
        last_sync_at=s.last_sync_at, last_sync_status=s.last_sync_status,
        last_sync_error=s.last_sync_error, active=s.active,
    )
