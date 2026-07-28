"""Ingestion job tracking."""

from __future__ import annotations

import uuid
from enum import Enum

from datetime import datetime
from sqlalchemy import (
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.mixins import Timestamped, UUIDPK, utcnow


class IngestionFormat(str, Enum):
    NESSUS = "nessus"
    NMAP = "nmap"
    BURP = "burp"
    ZAP = "zap"
    NUCLEI = "nuclei"
    OPENVAS = "openvas"
    QUALYS = "qualys"
    TRIVY = "trivy"
    SNYK = "snyk"
    PROWLER = "prowler"
    TESTSSL = "testssl"
    WPSCAN = "wpscan"
    NIKTO = "nikto"
    METASPLOIT = "metasploit"
    AWS_INSPECTOR = "aws_inspector"
    KUBE_BENCH = "kube_bench"
    SARIF = "sarif"
    CYCLONEDX = "cyclonedx"
    SPDX = "spdx"
    LEGACY_DB = "legacy_db"
    UNKNOWN = "unknown"


class IngestionStatus(str, Enum):
    QUEUED = "queued"
    PARSING = "parsing"
    DEDUPING = "deduping"
    DONE = "done"
    FAILED = "failed"
    PARTIAL = "partial"


class IngestionJob(Base, UUIDPK, Timestamped):
    __tablename__ = "ingestion_jobs"
    __table_args__ = (
        Index("ix_ij_workspace", "workspace_id"),
        Index("ix_ij_status", "status"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    engagement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("engagements.id", ondelete="CASCADE"), nullable=False
    )
    submitted_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    source: Mapped[str] = mapped_column(String(40), nullable=False)  # upload | poll | api
    source_filename: Mapped[str | None] = mapped_column(String(400), nullable=True)
    source_s3_key: Mapped[str | None] = mapped_column(String(500), nullable=True)

    format: Mapped[IngestionFormat] = mapped_column(
        SAEnum(IngestionFormat, name="ingestion_format", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=IngestionFormat.UNKNOWN,
    )

    status: Mapped[IngestionStatus] = mapped_column(
        SAEnum(IngestionStatus, name="ingestion_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=IngestionStatus.QUEUED,
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Counts
    raw_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    parsed_items: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    new_vulns: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    merged_vulns: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    new_findings: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_findings: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    regressed_findings: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    remediated_findings: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    log: Mapped[list[dict]] = mapped_column(JSONB, nullable=False, default=list)
