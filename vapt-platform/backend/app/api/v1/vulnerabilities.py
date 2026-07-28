"""Vulnerability router (one vuln, many findings)."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import APPROVE_ROLES, CurrentUser, can_approve_report, get_current_user
from app.core.db import get_session
from app.models.finding import Finding
from app.models.user import Role
from app.models.vulnerability import Vulnerability
from app.schemas.finding import FindingOut
from app.schemas.vulnerability import AiDraftUpdate, LinkedAsset, VulnerabilityOut

router = APIRouter(prefix="/workspaces/{wid}/vulnerabilities", tags=["vulnerabilities"])


@router.get("", response_model=list[VulnerabilityOut])
async def list_vulns(
    wid: UUID,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
    severity: str | None = None,
    q: str | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = 0,
):
    if current.role != Role.PLATFORM_ADMIN.value and current.workspace_id != wid:
        raise HTTPException(403, "no access")
    stmt = select(Vulnerability).where(Vulnerability.workspace_id == wid)
    if severity:
        stmt = stmt.where(Vulnerability.severity == severity)
    if q:
        stmt = stmt.where(
            Vulnerability.title.ilike(f"%{q}%") | Vulnerability.cve_id.ilike(f"%{q}%")
        )
    stmt = stmt.order_by(Vulnerability.occurrence_count.desc()).limit(limit).offset(offset)
    rows = (await db.execute(stmt)).scalars().all()
    return [await _to_out(db, v) for v in rows]


@router.get("/{vid}", response_model=VulnerabilityOut)
async def get_vuln(
    wid: UUID, vid: UUID,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    v = await db.get(Vulnerability, vid)
    if not v or v.workspace_id != wid:
        raise HTTPException(404, "not found")
    if current.role != Role.PLATFORM_ADMIN.value and current.workspace_id != wid:
        raise HTTPException(403, "no access")
    return await _to_out(db, v)


@router.patch("/{vid}/ai-draft", response_model=VulnerabilityOut)
async def update_ai_draft(
    wid: UUID, vid: UUID, body: AiDraftUpdate,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    v = await db.get(Vulnerability, vid)
    if not v or v.workspace_id != wid:
        raise HTTPException(404, "not found")
    if current.role != Role.PLATFORM_ADMIN.value and current.workspace_id != wid:
        raise HTTPException(403, "no access")
    if body.impact is not None:
        v.ai_draft_impact = body.impact
    if body.recommendation is not None:
        v.ai_draft_recommendation = body.recommendation
    if body.approve:
        # Only senior analyst+ can approve an AI draft
        if current.role not in (Role.PLATFORM_ADMIN.value, *APPROVE_ROLES):
            raise HTTPException(403, "approval requires senior_analyst+")
        v.ai_draft_approved = True
        v.ai_draft_reviewed_by = current.user.id
        from datetime import datetime, timezone
        v.ai_draft_reviewed_at = datetime.now(timezone.utc)
    return await _to_out(db, v)


async def _to_out(db: AsyncSession, v: Vulnerability) -> VulnerabilityOut:
    findings = (await db.execute(
        select(Finding, )
        .where(Finding.vulnerability_id == v.id)
        .limit(500)
    )).scalars().all()
    from app.models.asset import Asset
    linked: list[LinkedAsset] = []
    for f in findings:
        a = await db.get(Asset, f.asset_id)
        if not a:
            continue
        linked.append(LinkedAsset(
            asset_id=a.id, asset_value=a.value, asset_type=a.type.value,
            port=f.port, finding_id=f.id, finding_status=f.status.value,
            engagement_id=f.engagement_id,
        ))
    return VulnerabilityOut(
        id=v.id, title=v.title, description=v.description,
        cve_id=v.cve_id, cwe_id=v.cwe_id,
        cwe_category=v.cwe_category.value,
        severity=v.severity.value, cvss_score=v.cvss_score, cvss_vector=v.cvss_vector,
        confidence=v.confidence.value, references=v.references, tags=v.tags,
        source_plugin=v.source_plugin, source_plugin_id=v.source_plugin_id,
        occurrence_count=v.occurrence_count, linked_assets=linked,
        ai_draft_impact=v.ai_draft_impact,
        ai_draft_recommendation=v.ai_draft_recommendation,
        ai_drafted_at=v.ai_drafted_at, ai_draft_approved=v.ai_draft_approved,
        created_at=v.created_at, updated_at=v.updated_at,
    )
