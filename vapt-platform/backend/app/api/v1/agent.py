"""Agent run router. Triggers an MCP-driven report draft. The agent
*cannot* call any /approve endpoint — there is no such tool."""

from __future__ import annotations

import asyncio
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ANALYST_ROLES, CurrentUser, get_current_user
from app.core.db import get_session
from app.core.logging import get_logger
from app.models.agent_run import AgentRun
from app.models.engagement import Engagement
from app.models.user import Role
from app.services.agent.runtime import run_agent

router = APIRouter(prefix="/agent", tags=["agent"])
log = get_logger(__name__)


class RunRequest(BaseModel):
    engagement_id: uuid.UUID


@router.post("/run", status_code=202)
async def trigger_run(
    body: RunRequest,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    if current.role not in (Role.PLATFORM_ADMIN.value, *ANALYST_ROLES):
        raise HTTPException(403, "analyst+ required")
    e = await db.get(Engagement, body.engagement_id)
    if not e:
        raise HTTPException(404, "engagement not found")
    # Platform admin can run on any workspace; others must match their scope.
    if current.role != Role.PLATFORM_ADMIN.value and current.workspace_id != e.workspace_id:
        raise HTTPException(404, "engagement not found")

    async def _go():
        try:
            await run_agent(
                engagement_id=body.engagement_id,
                workspace_id=current.workspace_id,  # type: ignore[arg-type]
                actor_id=current.user.id,
            )
        except Exception:  # noqa: BLE001
            log.exception("agent_run_failed")

    asyncio.create_task(_go())
    return {"ok": True, "status": "started", "engagement_id": str(body.engagement_id)}


@router.get("/runs/{session_id}")
async def get_run(
    session_id: str,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    run = await db.scalar(select(AgentRun).where(AgentRun.agent_session_id == session_id))
    if not run:
        raise HTTPException(404, "not found")
    if current.role != Role.PLATFORM_ADMIN.value and current.workspace_id != run.workspace_id:
        raise HTTPException(403, "no access")
    return {
        "id": str(run.id),
        "session_id": run.agent_session_id,
        "engagement_id": str(run.engagement_id),
        "status": run.status,
        "started_at": run.started_at,
        "finished_at": run.finished_at,
        "iterations": run.iterations,
        "tool_calls": run.tool_calls,
        "tool_results": run.tool_results,
        "error": run.error,
        "vulns_drafted": run.vulns_drafted,
        "report_rendered": run.report_rendered,
    }
