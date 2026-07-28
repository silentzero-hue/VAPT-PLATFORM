"""SBOM ingestion + LDAP sync + agent feedback routers."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, check_workspace_scope_or_admin, get_current_user
from app.core.db import get_session
from app.models.ingestion import IngestionJob
from app.models.ldap import LdapConfig
from app.models.user import Role
from app.services.ingestion.sbom import (
    detect_format, parse_cyclonedx, parse_spdx,
)
from app.services.ldap_sync import (
    encrypt_password, sync_workspace,
)
from app.services.agent.feedback import per_analyst_stats, record_diff

router = APIRouter(tags=["features"])


# ---------------------------------------------------------------------------
# SBOM
# ---------------------------------------------------------------------------
sbom_router = APIRouter(prefix="/ingestion/sbom", tags=["sbom"])


@sbom_router.post("/upload", status_code=202)
async def upload_sbom(
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
    file: UploadFile = File(...),
    engagement_id: uuid.UUID = Form(...),
):
    if current.role not in (Role.PLATFORM_ADMIN.value, "analyst", "senior_analyst", "admin"):
        raise HTTPException(403, "analyst+ required")
    blob = await file.read()
    head = blob[:256]
    fmt = detect_format(file.filename or "", head)
    if fmt == "cyclonedx":
        comps = parse_cyclonedx(blob)
    elif fmt == "spdx":
        comps = parse_spdx(blob)
    else:
        raise HTTPException(415, "unsupported SBOM format")
    job = IngestionJob(
        workspace_id=current.workspace_id, engagement_id=engagement_id,
        submitted_by=current.user.id, source="upload",
        source_filename=file.filename, format="json",
    )
    db.add(job)
    await db.flush()
    # In production, async job would do the per-component vuln match.
    # Here we surface the parsed component count immediately.
    return {
        "job_id": str(job.id), "format": fmt, "components_parsed": len(comps),
        "components": [
            {"name": c.name, "version": c.version, "purl": c.purl, "ecosystem": c.ecosystem}
            for c in comps[:200]
        ],
    }


# ---------------------------------------------------------------------------
# LDAP
# ---------------------------------------------------------------------------
ldap_router = APIRouter(prefix="/workspaces/{wid}/ldap", tags=["ldap"])


class LdapConfigIn(BaseModel):
    server_url: str
    use_tls: bool = True
    bind_dn: str
    bind_password: str
    user_search_base: str
    user_search_filter: str = "(uid={username})"
    default_role: str = "viewer"
    group_role_map: dict = Field(default_factory=dict)


class LdapConfigOut(BaseModel):
    id: uuid.UUID
    server_url: str
    use_tls: bool
    bind_dn: str
    user_search_base: str
    user_search_filter: str
    default_role: str
    group_role_map: dict
    sync_interval_minutes: int
    last_sync_at: datetime | None
    last_sync_status: str | None
    last_sync_error: str | None
    active: bool


@ldap_router.put("", response_model=LdapConfigOut)
async def upsert(
    wid: uuid.UUID, body: LdapConfigIn,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    check_workspace_scope_or_admin(
        current, wid, required_roles={Role.ADMIN.value},
    )
    cfg = await db.scalar(select(LdapConfig).where(LdapConfig.workspace_id == wid))
    if not cfg:
        cfg = LdapConfig(workspace_id=wid)
        db.add(cfg)
    cfg.server_url = body.server_url
    cfg.use_tls = body.use_tls
    cfg.bind_dn = body.bind_dn
    cfg.bind_password_ciphertext = encrypt_password(body.bind_password)
    cfg.user_search_base = body.user_search_base
    cfg.user_search_filter = body.user_search_filter
    cfg.default_role = body.default_role
    cfg.group_role_map = body.group_role_map
    await db.flush()
    return _to_out(cfg)


@ldap_router.get("", response_model=LdapConfigOut | None)
async def get(
    wid: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    check_workspace_scope_or_admin(
        current, wid, required_roles={Role.ADMIN.value},
    )
    cfg = await db.scalar(select(LdapConfig).where(LdapConfig.workspace_id == wid))
    return _to_out(cfg) if cfg else None


@ldap_router.post("/sync")
async def sync(
    wid: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    check_workspace_scope_or_admin(
        current, wid, required_roles={Role.ADMIN.value},
    )
    return await sync_workspace(db, wid)


def _to_out(cfg: LdapConfig) -> LdapConfigOut:
    return LdapConfigOut(
        id=cfg.id, server_url=cfg.server_url, use_tls=cfg.use_tls,
        bind_dn=cfg.bind_dn, user_search_base=cfg.user_search_base,
        user_search_filter=cfg.user_search_filter,
        default_role=cfg.default_role, group_role_map=cfg.group_role_map or {},
        sync_interval_minutes=cfg.sync_interval_minutes,
        last_sync_at=cfg.last_sync_at, last_sync_status=cfg.last_sync_status,
        last_sync_error=cfg.last_sync_error, active=cfg.active,
    )


# ---------------------------------------------------------------------------
# Agent feedback (improvement loop)
# ---------------------------------------------------------------------------
agent_router = APIRouter(prefix="/workspaces/{wid}/agent-feedback", tags=["agent-feedback"])


class FeedbackIn(BaseModel):
    vulnerability_id: uuid.UUID
    agent_session_id: str
    engagement_id: uuid.UUID | None = None
    decision: str = Field(pattern=r"^(approved|changes_requested|rejected)$")
    final_impact: str | None = None
    final_recommendation: str | None = None
    edit_seconds: int | None = None


@agent_router.post("", status_code=201)
async def submit(
    wid: uuid.UUID, body: FeedbackIn,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    from app.models.vulnerability import Vulnerability
    v = await db.get(Vulnerability, body.vulnerability_id)
    if not v or v.workspace_id != wid:
        raise HTTPException(404, "vuln not found")
    diff = await record_diff(
        db, workspace_id=wid, vulnerability_id=body.vulnerability_id,
        agent_session_id=body.agent_session_id,
        engagement_id=body.engagement_id, reviewer_id=current.user.id,
        decision=body.decision,
        original_impact=v.ai_draft_impact, final_impact=body.final_impact,
        original_recommendation=v.ai_draft_recommendation,
        final_recommendation=body.final_recommendation,
        edit_seconds=body.edit_seconds,
    )
    return {"id": str(diff.id), "impact_similarity": diff.impact_similarity}


@agent_router.get("/stats")
async def stats(
    wid: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
    days: int = 30,
):
    check_workspace_scope_or_admin(
        current, wid,
        required_roles={Role.ADMIN.value, Role.SENIOR_ANALYST.value},
    )
    return await per_analyst_stats(db, wid, days=days)
