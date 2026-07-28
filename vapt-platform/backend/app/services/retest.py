"""Retest workflow: schedule, run, summarise.

A retest is a follow-up engagement against the same scope. After
the retest scans are ingested, this service computes the delta:
  - still remediated (good)
  - regressed (bad)
  - new findings (medium)
  - closed as false positive (acceptable)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.engagement import Engagement
from app.models.finding import Finding, FindingStatus
from app.models.retest import RetestCycle, RetestStatus
from app.models.user import AuditLog


async def schedule(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    engagement_id: uuid.UUID,
    title: str,
    scheduled_for,
    actor_id: uuid.UUID,
    note: str | None = None,
) -> RetestCycle:
    rc = RetestCycle(
        workspace_id=workspace_id, engagement_id=engagement_id,
        title=title, scheduled_for=scheduled_for, note=note,
        status=RetestStatus.SCHEDULED,
    )
    db.add(rc)
    db.add(AuditLog(
        workspace_id=workspace_id, actor_id=actor_id, action="retest.schedule",
        target_type="engagement", target_id=engagement_id,
        extra={"title": title, "scheduled_for": str(scheduled_for)},
    ))
    await db.flush()
    return rc


async def attach_retest_engagement(
    db: AsyncSession, rc_id: uuid.UUID, retest_engagement_id: uuid.UUID
) -> None:
    rc = await db.get(RetestCycle, rc_id)
    if rc:
        rc.retest_engagement_id = retest_engagement_id
        rc.status = RetestStatus.IN_PROGRESS
        rc.started_at = datetime.now(timezone.utc)


async def summarise(
    db: AsyncSession, rc_id: uuid.UUID
) -> dict:
    """Compare findings before vs after, persist summary."""
    rc = await db.get(RetestCycle, rc_id)
    if not rc or not rc.retest_engagement_id:
        return {}
    e_before = await db.get(Engagement, rc.engagement_id)
    e_after = await db.get(Engagement, rc.retest_engagement_id)
    if not e_before or not e_after:
        return {}
    findings_before = (await db.execute(
        select(Finding).where(Finding.engagement_id == e_before.id)
    )).scalars().all()
    findings_after = (await db.execute(
        select(Finding).where(Finding.engagement_id == e_after.id)
    )).scalars().all()
    by_vuln = {f.vulnerability_id: f for f in findings_before}
    by_vuln_after = {f.vulnerability_id: f for f in findings_after}

    still_remediated: list[str] = []
    regressed: list[str] = []
    new_findings: list[str] = []
    for vid, fa in by_vuln.items():
        if vid in by_vuln_after:
            fb = by_vuln_after[vid]
            if fb.status in (FindingStatus.REGRESSED,):
                regressed.append(str(vid))
            elif fb.status in (FindingStatus.RESOLVED, FindingStatus.FALSE_POSITIVE,
                               FindingStatus.ACCEPTED_RISK):
                still_remediated.append(str(vid))
        else:
            # vuln no longer seen — assume remediated
            still_remediated.append(str(vid))
    for vid in by_vuln_after:
        if vid not in by_vuln:
            new_findings.append(str(vid))

    summary = {
        "still_remediated_count": len(still_remediated),
        "regressed_count": len(regressed),
        "new_findings_count": len(new_findings),
        "still_remediated": still_remediated,
        "regressed": regressed,
        "new_findings": new_findings,
    }
    rc.summary = summary
    rc.status = RetestStatus.COMPLETED
    rc.completed_at = datetime.now(timezone.utc)
    return summary
