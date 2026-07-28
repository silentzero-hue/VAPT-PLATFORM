"""Nessus server connection. One per workspace. The credentials are
stored encrypted (Fernet with a key derived from JWT_SECRET) and used
by the Nessus API client to pull live scans.

Note: this is the same pattern as the legacy .env (NESSUS_BASE_URL /
NESSUS_ACCESS_KEY / NESSUS_SECRET_KEY), but per-workspace so multiple
clients can each have their own Nessus instance.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Index, Integer, String, Text, func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.mixins import Timestamped, UUIDPK


class NessusServer(Base, UUIDPK, Timestamped):
    __tablename__ = "nessus_servers"
    __table_args__ = (Index("ix_ns_workspace", "workspace_id", unique=True),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    base_url: Mapped[str] = mapped_column(String(500), nullable=False)
    access_key_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    secret_key_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    verify_ssl: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    request_timeout: Mapped[int] = mapped_column(Integer, nullable=False, default=30)
    max_concurrency: Mapped[int] = mapped_column(Integer, nullable=False, default=5)
    only_completed_scans: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_sync_status: Mapped[str | None] = mapped_column(String(40))
    last_sync_error: Mapped[str | None] = mapped_column(Text)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


class NessusScanCache(Base, UUIDPK, Timestamped):
    """Cached scan listing from a Nessus server. Refreshed on demand."""

    __tablename__ = "nessus_scan_cache"
    __table_args__ = (
        Index("ix_nsc_server_scan", "server_id", "scan_id", unique=True),
        Index("ix_nsc_created_at_meta", "created_at_meta"),
    )

    server_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("nessus_servers.id", ondelete="CASCADE"), nullable=False
    )
    scan_id: Mapped[int] = mapped_column(Integer, nullable=False)
    name: Mapped[str] = mapped_column(String(400), nullable=False)
    status: Mapped[str] = mapped_column(String(40), nullable=False)  # completed|running|...
    policy: Mapped[str | None] = mapped_column(String(200), nullable=True)
    scan_type: Mapped[str | None] = mapped_column(String(40), nullable=True)
    target: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at_meta: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class MultiScanJob(Base, UUIDPK, Timestamped):
    """A multi-scan comparison run. The legacy tool was famous for this:
    you scan the same scope on N dates, then ask 'what's new, what's
    fixed, what's regressed' between any two scans."""

    __tablename__ = "multi_scan_jobs"
    __table_args__ = (Index("ix_msj_workspace", "workspace_id"),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    engagement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # JSON list of IngestionJob IDs (or scan refs) in chronological order.
    # The analyzer resolves them into Finding sets on demand.
    scan_ingestion_ids: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    baseline_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
