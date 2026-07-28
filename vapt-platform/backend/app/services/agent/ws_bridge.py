"""WebSocket live feed for an in-progress agent run.

The agent runtime pushes events via `on_event`; we cache the last
N events per session in Redis (and persist to agent_runs) so late
joiners get a replay.
"""

from __future__ import annotations

import asyncio
import json
import secrets
import uuid
from collections import defaultdict
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.core.logging import get_logger
from app.models.agent_run import AgentRun

router = APIRouter(prefix="/agent", tags=["agent-ws"])
log = get_logger(__name__)

# in-memory live channels; survives only as long as the backend process
_channels: dict[str, list[asyncio.Queue]] = defaultdict(list)


async def broadcast(session_id: str, event: dict) -> None:
    dead = []
    for q in list(_channels.get(session_id, [])):
        try:
            q.put_nowait(event)
        except Exception:  # noqa: BLE001
            dead.append(q)
    for q in dead:
        try:
            _channels[session_id].remove(q)
        except ValueError:
            pass


@router.websocket("/ws/{session_id}")
async def ws_run(ws: WebSocket, session_id: str):
    await ws.accept()
    q: asyncio.Queue = asyncio.Queue(maxsize=200)
    _channels[session_id].append(q)
    try:
        # initial replay from DB
        async with SessionLocal() as db:
            run = await _load_run(db, session_id)
            if run:
                for ev in (run.tool_calls or []):
                    await ws.send_json({"type": "replay", "event": ev})
        while True:
            ev = await q.get()
            await ws.send_json(ev)
            if ev.get("type") in ("done", "error"):
                break
    except WebSocketDisconnect:
        pass
    except Exception as e:  # noqa: BLE001
        log.warning("ws_error", err=str(e))
    finally:
        try:
            _channels[session_id].remove(q)
        except ValueError:
            pass


async def _load_run(db: AsyncSession, session_id: str) -> AgentRun | None:
    from sqlalchemy import select
    return await db.scalar(
        select(AgentRun).where(AgentRun.agent_session_id == session_id)
    )


async def record_run(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    engagement_id: uuid.UUID,
    actor_id: uuid.UUID | None,
    session_id: str,
    provider: str,
    model: str,
) -> AgentRun:
    run = AgentRun(
        workspace_id=workspace_id,
        engagement_id=engagement_id,
        actor_id=actor_id,
        agent_session_id=session_id,
        provider=provider, model=model,
        status="running", started_at=datetime.now(timezone.utc),
    )
    db.add(run)
    await db.flush()
    return run


async def append_event(
    db: AsyncSession, session_id: str, kind: str, payload: dict
) -> None:
    run = await _load_run(db, session_id)
    if not run:
        return
    run.iterations = (run.iterations or 0) + (1 if kind == "iteration" else 0)
    if kind == "tool_call":
        run.tool_calls = (run.tool_calls or []) + [payload]
    elif kind == "tool_result":
        run.tool_results = (run.tool_results or []) + [payload]
    if kind == "done":
        run.status = "done"
        run.finished_at = datetime.now(timezone.utc)
    elif kind == "error":
        run.status = "error"
        run.finished_at = datetime.now(timezone.utc)
        run.error = payload.get("error", "")
    # push live
    await broadcast(session_id, {"type": kind, **payload})
