"""User notifications: in-app + email opt-in for @mentions, regressions,
approvals, etc. Resolved by the worker; consumed by the SSE/WebSocket feed."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Index, String, Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Enum as SAEnum

from app.core.db import Base
from app.models.mixins import Timestamped, UUIDPK


class NotificationKind(str, Enum):
    MENTION = "mention"
    FINDING_REGRESSED = "finding.regressed"
    FINDING_RESOLVED = "finding.resolved"
    REPORT_PENDING_REVIEW = "report.pending_review"
    REPORT_APPROVED = "report.approved"
    REPORT_PUBLISHED = "report.published"
    AGENT_RUN_COMPLETED = "agent.run_completed"
    WEBHOOK_FAILED = "webhook.failed"
    INGESTION_FAILED = "ingestion.failed"
    RETEST_DUE = "retest.due"


class Notification(Base, UUIDPK, Timestamped):
    __tablename__ = "notifications"
    __table_args__ = (
        Index("ix_n_user_read", "user_id", "read_at"),
        Index("ix_n_workspace", "workspace_id"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[NotificationKind] = mapped_column(
        SAEnum(NotificationKind, name="notification_kind", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
    target_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    target_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    extra: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    email_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    email_opt_in: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class NotificationPreference(Base, UUIDPK, Timestamped):
    __tablename__ = "notification_preferences"
    __table_args__ = (Index("ix_np_user", "user_id", unique=True),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    email_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    email_digest: Mapped[str] = mapped_column(
        String(20), nullable=False, default="instant"
    )  # instant|daily|weekly
    muted_kinds: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
