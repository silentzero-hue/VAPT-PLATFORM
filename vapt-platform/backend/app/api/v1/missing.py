"""Missing GET endpoints needed by the frontend but not yet exposed.

Covers:
  - /workspaces/{wid}/settings         (workspace settings blob)
  - /workspaces/{wid}/sbom/components  (latest SBOM components)
  - /engagements/{eid}/scan-jobs       (ingestion job history for an engagement)
  - /workspaces/{wid}/threat-intel/feed (recent risk recompute feed)
  - /engagements/{eid}/multiscan/summary (multi-scan dedup stats)
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.core.db import get_session
from app.models.engagement import Engagement
from app.models.ingestion import IngestionJob
from app.models.user import Role
from app.models.workspace import Workspace
from app.schemas.finding import FindingOut
from app.services.ingestion.sbom import parse_cyclonedx, parse_spdx, detect_format

router = APIRouter(tags=["missing"])


# ---------------------------------------------------------------------------
# /workspaces/{wid}/settings  GET + PUT
# ---------------------------------------------------------------------------
settings_router = APIRouter(prefix="/workspaces/{wid}/settings", tags=["settings"])


@settings_router.get("")
async def get_settings(
    wid: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_session)],
    cu: Annotated[CurrentUser, Depends(get_current_user)],
):
    if cu.role != Role.PLATFORM_ADMIN.value and cu.workspace_id != wid:
        raise HTTPException(403, "no access")
    w = await db.get(Workspace, wid)
    if not w:
        raise HTTPException(404, "workspace not found")
    return {
        "workspace_id": str(w.id),
        "name": w.name,
        "slug": w.slug,
        "description": w.description,
        "default_sla_days": w.default_sla_days,
        "settings": getattr(w, "settings", {}) or {},
    }


@settings_router.put("")
async def update_settings(
    wid: uuid.UUID,
    body: dict,
    db: Annotated[AsyncSession, Depends(get_session)],
    cu: Annotated[CurrentUser, Depends(get_current_user)],
):
    if cu.role not in (Role.PLATFORM_ADMIN.value, Role.ADMIN.value) and cu.workspace_id != wid:
        raise HTTPException(403, "no access")
    w = await db.get(Workspace, wid)
    if not w:
        raise HTTPException(404, "workspace not found")
    if "default_sla_days" in body and isinstance(body["default_sla_days"], dict):
        w.default_sla_days = body["default_sla_days"]
    if "description" in body:
        w.description = body["description"]
    if "settings" in body and isinstance(body["settings"], dict):
        # Workspace model has a JSONB `settings` column (added in recent schema)
        try:
            w.settings = body["settings"]
        except AttributeError:
            pass
    return {"ok": True}


# ---------------------------------------------------------------------------
# /workspaces/{wid}/sbom/components  GET (latest parsed components)
# ---------------------------------------------------------------------------
sbom_list_router = APIRouter(prefix="/workspaces/{wid}/sbom", tags=["sbom"])


@sbom_list_router.get("/components")
async def list_sbom_components(
    wid: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_session)],
    cu: Annotated[CurrentUser, Depends(get_current_user)],
    engagement_id: uuid.UUID | None = None,
    limit: int = 200,
):
    """Return parsed SBOM components for the most recent SBOM ingestion job.

    We don't persist components (yet), so we re-parse the original blob from S3
    if available; otherwise we surface an empty list with the most recent job id.
    """
    if cu.role != Role.PLATFORM_ADMIN.value and cu.workspace_id != wid:
        raise HTTPException(403, "no access")
    q = (
        select(IngestionJob)
        .where(
            IngestionJob.workspace_id == wid,
            IngestionJob.format.in_(["cyclonedx", "spdx"]),
        )
        .order_by(desc(IngestionJob.created_at))
        .limit(1)
    )
    if engagement_id:
        q = q.where(IngestionJob.engagement_id == engagement_id)
    job = (await db.execute(q)).scalars().first()
    if not job:
        return {"job_id": None, "format": None, "components_parsed": 0, "components": []}
    # Try to fetch the original blob from S3
    components: list[dict[str, Any]] = []
    if job.source_s3_key:
        try:
            from app.services import storage

            blob = await storage.get_bytes(job.source_s3_key)
            fmt = detect_format(job.source_filename or "", blob[:256])
            if fmt == "cyclonedx":
                comps = parse_cyclonedx(blob)
            elif fmt == "spdx":
                comps = parse_spdx(blob)
            else:
                comps = []
            components = [
                {"name": c.name, "version": c.version, "purl": c.purl, "ecosystem": c.ecosystem}
                for c in comps[:limit]
            ]
        except Exception:  # noqa: BLE001
            components = []
    return {
        "job_id": str(job.id),
        "format": job.format.value if hasattr(job.format, "value") else str(job.format),
        "filename": job.source_filename,
        "uploaded_at": job.created_at.isoformat() if job.created_at else None,
        "components_parsed": job.parsed_items,
        "components": components,
    }


# ---------------------------------------------------------------------------
# /engagements/{eid}/scan-jobs  GET
# ---------------------------------------------------------------------------
scan_jobs_router = APIRouter(prefix="/engagements", tags=["ingestion"])


@scan_jobs_router.get("/{eid}/scan-jobs")
async def list_scan_jobs(
    eid: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_session)],
    cu: Annotated[CurrentUser, Depends(get_current_user)],
    limit: int = 50,
):
    e = await db.get(Engagement, eid)
    if not e:
        raise HTTPException(404, "engagement not found")
    if cu.role != Role.PLATFORM_ADMIN.value and cu.workspace_id != e.workspace_id:
        raise HTTPException(403, "no access")
    jobs = (
        (
            await db.execute(
                select(IngestionJob)
                .where(IngestionJob.engagement_id == eid)
                .order_by(desc(IngestionJob.created_at))
                .limit(min(limit, 200))
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": str(j.id),
            "engagement_id": str(j.engagement_id),
            "source": j.source,
            "source_filename": j.source_filename,
            "format": j.format.value if hasattr(j.format, "value") else str(j.format),
            "status": j.status.value if hasattr(j.status, "value") else str(j.status),
            "started_at": (j.started_at.isoformat() if j.started_at else None),
            "finished_at": (j.finished_at.isoformat() if j.finished_at else None),
            "raw_items": j.raw_items,
            "parsed_items": j.parsed_items,
            "new_vulns": j.new_vulns,
            "merged_vulns": j.merged_vulns,
            "new_findings": j.new_findings,
            "updated_findings": j.updated_findings,
            "regressed_findings": j.regressed_findings,
            "remediated_findings": j.remediated_findings,
            "error": j.error,
            "created_at": j.created_at.isoformat() if j.created_at else None,
        }
        for j in jobs
    ]


# ---------------------------------------------------------------------------
# /workspaces/{wid}/threat-intel/feed  GET
# ---------------------------------------------------------------------------
threat_feed_router = APIRouter(prefix="/workspaces/{wid}/threat-intel", tags=["threat-intel"])


@threat_feed_router.get("/feed")
async def threat_intel_feed(
    wid: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_session)],
    cu: Annotated[CurrentUser, Depends(get_current_user)],
    limit: int = 50,
):
    """Vulnerabilities with their EPSS/KEV/CVSS enrichment joined in.

    LEFT JOIN to ThreatIntelCache so vulns without enrichment still show up
    (with `epss=None`, `kev=False`). Sort by CVSS desc so the most critical
    surface first.
    """
    if cu.role != Role.PLATFORM_ADMIN.value and cu.workspace_id != wid:
        raise HTTPException(403, "no access")
    from app.models.vulnerability import Vulnerability, Severity
    from app.models.threat_intel import ThreatIntelCache

    # One query, LEFT JOIN ThreatIntelCache on cve_id. Use a subquery to
    # avoid ambiguity on the joined columns.
    intel_subq = (
        select(ThreatIntelCache)
        .where(ThreatIntelCache.workspace_id == wid)
        .subquery()
    )
    rows = (
        await db.execute(
            select(
                Vulnerability,
                intel_subq.c.epss_score,
                intel_subq.c.epss_percentile,
                intel_subq.c.kev_listed,
                intel_subq.c.fetched_at,
            )
            .outerjoin(intel_subq, intel_subq.c.cve_id == Vulnerability.cve_id)
            .where(Vulnerability.workspace_id == wid)
            .order_by(desc(Vulnerability.cvss_score))
            .limit(min(limit, 200))
        )
    ).all()

    out = []
    for v, epss, epss_pct, kev, enriched_at in rows:
        out.append({
            "id": str(v.id),
            "title": v.title,
            "cve_id": v.cve_id,
            "severity": v.severity.value if isinstance(v.severity, Severity) else str(v.severity),
            "cvss_score": v.cvss_score,
            "confidence": v.confidence,
            "occurrence_count": v.occurrence_count,
            "epss_score": epss,
            "epss_percentile": epss_pct,
            "kev": bool(kev) if kev is not None else False,
            "fetched_at": enriched_at.isoformat() if enriched_at else None,
        })
    return out


# ---------------------------------------------------------------------------
# /engagements/{eid}/multiscan/summary  GET
# ---------------------------------------------------------------------------
multiscan_summary_router = APIRouter(prefix="/engagements", tags=["multi-scan"])


@multiscan_summary_router.get("/{eid}/multiscan/summary")
async def multiscan_summary(
    eid: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_session)],
    cu: Annotated[CurrentUser, Depends(get_current_user)],
):
    """Aggregate stats per scanner format for an engagement."""
    e = await db.get(Engagement, eid)
    if not e:
        raise HTTPException(404, "engagement not found")
    if cu.role != Role.PLATFORM_ADMIN.value and cu.workspace_id != e.workspace_id:
        raise HTTPException(403, "no access")
    jobs = (
        (
            await db.execute(
                select(IngestionJob)
                .where(IngestionJob.engagement_id == eid)
                .order_by(desc(IngestionJob.created_at))
            )
        )
        .scalars()
        .all()
    )
    # group by format
    by_format: dict[str, dict[str, Any]] = {}
    for j in jobs:
        fmt = j.format.value if hasattr(j.format, "value") else str(j.format)
        s = by_format.setdefault(
            fmt,
            {
                "format": fmt,
                "jobs": 0,
                "raw_items": 0,
                "parsed_items": 0,
                "new_vulns": 0,
                "merged_vulns": 0,
                "new_findings": 0,
                "last_uploaded_at": None,
            },
        )
        s["jobs"] += 1
        s["raw_items"] += j.raw_items
        s["parsed_items"] += j.parsed_items
        s["new_vulns"] += j.new_vulns
        s["merged_vulns"] += j.merged_vulns
        s["new_findings"] += j.new_findings
        if j.created_at:
            iso = j.created_at.isoformat()
            if not s["last_uploaded_at"] or iso > s["last_uploaded_at"]:
                s["last_uploaded_at"] = iso
    return {
        "engagement_id": str(eid),
        "total_jobs": len(jobs),
        "by_format": list(by_format.values()),
    }
