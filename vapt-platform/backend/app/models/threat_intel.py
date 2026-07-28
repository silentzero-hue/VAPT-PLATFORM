"""Threat intel cache: CVSS, EPSS, CISA KEV. Refreshed in the background.

One row per (workspace, cve_id). The workspace scoping lets us purge
intel for a deleted tenant without touching other tenants' caches.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.mixins import Timestamped, UUIDPK


class ThreatIntelCache(Base, UUIDPK, Timestamped):
    __tablename__ = "threat_intel_cache"
    __table_args__ = (
        Index("ix_ti_workspace_cve", "workspace_id", "cve_id", unique=True),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("workspaces.id", ondelete="CASCADE"),
        nullable=False,
    )
    cve_id: Mapped[str] = mapped_column(String(40), nullable=False, index=True)

    cvss_v3_vector: Mapped[str | None] = mapped_column(String(120))
    cvss_v3_score: Mapped[float | None] = mapped_column(Float)
    cvss_v2_score: Mapped[float | None] = mapped_column(Float)
    nvd_published: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    nvd_description: Mapped[str | None] = mapped_column(String(2000))
    nvd_references: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)

    epss_score: Mapped[float | None] = mapped_column(Float)
    epss_percentile: Mapped[float | None] = mapped_column(Float)
    epss_updated: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    kev_listed: Mapped[bool] = mapped_column(default=False, nullable=False)
    kev_due_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    kev_added_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    kev_ransomware_use: Mapped[bool] = mapped_column(default=False, nullable=False)

    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    next_refresh_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    fetch_attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_error: Mapped[str | None] = mapped_column(String(500))
