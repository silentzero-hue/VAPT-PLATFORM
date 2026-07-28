"""Findings router — the triage queue."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Query, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import CurrentUser, can_triage, get_current_user
from app.core.db import get_session
from app.models.asset import Asset
from app.models.engagement import Engagement
from app.models.finding import (
    Finding, FindingActivity, FindingEvidence, FindingStatus,
)
from app.models.user import AuditLog, Role
from app.models.vulnerability import Vulnerability
from app.models.workspace import Workspace
from app.schemas.finding import (
    BulkTriageRequest, FindingActivityOut, FindingEvidenceOut,
    FindingOut, FindingUpdate, TriageAction,
)

router = APIRouter(tags=["findings"])


def _to_out(f: Finding, v: Vulnerability | None, a: Asset | None) -> FindingOut:
    return FindingOut(
        id=f.id, workspace_id=f.workspace_id, engagement_id=f.engagement_id,
        vulnerability_id=f.vulnerability_id, asset_id=f.asset_id,
        port=f.port, protocol=f.protocol, evidence_ref=f.evidence_ref,
        status=f.status.value,
        severity=(v.severity.value if v else "info"),
        effective_severity=(f.severity_override or (v.severity.value if v else "info")),
        cvss_score=(f.cvss_score_override or (v.cvss_score if v else None)),
        risk_score=f.risk_score,
        risk_components=f.risk_components,
        sla_due_at=f.sla_due_at, sla_breached=f.sla_breached,
        first_seen=f.first_seen, last_seen=f.last_seen, resolved_at=f.resolved_at,
        assigned_to=f.assigned_to,
        asset_value=(a.value if a else None),
        asset_type=(a.type.value if a else None),
        vuln_title=(v.title if v else None),
        vuln_cve_id=(v.cve_id if v else None),
    )


async def _load_full(db: AsyncSession, fid: UUID) -> tuple[Finding, Vulnerability, Asset] | None:
    f = await db.get(Finding, fid)
    if not f:
        return None
    v = await db.get(Vulnerability, f.vulnerability_id)
    a = await db.get(Asset, f.asset_id)
    return f, v, a  # type: ignore[return-value]


def _check_workspace_scope(current: CurrentUser, workspace_id) -> None:
    if current.role == Role.PLATFORM_ADMIN.value:
        return
    if current.workspace_id != workspace_id:
        raise HTTPException(403, "cross-workspace access denied")


def _check_scope(current: CurrentUser, f: Finding) -> None:
    _check_workspace_scope(current, f.workspace_id)


@router.get("/engagements/{eid}/findings", response_model=list[FindingOut])
async def list_findings(
    eid: Annotated[UUID, Path(...)],
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
    status: str | None = None,
    severity: str | None = None,
    q: str | None = None,
    assigned_to: UUID | None = None,
    limit: int = Query(default=100, ge=1, le=5000),
    offset: int = 0,
):
    e = await db.get(Engagement, eid)
    if not e:
        raise HTTPException(404, "engagement not found")
    _check_scope(current, e)
    stmt = select(Finding).where(Finding.engagement_id == eid)
    if status:
        try:
            stmt = stmt.where(Finding.status == FindingStatus(status))
        except ValueError:
            raise HTTPException(400, "bad status")
    if assigned_to:
        stmt = stmt.where(Finding.assigned_to == assigned_to)
    if q:
        stmt = stmt.join(Vulnerability, Vulnerability.id == Finding.vulnerability_id).where(
            Vulnerability.title.ilike(f"%{q}%") | Vulnerability.cve_id.ilike(f"%{q}%")
        )
    stmt = stmt.options(
        selectinload(Finding.vulnerability),
        selectinload(Finding.asset),
    ).order_by(Finding.first_seen.desc()).limit(limit).offset(offset)
    rows = (await db.execute(stmt)).scalars().all()
    out: list[FindingOut] = []
    for f in rows:
        out.append(_to_out(f, f.vulnerability, f.asset))
    if severity:
        out = [o for o in out if o.effective_severity == severity]
    return out


@router.get("/findings/{fid}", response_model=FindingOut)
async def get_finding(
    fid: Annotated[UUID, Path(...)],
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    f = await db.get(Finding, fid)
    if not f:
        raise HTTPException(404, "not found")
    _check_scope(current, f)
    v = await db.get(Vulnerability, f.vulnerability_id)
    a = await db.get(Asset, f.asset_id)
    return _to_out(f, v, a)


@router.get("/findings/{fid}/activity", response_model=list[FindingActivityOut])
async def get_activity(
    fid: Annotated[UUID, Path(...)],
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    f = await db.get(Finding, fid)
    if not f:
        raise HTTPException(404, "not found")
    _check_scope(current, f)
    rows = (await db.execute(
        select(FindingActivity)
        .where(FindingActivity.finding_id == fid)
        .order_by(FindingActivity.created_at.desc())
        .limit(500)
    )).scalars().all()
    return [FindingActivityOut(
        id=r.id, action=r.action, actor_id=r.actor_id,
        detail=r.detail, comment=r.comment, created_at=r.created_at,
    ) for r in rows]


@router.get("/findings/{fid}/evidence", response_model=list[FindingEvidenceOut])
async def get_evidence(
    fid: Annotated[UUID, Path(...)],
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    f = await db.get(Finding, fid)
    if not f:
        raise HTTPException(404, "not found")
    _check_scope(current, f)
    rows = (await db.execute(
        select(FindingEvidence).where(FindingEvidence.finding_id == fid)
    )).scalars().all()
    return [FindingEvidenceOut(
        id=r.id, kind=r.kind, filename=r.filename, mime=r.mime,
        size=r.size, sha256=r.sha256, note=r.note, created_at=r.created_at,
    ) for r in rows]


@router.post("/findings/{fid}/triage", response_model=FindingOut)
async def triage(
    fid: Annotated[UUID, Path(...)], body: TriageAction, request: Request,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    if not can_triage(current.role):
        raise HTTPException(403, "triage role required")
    f = await db.get(Finding, fid)
    if not f:
        raise HTTPException(404, "not found")
    _check_scope(current, f)

    new_status = f.status
    detail = {"by": current.user.id, "via": "triage_endpoint"}
    now = datetime.now(timezone.utc)
    if body.action == "confirm":
        new_status = FindingStatus.CONFIRMED
    elif body.action == "reject":
        new_status = FindingStatus.FALSE_POSITIVE
    elif body.action == "mark_remediated":
        new_status = FindingStatus.RESOLVED
        f.resolved_at = now
        f.resolved_by = current.user.id
    elif body.action == "mark_in_remediation":
        new_status = FindingStatus.IN_REMEDIATION
    elif body.action == "accept_risk":
        new_status = FindingStatus.ACCEPTED_RISK
    elif body.action == "defer":
        new_status = FindingStatus.DEFERRED
    elif body.action == "reassign":
        f.assigned_to = body.assigned_to
    elif body.action == "comment":
        pass
    if body.severity_override:
        f.severity_override = body.severity_override
    f.status = new_status
    db.add(FindingActivity(
        finding_id=f.id, actor_id=current.user.id, action=body.action,
        detail=detail, comment=body.comment,
    ))
    db.add(AuditLog(
        workspace_id=f.workspace_id, actor_id=current.user.id, actor_role=current.role,
        action=f"finding.{body.action}", target_type="finding", target_id=f.id,
        extra={"new_status": new_status.value},
        ip=request.client.host if request.client else None,
    ))
    v = await db.get(Vulnerability, f.vulnerability_id)
    a = await db.get(Asset, f.asset_id)
    return _to_out(f, v, a)


@router.post("/findings/bulk-triage", response_model=dict)
async def bulk_triage(
    body: BulkTriageRequest, request: Request,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    if not can_triage(current.role):
        raise HTTPException(403, "triage role required")
    success = 0
    skipped: list[str] = []
    is_platform_admin = current.role == Role.PLATFORM_ADMIN.value
    for fid in body.finding_ids:
        f = await db.get(Finding, fid)
        if not f:
            skipped.append(str(fid))
            continue
        if not is_platform_admin and f.workspace_id != current.workspace_id:
            skipped.append(str(fid))
            continue
        if body.action.action == "confirm":
            f.status = FindingStatus.CONFIRMED
        elif body.action.action == "reject":
            f.status = FindingStatus.FALSE_POSITIVE
        elif body.action.action == "mark_remediated":
            f.status = FindingStatus.RESOLVED
            f.resolved_at = datetime.now(timezone.utc)
            f.resolved_by = current.user.id
        elif body.action.action == "mark_in_remediation":
            f.status = FindingStatus.IN_REMEDIATION
        elif body.action.action == "accept_risk":
            f.status = FindingStatus.ACCEPTED_RISK
        elif body.action.action == "defer":
            f.status = FindingStatus.DEFERRED
        if body.action.severity_override:
            f.severity_override = body.action.severity_override
        if body.action.assigned_to:
            f.assigned_to = body.action.assigned_to
        db.add(FindingActivity(
            finding_id=f.id, actor_id=current.user.id,
            action=f"bulk_{body.action.action}", detail={"bulk": True},
            comment=body.action.comment,
        ))
        success += 1
    db.add(AuditLog(
        workspace_id=current.workspace_id, actor_id=current.user.id,
        actor_role=current.role, action=f"finding.bulk_{body.action.action}",
        extra={"count": success, "ids": [str(x) for x in body.finding_ids],
               "skipped": skipped},
        ip=request.client.host if request.client else None,
    ))
    return {"ok": True, "updated": success, "skipped": skipped}


@router.patch("/findings/{fid}", response_model=FindingOut)
async def update_finding(
    fid: Annotated[UUID, Path(...)], body: FindingUpdate, request: Request,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    if not can_triage(current.role):
        raise HTTPException(403, "triage role required")
    f = await db.get(Finding, fid)
    if not f:
        raise HTTPException(404, "not found")
    _check_scope(current, f)
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(f, k, v)
    db.add(AuditLog(
        workspace_id=f.workspace_id, actor_id=current.user.id, actor_role=current.role,
        action="finding.update", target_type="finding", target_id=f.id,
        ip=request.client.host if request.client else None,
    ))
    v = await db.get(Vulnerability, f.vulnerability_id)
    a = await db.get(Asset, f.asset_id)
    return _to_out(f, v, a)
