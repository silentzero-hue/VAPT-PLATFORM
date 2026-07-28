"""Asset model — anything that can have a finding attached to it."""

from __future__ import annotations

import uuid
from enum import Enum

from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.mixins import Timestamped, UUIDPK


class AssetType(str, Enum):
    HOST = "host"
    DOMAIN = "domain"
    URL = "url"
    APP = "app"
    IP = "ip"
    SERVICE = "service"
    REPO = "repo"
    PERSON = "person"
    OTHER = "other"


class AssetCriticality(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Asset(Base, UUIDPK, Timestamped):
    """A discoverable/scanned target. Deduped by (workspace, type, value, port?)."""

    __tablename__ = "assets"
    __table_args__ = (
        Index(
            "uq_asset_per_workspace",
            "workspace_id",
            "type",
            "value",
            "port",
            unique=True,
        ),
        Index("ix_asset_workspace", "workspace_id"),
        Index("ix_asset_value", "value"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[AssetType] = mapped_column(
        SAEnum(AssetType, name="asset_type", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
    )
    value: Mapped[str] = mapped_column(String(500), nullable=False)
    port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    protocol: Mapped[str | None] = mapped_column(String(20), nullable=True)  # tcp/udp
    fqdn: Mapped[str | None] = mapped_column(String(500), nullable=True, index=True)
    ip: Mapped[str | None] = mapped_column(INET, nullable=True, index=True)

    # Asset classification
    environment: Mapped[str | None] = mapped_column(String(40), nullable=True)  # prod/stage/dev
    criticality: Mapped[AssetCriticality] = mapped_column(
        SAEnum(AssetCriticality, name="asset_criticality", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=AssetCriticality.MEDIUM,
    )
    owner: Mapped[str | None] = mapped_column(String(200), nullable=True)
    business_unit: Mapped[str | None] = mapped_column(String(200), nullable=True)
    tags: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)
    extra: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    first_seen: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_seen: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    workspace: Mapped["Workspace"] = relationship("Workspace", back_populates="assets")
