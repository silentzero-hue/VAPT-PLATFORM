"""Agent run schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class AgentRunOut(BaseModel):
    id: UUID
    session_id: str
    engagement_id: UUID
    status: str
    started_at: datetime
    finished_at: datetime | None
    iterations: int
    tool_calls: list
    tool_results: list
    error: str | None
    vulns_drafted: int
    report_rendered: bool
