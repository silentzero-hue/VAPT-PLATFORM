"""Workspace = tenant root. All other entities are workspace-scoped."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.mixins import Timestamped, UUIDPK

if TYPE_CHECKING:
    from app.models.engagement import Engagement
    from app.models.user import WorkspaceMembership
    from app.models.asset import Asset
    from app.models.vulnerability import Vulnerability


class Workspace(Base, UUIDPK, Timestamped):
    """Top-level tenant. Org = a company; Workspace = a project/team
    inside that org. All queries MUST be scoped by workspace_id."""

    __tablename__ = "workspaces"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    slug: Mapped[str] = mapped_column(String(60), nullable=False, unique=True, index=True)
    description: Mapped[str | None] = mapped_column(String(500), nullable=True)
    settings: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    default_sla_days: Mapped[dict] = mapped_column(
        JSONB,
        nullable=False,
        default=lambda: {
            "critical": 7,
            "high": 14,
            "medium": 30,
            "low": 60,
            "info": 90,
        },
    )

    engagements: Mapped[list["Engagement"]] = relationship(
        "Engagement", back_populates="workspace", cascade="all, delete-orphan"
    )
    memberships: Mapped[list["WorkspaceMembership"]] = relationship(
        "WorkspaceMembership", back_populates="workspace", cascade="all, delete-orphan"
    )
    assets: Mapped[list["Asset"]] = relationship(
        "Asset", back_populates="workspace", cascade="all, delete-orphan"
    )
    vulnerabilities: Mapped[list["Vulnerability"]] = relationship(
        "Vulnerability", back_populates="workspace", cascade="all, delete-orphan"
    )
