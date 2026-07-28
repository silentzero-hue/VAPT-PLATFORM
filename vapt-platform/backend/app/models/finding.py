"""Finding = the JOIN between one Vulnerability and one Asset (in one
engagement). A vulnerability is unique; a finding is the per-asset
manifestation of that vulnerability. This is the table that proves the
spec's central claim: 'same vuln across many hosts' is ONE vulnerability
row + N findings, not N vulnerability rows."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Date,
    DateTime,
    Enum as SAEnum,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.mixins import Timestamped, UUIDPK, utcnow


class FindingStatus(str, Enum):
    """Triage lifecycle. New → Confirmed → In Remediation → Resolved.
    Retest flow: Resolved → Regressed (re-detected) or stays Resolved.
    False positive tracks intentional rejections."""

    NEW = "new"
    CONFIRMED = "confirmed"
    IN_REMEDIATION = "in_remediation"
    RESOLVED = "resolved"
    RESOLVED_PENDING_CONFIRMATION = "remediated_pending_confirmation"
    REGRESSED = "regressed"
    FALSE_POSITIVE = "false_positive"
    ACCEPTED_RISK = "accepted_risk"
    DEFERRED = "deferred"


class Finding(Base, UUIDPK, Timestamped):
    """One row per (vulnerability, asset, port, engagement) tuple."""

    __tablename__ = "findings"
    __table_args__ = (
        # Same vuln on same asset in same engagement should be one row.
        UniqueConstraint(
            "vulnerability_id",
            "asset_id",
            "engagement_id",
            "port",
            name="uq_finding_unique",
        ),
        Index("ix_find_workspace", "workspace_id"),
        Index("ix_find_engagement", "engagement_id"),
        Index("ix_find_vuln", "vulnerability_id"),
        Index("ix_find_status", "status"),
    )

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    engagement_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("engagements.id", ondelete="CASCADE"),
        nullable=False,
    )
    vulnerability_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("vulnerabilities.id", ondelete="CASCADE"),
        nullable=False,
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("assets.id", ondelete="CASCADE"), nullable=False
    )

    port: Mapped[int | None] = mapped_column(Integer, nullable=True)
    protocol: Mapped[str | None] = mapped_column(String(20), nullable=True)
    evidence_ref: Mapped[str | None] = mapped_column(
        Text, nullable=True
    )  # pointer to MinIO evidence blob
    request: Mapped[str | None] = mapped_column(Text, nullable=True)
    response: Mapped[str | None] = mapped_column(Text, nullable=True)
    raw_output: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Per-finding overrides; per-vuln is the default
    severity_override: Mapped[str | None] = mapped_column(String(20), nullable=True)
    cvss_score_override: Mapped[float | None] = mapped_column(Float, nullable=True)

    # Risk score: composite of severity, asset criticality, EPSS, KEV.
    # 0..100. Recomputed on retest / threat-intel refresh.
    risk_score: Mapped[float | None] = mapped_column(Float, nullable=True, index=True)
    risk_components: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    status: Mapped[FindingStatus] = mapped_column(
        SAEnum(FindingStatus, name="finding_status", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=FindingStatus.NEW,
        index=True,
    )

    # Threat intel link (filled by the enrichment job; NULL if no CVE).
    threat_intel_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("threat_intel_cache.id", ondelete="SET NULL"),
        nullable=True,
    )

    # Effective severity = override OR inherited from vulnerability
    @property
    def effective_severity(self) -> str:
        return self.severity_override or self.vulnerability.severity.value

    # SLA
    sla_due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    sla_breached: Mapped[bool] = mapped_column(default=False, nullable=False)

    first_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    last_seen: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    resolution_note: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Analyst assignments
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    extra: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)

    vulnerability: Mapped["Vulnerability"] = relationship(
        "Vulnerability", back_populates="findings"
    )
    asset: Mapped["Asset"] = relationship("Asset")
    activity: Mapped[list["FindingActivity"]] = relationship(
        "FindingActivity",
        back_populates="finding",
        cascade="all, delete-orphan",
        order_by="FindingActivity.created_at",
    )
    evidence: Mapped[list["FindingEvidence"]] = relationship(
        "FindingEvidence",
        back_populates="finding",
        cascade="all, delete-orphan",
    )


class FindingActivity(Base, UUIDPK, Timestamped):
    """Append-only status / comment / assignment changes."""

    __tablename__ = "finding_activity"
    __table_args__ = (Index("ix_fact_finding", "finding_id"),)

    finding_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("findings.id", ondelete="CASCADE"),
        nullable=False,
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    # free-form detail like severity override, status change, comment body
    detail: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)

    finding: Mapped["Finding"] = relationship("Finding", back_populates="activity")


class FindingEvidence(Base, UUIDPK, Timestamped):
    """Pointer to evidence blob in MinIO. The actual bytes live in
    evidence_blobs (content-addressed) so the same SHA-256 is stored once."""

    __tablename__ = "finding_evidence"
    __table_args__ = (Index("ix_fev_finding", "finding_id"),)

    finding_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("findings.id", ondelete="CASCADE"),
        nullable=False,
    )
    evidence_blob_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("evidence_blobs.id", ondelete="SET NULL"),
        nullable=True,
    )
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    filename: Mapped[str] = mapped_column(String(400), nullable=False)
    note: Mapped[str | None] = mapped_column(String(400), nullable=True)

    finding: Mapped["Finding"] = relationship("Finding", back_populates="evidence")
    blob: Mapped["EvidenceBlob"] = relationship("EvidenceBlob")
