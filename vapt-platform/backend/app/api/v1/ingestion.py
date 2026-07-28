"""Ingestion router: upload + drop-poll + status + preview parse."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ANALYST_ROLES, CurrentUser, get_current_user
from app.core.config import settings
from app.core.db import get_session
from app.core.logging import get_logger
from app.models.engagement import Engagement
from app.models.ingestion import IngestionJob, IngestionStatus
from app.models.user import Role
from app.schemas.ingestion import IngestionJobOut, IngestionUploadResponse
from app.services.ingestion.service import detect_format, _parse_for_format

router = APIRouter(prefix="/ingestion", tags=["ingestion"])
log = get_logger(__name__)

MAX_UPLOAD_BYTES = 100 * 1024 * 1024


def _enforce_size_cap(request: Request) -> None:
    cl = request.headers.get("content-length")
    if cl and cl.isdigit() and int(cl) > MAX_UPLOAD_BYTES:
        raise HTTPException(413, "file too large")


@router.post("/upload", response_model=IngestionUploadResponse, status_code=202)
async def upload(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
    file: UploadFile = File(...),
    engagement_id: uuid.UUID = Form(...),
):
    _enforce_size_cap(request)
    if current.role not in (Role.PLATFORM_ADMIN.value, *ANALYST_ROLES):
        raise HTTPException(403, "analyst+ required")
    e = await db.get(Engagement, engagement_id)
    if not e or e.workspace_id != current.workspace_id:
        raise HTTPException(404, "engagement not found")
    if e.ingestion_locked:
        raise HTTPException(409, "engagement locked for this engagement")
    blob = await file.read()
    head = blob[:512]
    fmt = detect_format(file.filename or "", head)
    if fmt.value == "unknown":
        raise HTTPException(415, "unsupported format")
    job = IngestionJob(
        workspace_id=current.workspace_id,
        engagement_id=engagement_id,
        submitted_by=current.user.id,
        source="upload",
        source_filename=file.filename,
        format=fmt,
    )
    db.add(job)
    await db.flush()
    if settings.app_env == "development":
        try:
            from app.services.ingestion.service import process
            await process(db, job=job, blob=blob)
        except Exception as ex:  # noqa: BLE001
            log.exception("ingest_failed", job=str(job.id), err=str(ex))
            raise HTTPException(500, f"ingest failed: {ex}") from ex
    return IngestionUploadResponse(
        job_id=job.id, filename=file.filename or "", size=len(blob), format_detected=fmt.value,
    )


class ParsePreviewItem(BaseModel):
    title: str
    severity: str
    asset_value: str
    asset_type: str
    port: int | None = None
    cve_id: str | None = None
    plugin: str | None = None
    plugin_id: str | None = None


class ParsePreviewOut(BaseModel):
    format_detected: str
    filename: str
    size: int
    count: int
    sample: list[ParsePreviewItem]


@router.post("/parse", response_model=ParsePreviewOut)
async def preview_parse(
    request: Request,
    current: Annotated[CurrentUser, Depends(get_current_user)],
    file: UploadFile = File(...),
    limit: int = Query(default=20, ge=1, le=200),
):
    """Parse a scan output without persisting anything. Useful for the
    'what is this file' UX in the upload widget."""
    _enforce_size_cap(request)
    if current.role not in (Role.PLATFORM_ADMIN.value, *ANALYST_ROLES):
        raise HTTPException(403, "analyst+ required")
    blob = await file.read()
    head = blob[:512]
    fmt = detect_format(file.filename or "", head)
    if fmt.value == "unknown":
        raise HTTPException(415, "unsupported format")
    try:
        items = _parse_for_format(fmt, blob)
    except Exception as ex:  # noqa: BLE001
        raise HTTPException(400, f"parse error: {ex}") from ex
    sample = [
        ParsePreviewItem(
            title=it.title,
            severity=it.severity,
            asset_value=it.asset_value,
            asset_type=it.asset_type,
            port=it.port,
            cve_id=it.cve_id,
            plugin=it.plugin,
            plugin_id=it.plugin_id,
        )
        for it in items[:limit]
    ]
    return ParsePreviewOut(
        format_detected=fmt.value,
        filename=file.filename or "",
        size=len(blob),
        count=len(items),
        sample=sample,
    )


@router.get("/jobs/{jid}", response_model=IngestionJobOut)
async def get_job(
    jid: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    job = await db.get(IngestionJob, jid)
    if not job or job.workspace_id != current.workspace_id:
        raise HTTPException(404, "not found")
    return IngestionJobOut(
        id=job.id, engagement_id=job.engagement_id, source=job.source,
        source_filename=job.source_filename, format=job.format.value,
        status=job.status.value, started_at=job.started_at, finished_at=job.finished_at,
        raw_items=job.raw_items, parsed_items=job.parsed_items,
        new_vulns=job.new_vulns, merged_vulns=job.merged_vulns,
        new_findings=job.new_findings, updated_findings=job.updated_findings,
        regressed_findings=job.regressed_findings,
        remediated_findings=job.remediated_findings,
        error=job.error, log=job.log, created_at=job.created_at,
    )


@router.get("/engagements/{eid}/jobs", response_model=list[IngestionJobOut])
async def list_jobs(
    eid: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    rows = (await db.execute(
        select(IngestionJob).where(
            IngestionJob.engagement_id == eid,
            IngestionJob.workspace_id == current.workspace_id,
        ).order_by(IngestionJob.created_at.desc()).limit(100)
    )).scalars().all()
    return [IngestionJobOut(
        id=j.id, engagement_id=j.engagement_id, source=j.source,
        source_filename=j.source_filename, format=j.format.value,
        status=j.status.value, started_at=j.started_at, finished_at=j.finished_at,
        raw_items=j.raw_items, parsed_items=j.parsed_items,
        new_vulns=j.new_vulns, merged_vulns=j.merged_vulns,
        new_findings=j.new_findings, updated_findings=j.updated_findings,
        regressed_findings=j.regressed_findings,
        remediated_findings=j.remediated_findings,
        error=j.error, log=j.log, created_at=j.created_at,
    ) for j in rows]
