"""Engagement + Scope. An engagement is a single pentest contract; scope
determines which assets are in/out."""

from __future__ import annotations

import uuid
from enum import Enum

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.mixins import Timestamped, UUIDPK


class EngagementStatus(str, Enum):
    PLANNED = "planned"
    ACTIVE = "active"
    IN_REPORTING = "in_reporting"
    DELIVERED = "delivered"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class EngagementType(str, Enum):
    WEBAPP = "webapp"
    NETWORK = "network"
    WIRELESS = "wireless"
    MOBILE = "mobile"
    CLOUD = "cloud"
    REDTEAM = "redteam"
    SOCIAL = "social"
    OTHER = "other"


class Engagement(Base, UUIDPK, Timestamped):
    __tablename__ = "engagements"
    __table_args__ = (
        Index("ix_eng_workspace", "workspace_id"),
        Index("ix_eng_status", "status"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    client: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    type: Mapped[EngagementType] = mapped_column(
        SAEnum(EngagementType, name="engagement_type", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=EngagementType.WEBAPP,
    )
    status: Mapped[EngagementStatus] = mapped_column(
        SAEnum(EngagementStatus, name="engagement_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=EngagementStatus.PLANNED,
    )

    start_date: Mapped["Date | None"] = mapped_column(Date, nullable=True)
    end_date: Mapped["Date | None"] = mapped_column(Date, nullable=True)
    report_due_date: Mapped["Date | None"] = mapped_column(Date, nullable=True)

    # Methodology (OWASP WSTG, PTES, NIST, custom)
    methodology: Mapped[str] = mapped_column(String(40), nullable=False, default="OWASP-WSTG")
    test_types: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    extra: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    # Lead analyst
    lead_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Lock flag: once True, ingestion is frozen (so the report is reproducible)
    ingestion_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    ingestion_locked_at: Mapped[DateTime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="engagements")
    scope_rules: Mapped[list["ScopeRule"]] = relationship(
        "ScopeRule", back_populates="engagement", cascade="all, delete-orphan"
    )


class ScopeRule(Base, UUIDPK, Timestamped):
    """CIDR / hostname / URL pattern rules that determine in-scope assets."""

    __tablename__ = "scope_rules"

    engagement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("engagements.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(30), nullable=False)  # cidr|hostname|url|app
    pattern: Mapped[str] = mapped_column(String(500), nullable=False)
    include: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    note: Mapped[str | None] = mapped_column(String(300), nullable=True)

    engagement: Mapped["Engagement"] = relationship(
        "Engagement", back_populates="scope_rules"
    )
