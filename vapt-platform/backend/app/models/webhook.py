"""Outbound webhooks. Signed (HMAC-SHA256), per-workspace, scoped to events."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import (
    ARRAY, Boolean, DateTime, ForeignKey, Index, Integer, String, Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Enum as SAEnum

from app.core.db import Base
from app.models.mixins import Timestamped, UUIDPK


class WebhookEvent(str, Enum):
    FINDING_CREATED = "finding.created"
    FINDING_TRIAGED = "finding.triaged"
    FINDING_REGRESSED = "finding.regressed"
    FINDING_RESOLVED = "finding.resolved"
    VULN_CRITICAL_ADDED = "vuln.critical_added"
    REPORT_RENDERED = "report.rendered"
    REPORT_PENDING_REVIEW = "report.pending_review"
    REPORT_APPROVED = "report.approved"
    REPORT_PUBLISHED = "report.published"
    AGENT_RUN_COMPLETED = "agent.run_completed"
    INGESTION_COMPLETED = "ingestion.completed"


class WebhookStatus(str, Enum):
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    GIVEN_UP = "given_up"


class WebhookEndpoint(Base, UUIDPK, Timestamped):
    __tablename__ = "webhook_endpoints"
    __table_args__ = (Index("ix_we_workspace", "workspace_id"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    secret: Mapped[str] = mapped_column(String(128), nullable=False)  # HMAC key
    events: Mapped[list[str]] = mapped_column(ARRAY(String), nullable=False, default=list)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    last_delivery_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    disabled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class WebhookDelivery(Base, UUIDPK, Timestamped):
    """Audit trail of every delivery attempt (incl. failures)."""

    __tablename__ = "webhook_deliveries"
    __table_args__ = (
        Index("ix_wd_endpoint", "endpoint_id"),
        Index("ix_wd_event", "event"),
    )

    endpoint_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("webhook_endpoints.id", ondelete="CASCADE"), nullable=False
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    event: Mapped[str] = mapped_column(String(80), nullable=False)
    target_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    target_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    status: Mapped[WebhookStatus] = mapped_column(
        SAEnum(WebhookStatus, name="webhook_delivery_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False, default=WebhookStatus.PENDING,
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    response_status: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
