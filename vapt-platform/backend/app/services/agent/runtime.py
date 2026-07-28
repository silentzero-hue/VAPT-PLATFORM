"""MCP client + tool-calling agent loop.

The agent runtime is what orchestrates model calls against the local
MCP server. It strictly does NOT touch the database — every data
access goes through the MCP HTTP API.
"""

from __future__ import annotations

import json
import secrets
import uuid
from typing import Any

import httpx

from app.core.config import settings
from app.core.logging import get_logger
from app.services.agent.providers import LLMClient

log = get_logger(__name__)


# OpenAI/Anthropic function schema for the 8 tools
TOOL_SCHEMAS: list[dict] = [
    {
        "name": "list_findings",
        "description": "List findings in an engagement, optionally filtered by status or severity.",
        "parameters": {
            "type": "object",
            "properties": {
                "engagement_id": {"type": "string"},
                "status": {"type": "string"},
                "severity": {"type": "string"},
            },
            "required": ["engagement_id"],
        },
    },
    {
        "name": "get_vulnerability",
        "description": "Return full vulnerability details, including all linked assets and prior findings.",
        "parameters": {
            "type": "object",
            "properties": {"vulnerability_id": {"type": "string"}},
            "required": ["vulnerability_id"],
        },
    },
    {
        "name": "get_asset_context",
        "description": "Return asset metadata and its prior findings count.",
        "parameters": {
            "type": "object",
            "properties": {"asset_id": {"type": "string"}},
            "required": ["asset_id"],
        },
    },
    {
        "name": "check_duplicate",
        "description": "Check if a (title, description) pair semantically duplicates an existing vulnerability in the workspace.",
        "parameters": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "description": {"type": "string"},
                "workspace_id": {"type": "string"},
            },
            "required": ["title", "description", "workspace_id"],
        },
    },
    {
        "name": "draft_finding_narrative",
        "description": "Persist the agent's impact + recommendation draft for a unique vulnerability. NOT approved until a human reviews it.",
        "parameters": {
            "type": "object",
            "properties": {
                "vulnerability_id": {"type": "string"},
                "impact_text": {"type": "string"},
                "recommendation_text": {"type": "string"},
            },
            "required": ["vulnerability_id", "impact_text", "recommendation_text"],
        },
    },
    {
        "name": "generate_exec_summary_stats",
        "description": "Compute aggregate stats for the exec summary of a report.",
        "parameters": {
            "type": "object",
            "properties": {"engagement_id": {"type": "string"}},
            "required": ["engagement_id"],
        },
    },
    {
        "name": "render_report",
        "description": "Render a docx report for an engagement. Returns a draft; status='draft'.",
        "parameters": {
            "type": "object",
            "properties": {
                "engagement_id": {"type": "string"},
                "template_id": {"type": "string"},
            },
            "required": ["engagement_id"],
        },
    },
    {
        "name": "flag_for_human_review",
        "description": "Mark a draft report as awaiting human review. Agent must end here.",
        "parameters": {
            "type": "object",
            "properties": {
                "report_id": {"type": "string"},
                "notes": {"type": "string"},
            },
            "required": ["report_id"],
        },
    },
]


class MCPClient:
    def __init__(self, base_url: str | None = None) -> None:
        self.base = base_url or settings.mcp_server_url
        self._http = httpx.AsyncClient(base_url=self.base, timeout=120)

    async def call(self, tool: str, args: dict, agent_session_id: str,
                   workspace_id: str | None, actor_id: str | None) -> dict:
        r = await self._http.post(
            "/tools/call",
            json={
                "tool": tool,
                "args": args,
                "agent_session_id": agent_session_id,
                "workspace_id": workspace_id,
                "actor_id": actor_id,
            },
        )
        r.raise_for_status()
        return r.json()

    async def aclose(self) -> None:
        await self._http.aclose()


def _anthropic_tool_schema(tools: list[dict]) -> list[dict]:
    """Anthropic wants input_schema, not parameters."""
    out: list[dict] = []
    for t in tools:
        out.append({
            "name": t["name"],
            "description": t["description"],
            "input_schema": t["parameters"],
        })
    return out


async def run_agent(
    *,
    engagement_id: uuid.UUID,
    workspace_id: uuid.UUID,
    actor_id: uuid.UUID | None,
    on_event=None,
) -> dict:
    """Run the agent loop. Stops when the model calls flag_for_human_review
    or when it returns without any further tool calls."""
    session_id = f"agent-{secrets.token_urlsafe(8)}"
    mcp = MCPClient()
    llm = LLMClient()
    events: list[dict] = []

    # Provider-specific tool schema
    tools_for_llm = (
        _anthropic_tool_schema(TOOL_SCHEMAS)
        if llm.kind == "anthropic"
        else TOOL_SCHEMAS
    )

    # Persist the run + set up the WebSocket bridge
    from app.core.db import SessionLocal
    from app.services.agent.ws_bridge import record_run, append_event
    run_id = None
    async with SessionLocal() as db:
        run = await record_run(
            db, workspace_id=workspace_id, engagement_id=engagement_id,
            actor_id=actor_id, session_id=session_id,
            provider=llm.kind, model=settings.llm_model,
        )
        run_id = run.id
        await db.commit()

    # Load few-shot corpus to improve the agent over time
    try:
        from app.services.agent.feedback import few_shot_corpus
        async with SessionLocal() as db:
            shots = await few_shot_corpus(db, workspace_id, max_examples=2)
    except Exception:
        shots = []

    messages: list[dict] = [
        {
            "role": "user",
            "content": (
                f"Draft a pentest report for engagement {engagement_id}. "
                "Use list_findings, get_vulnerability, check_duplicate, "
                "draft_finding_narrative, generate_exec_summary_stats, "
                "render_report, then flag_for_human_review. "
                "Stop after flag_for_human_review."
            ),
        },
    ]
    if shots:
        messages.insert(0, {
            "role": "system",
            "content": (
                "Examples of approved narratives (style guide):\n"
                + "\n---\n".join(
                    f"Title: {s['vuln_title']}\nAI Impact: {s['ai_impact']}\n"
                    f"Final Impact: {s['final_impact']}\nAI Rec: {s['ai_recommendation']}\n"
                    f"Final Rec: {s['final_recommendation']}"
                    for s in shots
                )
            ),
        })
    flagged = False
    reaped = False
    try:
        for it in range(40):
            async with SessionLocal() as db:
                await append_event(db, session_id, "iteration", {"i": it})
            resp = await llm.chat(messages, tools_for_llm)
            if resp.get("text"):
                events.append({"type": "text", "text": resp["text"]})
                if on_event:
                    await on_event(events[-1])
                async with SessionLocal() as db:
                    await append_event(db, session_id, "text", {"text": resp["text"]})
            tool_calls = resp.get("tool_calls") or []
            if not tool_calls:
                events.append({"type": "done", "reason": "no_tool_calls"})
                async with SessionLocal() as db:
                    await append_event(db, session_id, "done", {"reason": "no_tool_calls"})
                reaped = True
                break

            messages.append({
                "role": "assistant",
                "content": resp.get("text") or "",
                "tool_calls": [
                    {"id": c["id"], "name": c["name"], "arguments": c["arguments"]}
                    for c in tool_calls
                ],
            })
            for c in tool_calls:
                events.append({"type": "tool_call", "tool": c["name"], "args": c["arguments"]})
                if on_event:
                    await on_event(events[-1])
                async with SessionLocal() as db:
                    await append_event(db, session_id, "tool_call", c)
                try:
                    res = await mcp.call(
                        c["name"], c["arguments"], session_id,
                        str(workspace_id), str(actor_id) if actor_id else None,
                    )
                    events.append({"type": "tool_result", "tool": c["name"], "ok": res.get("ok")})
                    if on_event:
                        await on_event(events[-1])
                    async with SessionLocal() as db:
                        await append_event(db, session_id, "tool_result", {"tool": c["name"], "ok": res.get("ok")})
                    messages.append({
                        "role": "tool",
                        "tool_call_id": c["id"],
                        "name": c["name"],
                        "content": json.dumps(res, default=str)[:20000],
                    })
                    if c["name"] == "flag_for_human_review":
                        flagged = True
                except Exception as e:  # noqa: BLE001
                    events.append({"type": "tool_error", "tool": c["name"], "err": str(e)})
                    messages.append({
                        "role": "tool",
                        "tool_call_id": c["id"],
                        "name": c["name"],
                        "content": json.dumps({"ok": False, "error": str(e)}),
                    })
            if flagged:
                events.append({"type": "done", "reason": "agent_flagged_for_human_review"})
                async with SessionLocal() as db:
                    await append_event(db, session_id, "done", {"reason": "flagged"})
                reaped = True
                break
        else:
            if not reaped:
                events.append({"type": "done", "reason": "max_iterations"})
                async with SessionLocal() as db:
                    await append_event(db, session_id, "done", {"reason": "max_iterations"})
                reaped = True
        if not reaped:
            events.append({"type": "done", "reason": "flush"})
            async with SessionLocal() as db:
                await append_event(db, session_id, "done", {"reason": "flush"})
        return {"ok": True, "session_id": session_id, "events": events}
    finally:
        await mcp.aclose()
