"""Engagement + scope router.

SECURITY: every workspace-scoped handler enforces that the caller's
`current.workspace_id` matches the engagement's `workspace_id`. The
admin-of-any-workspace shortcut has been removed.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.core.db import get_session
from app.models.engagement import Engagement, EngagementStatus, ScopeRule
from app.models.finding import Finding
from app.models.user import AuditLog, Role
from app.schemas.engagement import (
    EngagementCreate, EngagementOut, EngagementUpdate,
    ScopeRuleCreate, ScopeRuleOut,
)

router = APIRouter(tags=["engagements"])


def _check_workspace_scope(current: CurrentUser, workspace_id: UUID) -> None:
    """Raise 403 if the caller cannot access this workspace."""
    if current.role == Role.PLATFORM_ADMIN.value:
        return
    if current.workspace_id != workspace_id:
        raise HTTPException(403, "no access")


@router.post("/workspaces/{wid}/engagements", response_model=EngagementOut, status_code=201)
async def create_engagement(
    wid: Annotated[UUID, Path(...)],
    body: EngagementCreate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    _check_workspace_scope(current, wid)
    e = Engagement(
        workspace_id=wid, code=body.code, name=body.name, client=body.client,
        description=body.description, type=body.type,
        start_date=body.start_date, end_date=body.end_date,
        report_due_date=body.report_due_date,
        methodology=body.methodology, test_types=body.test_types,
        lead_id=body.lead_id,
    )
    db.add(e)
    db.add(AuditLog(
        workspace_id=wid, actor_id=current.user.id, actor_role=current.role,
        action="engagement.create", target_type="engagement",
        ip=request.client.host if request.client else None,
    ))
    await db.flush()
    return await _to_out(db, e)


@router.get("/workspaces/{wid}/engagements", response_model=list[EngagementOut])
async def list_engagements(
    wid: Annotated[UUID, Path(...)],
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
    status: str | None = None,
):
    _check_workspace_scope(current, wid)
    q = select(Engagement).where(Engagement.workspace_id == wid)
    if status:
        try:
            q = q.where(Engagement.status == EngagementStatus(status))
        except ValueError:
            raise HTTPException(400, "bad status")
    rows = (await db.execute(q.order_by(Engagement.created_at.desc()))).scalars().all()
    return [await _to_out(db, e) for e in rows]


@router.get("/engagements/{eid}", response_model=EngagementOut)
async def get_engagement(
    eid: Annotated[UUID, Path(...)],
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    e = await db.get(Engagement, eid)
    if not e:
        raise HTTPException(404, "not found")
    _check_workspace_scope(current, e.workspace_id)
    return await _to_out(db, e)


@router.patch("/engagements/{eid}", response_model=EngagementOut)
async def update_engagement(
    eid: Annotated[UUID, Path(...)],
    body: EngagementUpdate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    e = await db.get(Engagement, eid)
    if not e:
        raise HTTPException(404, "not found")
    _check_workspace_scope(current, e.workspace_id)
    # Whitelist updatable fields; the free-form setattr was a footgun.
    allowed_fields = {
        "name", "client", "description", "type", "status",
        "start_date", "end_date", "report_due_date",
        "methodology", "test_types", "lead_id", "ingestion_locked",
    }
    for k, v in body.model_dump(exclude_unset=True).items():
        if k not in allowed_fields:
            continue
        setattr(e, k, v)
    db.add(AuditLog(
        workspace_id=e.workspace_id, actor_id=current.user.id, actor_role=current.role,
        action="engagement.update", target_type="engagement", target_id=e.id,
        ip=request.client.host if request.client else None,
    ))
    return await _to_out(db, e)


@router.post("/engagements/{eid}/scope", response_model=ScopeRuleOut, status_code=201)
async def add_scope(
    eid: Annotated[UUID, Path(...)],
    body: ScopeRuleCreate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    e = await db.get(Engagement, eid)
    if not e:
        raise HTTPException(404, "not found")
    _check_workspace_scope(current, e.workspace_id)
    s = ScopeRule(
        engagement_id=eid, kind=body.kind, pattern=body.pattern,
        include=body.include, note=body.note,
    )
    db.add(s)
    db.add(AuditLog(
        workspace_id=e.workspace_id, actor_id=current.user.id, actor_role=current.role,
        action="scope.add", target_type="engagement", target_id=eid,
        extra={"kind": body.kind, "pattern": body.pattern},
        ip=request.client.host if request.client else None,
    ))
    await db.flush()
    return ScopeRuleOut(id=s.id, kind=s.kind, pattern=s.pattern, include=s.include, note=s.note)


@router.delete("/engagements/{eid}/scope/{sid}", status_code=204)
async def del_scope(
    eid: Annotated[UUID, Path(...)],
    sid: UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    s = await db.get(ScopeRule, sid)
    if not s or s.engagement_id != eid:
        raise HTTPException(404, "not found")
    e = await db.get(Engagement, eid)
    if not e:
        raise HTTPException(404, "not found")
    _check_workspace_scope(current, e.workspace_id)
    await db.delete(s)
    db.add(AuditLog(
        workspace_id=e.workspace_id, actor_id=current.user.id, actor_role=current.role,
        action="scope.delete", target_type="engagement", target_id=eid,
        ip=request.client.host if request.client else None,
    ))


async def _to_out(db: AsyncSession, e: Engagement) -> EngagementOut:
    # severity breakdown for the dashboard
    from app.models.vulnerability import Vulnerability
    sev_rows = (await db.execute(
        select(Vulnerability.severity).join(Finding, Finding.vulnerability_id == Vulnerability.id)
        .where(Finding.engagement_id == e.id)
    )).all()
    sev_count: dict[str, int] = {}
    for (sev,) in sev_rows:
        sev_value = sev.value if hasattr(sev, "value") else str(sev)
        sev_count[sev_value] = sev_count.get(sev_value, 0) + 1
    type_value = e.type.value if hasattr(e.type, "value") else str(e.type)
    status_value = e.status.value if hasattr(e.status, "value") else str(e.status)
    return EngagementOut(
        id=e.id, workspace_id=e.workspace_id, code=e.code, name=e.name,
        client=e.client, description=e.description, type=type_value,
        status=status_value, start_date=e.start_date, end_date=e.end_date,
        report_due_date=e.report_due_date, methodology=e.methodology,
        test_types=e.test_types, lead_id=e.lead_id,
        ingestion_locked=e.ingestion_locked,
        created_at=e.created_at, updated_at=e.updated_at,
        severity_breakdown=sev_count,
        findings_total=sum(sev_count.values()),
    )
