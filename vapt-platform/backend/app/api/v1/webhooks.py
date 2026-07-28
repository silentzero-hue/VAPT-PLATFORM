"""Webhooks router: CRUD + delivery inspection + test-fire."""

from __future__ import annotations

import ipaddress
import socket
import uuid
from datetime import datetime
from typing import Annotated
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.core.db import get_session
from app.models.webhook import WebhookDelivery, WebhookEndpoint, WebhookEvent
from app.services.webhooks import deliver_due, enqueue, new_secret

router = APIRouter(prefix="/workspaces/{wid}/webhooks", tags=["webhooks"])


def _check_workspace_scope(current: CurrentUser, workspace_id) -> None:
    if current.role == "platform_admin":
        return
    if current.workspace_id != workspace_id:
        raise HTTPException(403, "no access")


def _validate_webhook_url(url: str) -> None:
    """Reject URLs that would let an attacker pivot to internal infra
    (loopback, link-local, RFC1918, cloud metadata, etc.)."""
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise HTTPException(400, "url scheme must be http or https")
    host = parsed.hostname
    if not host:
        raise HTTPException(400, "url missing hostname")
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror:
        raise HTTPException(400, "url hostname could not be resolved")
    for info in infos:
        ip_str = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            raise HTTPException(400, "url resolved to invalid address")
        if (
            ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise HTTPException(
                400, f"url resolves to disallowed address {ip}"
            )


class WebhookOut(BaseModel):
    id: uuid.UUID
    name: str
    url: str
    events: list[str]
    active: bool
    last_delivery_at: datetime | None
    failure_count: int
    created_at: datetime


class WebhookCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    url: str = Field(min_length=10)
    events: list[str] = Field(default_factory=list)


@router.get("", response_model=list[WebhookOut])
async def list_wh(
    wid: Annotated[uuid.UUID, Path(...)],
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    _check_workspace_scope(current, wid)
    rows = (await db.execute(
        select(WebhookEndpoint).where(WebhookEndpoint.workspace_id == wid)
        .order_by(WebhookEndpoint.created_at.desc())
    )).scalars().all()
    return [WebhookOut(
        id=e.id, name=e.name, url=e.url, events=e.events or [],
        active=e.active, last_delivery_at=e.last_delivery_at,
        failure_count=e.failure_count, created_at=e.created_at,
    ) for e in rows]


@router.post("", status_code=201)
async def create_wh(
    wid: Annotated[uuid.UUID, Path(...)], body: WebhookCreate,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    _check_workspace_scope(current, wid)
    _validate_webhook_url(body.url)
    e = WebhookEndpoint(
        workspace_id=wid, name=body.name, url=body.url,
        secret=new_secret(), events=body.events,
        created_by=current.user.id,
    )
    db.add(e)
    await db.flush()
    return WebhookOut(
        id=e.id, name=e.name, url=e.url, events=e.events or [],
        active=e.active, last_delivery_at=e.last_delivery_at,
        failure_count=e.failure_count, created_at=e.created_at,
    )


@router.delete("/{eid}", status_code=204)
async def delete_wh(
    wid: Annotated[uuid.UUID, Path(...)],
    eid: Annotated[uuid.UUID, Path(...)],
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    _check_workspace_scope(current, wid)
    e = await db.get(WebhookEndpoint, eid)
    if not e or e.workspace_id != wid:
        raise HTTPException(404, "not found")
    await db.delete(e)


@router.post("/{eid}/test")
async def test_wh(
    wid: Annotated[uuid.UUID, Path(...)],
    eid: Annotated[uuid.UUID, Path(...)],
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    _check_workspace_scope(current, wid)
    ep = await db.get(WebhookEndpoint, eid)
    if not ep or ep.workspace_id != wid:
        raise HTTPException(404, "not found")
    n = await enqueue(
        db, workspace_id=wid, event=WebhookEvent.FINDING_CREATED,
        target_type="test", target_id=None, payload={"hello": "world"},
    )
    delivered = await deliver_due(db, endpoint_id=eid)
    return {"queued": n, "delivered": delivered}


@router.get("/deliveries")
async def list_deliveries(
    wid: Annotated[uuid.UUID, Path(...)],
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
    limit: int = 50,
):
    _check_workspace_scope(current, wid)
    rows = (await db.execute(
        select(WebhookDelivery).where(WebhookDelivery.workspace_id == wid)
        .order_by(WebhookDelivery.created_at.desc()).limit(limit)
    )).scalars().all()
    return [
        {
            "id": str(d.id), "endpoint_id": str(d.endpoint_id),
            "event": d.event, "status": d.status.value,
            "attempts": d.attempts, "response_status": d.response_status,
            "delivered_at": d.delivered_at, "created_at": d.created_at,
        }
        for d in rows
    ]
