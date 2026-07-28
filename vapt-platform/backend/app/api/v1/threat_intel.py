"""Threat intel + risk score router."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.core.db import get_session
from app.models.finding import Finding
from app.models.threat_intel import ThreatIntelCache
from app.services.threat_intel.service import enrich_one

router = APIRouter(prefix="/workspaces/{wid}", tags=["threat-intel"])


def _check_workspace_scope(current: CurrentUser, workspace_id) -> None:
    if current.role == "platform_admin":
        return
    if current.workspace_id != workspace_id:
        raise HTTPException(403, "no access")


@router.post("/vulnerabilities/{vid}/enrich", status_code=202)
async def enrich_vuln(
    wid: Annotated[uuid.UUID, Path(...)],
    vid: Annotated[uuid.UUID, Path(...)],
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    _check_workspace_scope(current, wid)
    from app.models.vulnerability import Vulnerability
    v = await db.get(Vulnerability, vid)
    if not v or v.workspace_id != wid:
        raise HTTPException(404, "vuln not found")
    if not v.cve_id:
        raise HTTPException(400, "vulnerability has no CVE")
    rec = await enrich_one(db, wid, v.cve_id)
    # re-enrich only the findings in this workspace that reference this vuln
    findings = (await db.execute(
        select(Finding).where(
            Finding.vulnerability_id == vid,
            Finding.workspace_id == wid,
        )
    )).scalars().all()
    for f in findings:
        f.threat_intel_id = rec.id
    return {"ok": True, "cve_id": v.cve_id, "epss": rec.epss_score, "kev": rec.kev_listed}


@router.get("/threat-intel/{cve_id}")
async def get_intel(
    wid: Annotated[uuid.UUID, Path(...)],
    cve_id: str,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    _check_workspace_scope(current, wid)
    rec = await db.scalar(
        select(ThreatIntelCache).where(
            ThreatIntelCache.workspace_id == wid, ThreatIntelCache.cve_id == cve_id,
        )
    )
    if rec:
        return {
            "cve_id": rec.cve_id, "cvss_v3": rec.cvss_v3_score, "cvss_v3_vector": rec.cvss_v3_vector,
            "epss_score": rec.epss_score, "epss_percentile": rec.epss_percentile,
            "kev_listed": rec.kev_listed, "kev_due_date": rec.kev_due_date,
            "kev_ransomware_use": rec.kev_ransomware_use,
            "fetched_at": rec.fetched_at, "next_refresh_after": rec.next_refresh_after,
        }
    # Auto-enrich on miss: rather than 404-ing, kick off the enrich and return
    # what we have. This avoids forcing the SPA to call two endpoints in sequence.
    if not cve_id.upper().startswith("CVE-"):
        # Defensive: avoid calling external services for malformed input.
        raise HTTPException(404, "no intel — invalid CVE format")
    try:
        rec = await enrich_one(db, wid, cve_id)
    except Exception:
        # External APIs (NVD/EPSS/KEV) may fail. Return a minimal record so the
        # UI doesn't break; the analyst can retry.
        return {
            "cve_id": cve_id,
            "cvss_v3": None, "cvss_v3_vector": None,
            "epss_score": None, "epss_percentile": None,
            "kev_listed": False, "kev_due_date": None, "kev_ransomware_use": False,
            "fetched_at": None, "next_refresh_after": None,
            "pending": True,
        }
    return {
        "cve_id": rec.cve_id, "cvss_v3": rec.cvss_v3_score, "cvss_v3_vector": rec.cvss_v3_vector,
        "epss_score": rec.epss_score, "epss_percentile": rec.epss_percentile,
        "kev_listed": rec.kev_listed, "kev_due_date": rec.kev_due_date,
        "kev_ransomware_use": rec.kev_ransomware_use,
        "fetched_at": rec.fetched_at, "next_refresh_after": rec.next_refresh_after,
    }


@router.post("/findings/recompute-risk", status_code=202)
async def recompute(
    wid: Annotated[uuid.UUID, Path(...)],
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    _check_workspace_scope(current, wid)
    from app.workers.worker import recompute_risk_scores
    n = await recompute_risk_scores({})
    return n


@router.get("/findings/by-risk")
async def by_risk(
    wid: Annotated[uuid.UUID, Path(...)],
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
    limit: int = Query(default=100, ge=1, le=500),
):
    _check_workspace_scope(current, wid)
    rows = (await db.execute(
        select(Finding)
        .where(Finding.workspace_id == wid, Finding.risk_score.is_not(None))
        .order_by(Finding.risk_score.desc())
        .limit(limit)
    )).scalars().all()
    return [
        {
            "id": str(f.id), "asset_id": str(f.asset_id), "vulnerability_id": str(f.vulnerability_id),
            "status": f.status.value, "risk_score": f.risk_score,
            "risk_components": f.risk_components,
        }
        for f in rows
    ]
