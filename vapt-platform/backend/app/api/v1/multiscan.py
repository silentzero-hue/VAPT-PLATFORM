"""Multi-scan analysis, table view, legacy SQLite import."""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ANALYST_ROLES, CurrentUser, check_workspace_scope_or_admin, get_current_user
from app.core.db import get_session
from app.models.engagement import Engagement
from app.models.user import Role
from app.services.multi_scan import (
    bulk_delete, compare_two, regressed_across, ScanFingerprint,
)
from app.services.legacy_db import import_legacy, read_legacy_db
from app.services.reporting.table_view import (
    build_table_view, render_table_view_docx, render_table_view_html,
)

router = APIRouter(tags=["multi-scan"])


# ---------------------------------------------------------------------------
# Multi-scan
# ---------------------------------------------------------------------------

@router.get("/engagements/{eid}/multiscan/compare")
async def multiscan_compare(
    eid: uuid.UUID,
    baseline: uuid.UUID,
    current: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_session)],
    cu: Annotated[CurrentUser, Depends(get_current_user)],
):
    e = await db.get(Engagement, eid)
    if not e:
        raise HTTPException(404, "engagement not found")
    if cu.role != Role.PLATFORM_ADMIN.value and cu.workspace_id != e.workspace_id:
        raise HTTPException(403, "no access")
    res = await compare_two(db, baseline, current)
    return {
        "baseline": {
            "scan_id": res.baseline.scan_id, "name": res.baseline.name,
            "created_at": res.baseline.created_at, "finished_at": res.baseline.finished_at,
            "triple_count": res.baseline.triple_count,
        },
        "current": {
            "scan_id": res.current.scan_id, "name": res.current.name,
            "created_at": res.current.created_at, "finished_at": res.current.finished_at,
            "triple_count": res.current.triple_count,
        },
        "summary": res.summary,
        "still_present_count": len(res.still_present),
        "new_findings_count": len(res.new_findings),
        "fixed_count": len(res.fixed),
        "still_present": [_fto(f) for f in res.still_present[:200]],
        "new_findings": [_fto(f) for f in res.new_findings[:200]],
        "fixed": [_fto(f) for f in res.fixed[:200]],
    }


class BulkDeleteIn(BaseModel):
    finding_ids: list[uuid.UUID]


@router.post("/findings/bulk-delete")
async def finding_bulk_delete(
    body: BulkDeleteIn,
    db: Annotated[AsyncSession, Depends(get_session)],
    cu: Annotated[CurrentUser, Depends(get_current_user)],
):
    if cu.role not in (Role.PLATFORM_ADMIN.value, *ANALYST_ROLES):
        raise HTTPException(403, "analyst+ required")
    n = await bulk_delete(db, body.finding_ids, cu.user.id)
    return {"ok": True, "deleted": n}


def _fto(f) -> dict:
    return {
        "id": str(f.id), "asset_id": str(f.asset_id),
        "vulnerability_id": str(f.vulnerability_id),
        "port": f.port, "protocol": f.protocol,
        "status": f.status.value, "first_seen": f.first_seen.isoformat() if f.first_seen else None,
        "last_seen": f.last_seen.isoformat() if f.last_seen else None,
    }


# ---------------------------------------------------------------------------
# Table view
# ---------------------------------------------------------------------------

table_router = APIRouter(tags=["table-view"])


@table_router.get("/engagements/{eid}/table-view")
async def get_table_view(
    eid: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_session)],
    cu: Annotated[CurrentUser, Depends(get_current_user)],
    fmt: str = "json",
):
    e = await db.get(Engagement, eid)
    if not e:
        raise HTTPException(404, "engagement not found")
    if cu.role != Role.PLATFORM_ADMIN.value and cu.workspace_id != e.workspace_id:
        raise HTTPException(403, "no access")
    data = await build_table_view(db, eid)
    if fmt == "docx":
        b = render_table_view_docx(data)
        return StreamingResponse(
            iter([b]),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f'attachment; filename="{e.code}-table-view.docx"'},
        )
    if fmt == "html":
        return StreamingResponse(
            iter([render_table_view_html(data).encode()]),
            media_type="text/html",
        )
    return data


# ---------------------------------------------------------------------------
# Legacy DB import
# ---------------------------------------------------------------------------

legacy_router = APIRouter(prefix="/workspaces/{wid}/legacy", tags=["legacy"])


@legacy_router.post("/import")
async def legacy_import(
    wid: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_session)],
    cu: Annotated[CurrentUser, Depends(get_current_user)],
    engagement_id: uuid.UUID = Form(...),
    db_path: str = Form(...),
):
    check_workspace_scope_or_admin(
        cu, wid, required_roles={Role.ADMIN.value},
    )
    e = await db.get(Engagement, engagement_id)
    if not e or e.workspace_id != wid:
        raise HTTPException(404, "engagement not found")
    try:
        # Note: this is a sync sqlite call — we run it inline; for very
        # large legacy DBs, dispatch to the worker.
        items = read_legacy_db(db_path)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"legacy db read failed: {e}")
    from app.models.ingestion import IngestionJob
    job = IngestionJob(
        workspace_id=wid, engagement_id=engagement_id,
        submitted_by=cu.user.id, source="legacy_db",
        source_filename=db_path, format="nessus",
    )
    db.add(job)
    await db.flush()
    from app.services.ingestion.service import process
    # Build a synthetic .nessus-shaped blob from the items; process()
    # only dedups by the (cve|plugin) key, which matches our NormalizedItem.
    # We re-use the existing nessus parser path by serializing items
    # back into a fake XML is unnecessary; instead we pass through
    # the dedup service directly.
    from app.services.dedup.engine import find_or_create
    from app.services.ingestion.service import _upsert_asset
    from app.models.finding import Finding, FindingStatus
    from datetime import datetime, timezone
    new_f = 0
    new_v = 0
    for it in items:
        vuln, created, _ = await find_or_create(
            db, workspace_id=wid, title=it.title, description=it.description,
            cve_id=it.cve_id, cwe_id=None,
            plugin=it.plugin, plugin_id=it.plugin_id, severity=it.severity,
        )
        if created:
            new_v += 1
        a = await _upsert_asset(db, wid, it)
        existing = await db.scalar(
            __import__("sqlalchemy").select(Finding).where(
                Finding.vulnerability_id == vuln.id,
                Finding.asset_id == a.id,
                Finding.engagement_id == engagement_id,
                Finding.port == it.port,
            )
        )
        if not existing:
            now = datetime.now(timezone.utc)
            db.add(Finding(
                workspace_id=wid, engagement_id=engagement_id,
                vulnerability_id=vuln.id, asset_id=a.id,
                port=it.port, protocol=it.protocol,
                status=FindingStatus.NEW,
                first_seen=now, last_seen=now,
            ))
            new_f += 1
    job.new_vulns = new_v
    job.new_findings = new_f
    job.parsed_items = len(items)
    job.status = "done"
    job.finished_at = datetime.now(timezone.utc)
    return {"ok": True, "rows": len(items), "new_vulns": new_v, "new_findings": new_f, "job_id": str(job.id)}


@legacy_router.get("/preview")
async def legacy_preview(
    wid: uuid.UUID,
    db_path: str,
    cu: Annotated[CurrentUser, Depends(get_current_user)],
):
    """Dry-run: count rows in a legacy DB without ingesting."""
    check_workspace_scope_or_admin(
        cu, wid, required_roles={Role.ADMIN.value},
    )
    try:
        items = read_legacy_db(db_path)
    except Exception as e:  # noqa: BLE001
        raise HTTPException(400, f"read failed: {e}")
    return {"rows": len(items), "first_3": [i.title for i in items[:3]]}
