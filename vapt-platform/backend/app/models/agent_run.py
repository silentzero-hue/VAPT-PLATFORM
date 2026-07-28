"""Agent improvement loop. Captures the diff between the AI draft and
the human-approved final text, plus per-run approval stats. These
diff records become the few-shot corpus for future runs and feed
the per-analyst improvement dashboard."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.mixins import Timestamped, UUIDPK


class AgentDraftDiff(Base, UUIDPK, Timestamped):
    """One row per approved (or rejected) AI-drafted narrative."""

    __tablename__ = "agent_draft_diffs"
    __table_args__ = (
        Index("ix_add_vuln", "vulnerability_id"),
        Index("ix_add_workspace", "workspace_id"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    vulnerability_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("vulnerabilities.id", ondelete="CASCADE"), nullable=False
    )
    agent_session_id: Mapped[str] = mapped_column(String(80), nullable=False)
    engagement_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("engagements.id", ondelete="SET NULL"), nullable=True
    )
    reviewer_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    decision: Mapped[str] = mapped_column(String(20), nullable=False)  # approved|changes_requested|rejected
    original_impact: Mapped[str | None] = mapped_column(Text)
    final_impact: Mapped[str | None] = mapped_column(Text)
    original_recommendation: Mapped[str | None] = mapped_column(Text)
    final_recommendation: Mapped[str | None] = mapped_column(Text)
    # Numeric similarity (0..1) between original and final — proxy for edit distance
    impact_similarity: Mapped[float | None] = mapped_column(Float)
    recommendation_similarity: Mapped[float | None] = mapped_column(Float)
    edit_seconds: Mapped[int | None] = mapped_column(Integer)
    extra: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    reviewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AgentRun(Base, UUIDPK, Timestamped):
    """Persistent record of an agent run. The WebSocket feed reads from
    here to replay events to a late-joining client."""

    __tablename__ = "agent_runs"
    __table_args__ = (
        Index("ix_ar_engagement", "engagement_id"),
        Index("ix_ar_session", "agent_session_id", unique=True),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    engagement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    agent_session_id: Mapped[str] = mapped_column(String(80), nullable=False)
    provider: Mapped[str] = mapped_column(String(20), nullable=False)  # anthropic|openai|local
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)  # running|done|error
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    iterations: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tool_calls: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    tool_results: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    vulns_drafted: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    report_rendered: Mapped[bool] = mapped_column(default=False, nullable=False)
