"""Report + ReportTemplate + ReportVersion (immutable version chain)."""

from __future__ import annotations

import uuid
from enum import Enum

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.mixins import Timestamped, UUIDPK


class ReportStatus(str, Enum):
    DRAFTING = "drafting"  # agent is working
    PENDING_REVIEW = "pending_review"  # agent done, awaiting human
    CHANGES_REQUESTED = "changes_requested"  # human sent back
    APPROVED = "approved"  # human approved & locked
    PUBLISHED = "published"  # exported/sent to client (terminal)
    REJECTED = "rejected"  # killed


class ReportTemplate(Base, UUIDPK, Timestamped):
    """A docx or markdown template + a jinja context schema."""

    __tablename__ = "report_templates"
    __table_args__ = (Index("ix_rtpl_workspace", "workspace_id"),)

    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=True,
    )  # null = system template
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    kind: Mapped[str] = mapped_column(String(20), nullable=False)  # docx | html
    template_path: Mapped[str] = mapped_column(String(500), nullable=False)
    schema: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)


class Report(Base, UUIDPK, Timestamped):
    """One pentest report per engagement, with a version chain."""

    __tablename__ = "reports"
    __table_args__ = (
        Index("ix_rep_engagement", "engagement_id"),
        Index("ix_rep_status", "status"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    engagement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False
    )
    template_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("report_templates.id", ondelete="SET NULL"),
        nullable=True,
    )

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    status: Mapped[ReportStatus] = mapped_column(
        SAEnum(ReportStatus, name="report_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=ReportStatus.DRAFTING,
    )
    current_version_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("report_versions.id", ondelete="SET NULL"), nullable=True
    )

    # PKI signing fingerprint of the final approved report (sha256 of docx)
    signed_sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    signed_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    signed_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    locked_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Analyst-edited overlay merged into the auto-built report context
    # at render time. Shape: {"overall_rating": str, "exec_summary": str,
    # "finding_overrides": {finding_id: {severity_override, impact,
    # recommendation, note}}}. Empty dict = no edits.
    draft_payload: Mapped[dict] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb"),
    )

    versions: Mapped[list["ReportVersion"]] = relationship(
        "ReportVersion",
        back_populates="report",
        cascade="all, delete-orphan",
        order_by="ReportVersion.version_no",
        # The Report→ReportVersion link has TWO foreign keys (this one
        # and `current_version_id`). We must tell SQLAlchemy which FK
        # drives the `versions` collection.
        foreign_keys="ReportVersion.report_id",
    )
    current_version: Mapped["ReportVersion | None"] = relationship(
        "ReportVersion",
        foreign_keys=[current_version_id],
        post_update=True,
    )


class ReportVersion(Base, UUIDPK, Timestamped):
    """Each save = a new immutable version. final version's blob is signed."""

    __tablename__ = "report_versions"
    __table_args__ = (
        Index("ix_rv_report", "report_id"),
        UniqueConstraint("report_id", "version_no", name="uq_rv_no"),
    )

    report_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("reports.id", ondelete="CASCADE"),
        nullable=False,
    )
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[ReportStatus] = mapped_column(
        SAEnum(ReportStatus, name="report_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    author_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    agent_session_id: Mapped[str | None] = mapped_column(String(80), nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # The rendered output
    s3_key: Mapped[str | None] = mapped_column(String(500), nullable=True)
    sha256: Mapped[str | None] = mapped_column(String(64), nullable=True)
    size: Mapped[int | None] = mapped_column(Integer, nullable=True)
    mime: Mapped[str] = mapped_column(String(100), nullable=False, default="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

    # Full draft payload: findings, exec summary, narrative, etc.
    draft_payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    report: Mapped["Report"] = relationship(
        "Report",
        back_populates="versions",
        foreign_keys=[report_id],
    )
