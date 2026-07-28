"""Multi-scan analyzer.

The legacy tool's main value-add: take 2+ scans of the same scope
taken on different dates, and tell the analyst exactly what changed.

For each scan we identify the set of (vuln_id, asset_id, port) tuples
present at that time. Comparing any two scans produces:

  * still_present  — present in both
  * new            — present in scan B but not scan A (regression OR new finding)
  * fixed          — present in scan A but not scan B (remediated)
  * regressed      — present in scan A, fixed, then present again in scan C

We also surface the *exact* finding rows that fall into each bucket,
so the analyst can re-open them in one click.
"""

from __future__ import annotations

import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.engagement import Engagement
from app.models.finding import Finding
from app.models.ingestion import IngestionJob
from app.models.vulnerability import Vulnerability


def _triples(findings: Iterable[Finding]) -> set[tuple[str, str, int | None]]:
    """A scan is represented as the set of (vuln_id, asset_id, port) tuples
    it produced. This is the same set on which our dedup uniqueness
    is built, so it's a faithful re-identification."""
    out: set[tuple[str, str, int | None]] = set()
    for f in findings:
        out.add((str(f.vulnerability_id), str(f.asset_id), f.port))
    return out


@dataclass
class ScanFingerprint:
    scan_id: str
    name: str
    created_at: str
    finished_at: str | None
    triple_count: int
    triples: set[tuple[str, str, int | None]] = field(default_factory=set)
    findings: list[Finding] = field(default_factory=list)


async def _fingerprint(db: AsyncSession, job_id: uuid.UUID) -> ScanFingerprint:
    job = await db.get(IngestionJob, job_id)
    if not job:
        raise ValueError(f"job {job_id} not found")
    rows = (await db.execute(
        select(Finding).where(
            Finding.workspace_id == job.workspace_id,
        )
    )).scalars().all()
    # We don't currently persist a per-job finding list, so we
    # approximate: findings whose last_seen falls within the job's
    # started_at..finished_at window.
    findings = []
    if job.started_at and job.finished_at:
        findings = [f for f in rows if job.started_at <= f.last_seen <= job.finished_at]
    elif job.started_at:
        findings = [f for f in rows if f.last_seen >= job.started_at]
    else:
        findings = rows
    return ScanFingerprint(
        scan_id=str(job_id),
        name=job.source_filename or f"job-{job_id}",
        created_at=job.created_at.isoformat() if job.created_at else "",
        finished_at=job.finished_at.isoformat() if job.finished_at else None,
        triple_count=len(findings),
        triples=_triples(findings),
        findings=findings,
    )


@dataclass
class CompareResult:
    baseline: ScanFingerprint
    current: ScanFingerprint
    still_present: list[Finding]
    new_findings: list[Finding]
    fixed: list[Finding]
    summary: dict


async def compare_two(
    db: AsyncSession, baseline_job_id: uuid.UUID, current_job_id: uuid.UUID
) -> CompareResult:
    a = await _fingerprint(db, baseline_job_id)
    b = await _fingerprint(db, current_job_id)
    a_only = a.triples - b.triples
    b_only = b.triples - a.triples
    both = a.triples & b.triples
    fp_to_finding: dict[tuple[str, str, int | None], Finding] = {}
    for f in (*a.findings, *b.findings):
        fp_to_finding[(str(f.vulnerability_id), str(f.asset_id), f.port)] = f
    return CompareResult(
        baseline=a,
        current=b,
        still_present=[fp_to_finding[t] for t in both if t in fp_to_finding],
        new_findings=[fp_to_finding[t] for t in b_only if t in fp_to_finding],
        fixed=[fp_to_finding[t] for t in a_only if t in fp_to_finding],
        summary={
            "baseline_triples": len(a.triples),
            "current_triples": len(b.triples),
            "still_present": len(both),
            "new": len(b_only),
            "fixed": len(a_only),
        },
    )


async def regressed_across(
    db: AsyncSession, job_ids: list[uuid.UUID]
) -> list[dict]:
    """For 3+ ordered scans: which findings were fixed then reappeared?"""
    if len(job_ids) < 2:
        return []
    fps = [await _fingerprint(db, j) for j in job_ids]
    out = []
    for i in range(1, len(fps)):
        for t in fps[i - 1].triples - fps[i].triples:  # present in A, gone in B
            for k in range(i + 1, len(fps)):
                if t in fps[k].triples:  # back in C
                    out.append({
                        "triple": list(t),
                        "fixed_in": fps[i].scan_id,
                        "regressed_in": fps[k].scan_id,
                    })
                    break
    return out


async def bulk_delete(
    db: AsyncSession, finding_ids: list[uuid.UUID], actor_id: uuid.UUID
) -> int:
    """Legacy `test_vulnerability_crud_operations` parity — bulk delete
    is the cleanup that makes retest workflow usable.

    Only deletes findings in the new state. Returns count deleted.
    """
    from sqlalchemy import delete
    from app.models.finding import FindingStatus
    rows = (await db.execute(
        select(Finding).where(
            Finding.id.in_(finding_ids),
            Finding.status == FindingStatus.NEW,
        )
    )).scalars().all()
    n = len(rows)
    for f in rows:
        await db.delete(f)
    from app.models.user import AuditLog
    db.add(AuditLog(
        workspace_id=rows[0].workspace_id if rows else uuid.uuid4(),
        actor_id=actor_id, action="finding.bulk_delete",
        extra={"count": n, "ids": [str(x) for x in finding_ids]},
    ))
    return n
