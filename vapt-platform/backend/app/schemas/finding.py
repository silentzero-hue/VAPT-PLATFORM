"""Finding schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class FindingOut(BaseModel):
    id: UUID
    workspace_id: UUID
    engagement_id: UUID
    vulnerability_id: UUID
    asset_id: UUID
    port: int | None
    protocol: str | None
    evidence_ref: str | None
    status: str
    severity: str
    effective_severity: str
    cvss_score: float | None
    risk_score: float | None = None
    risk_components: dict = Field(default_factory=dict)
    sla_due_at: datetime | None
    sla_breached: bool
    first_seen: datetime
    last_seen: datetime
    resolved_at: datetime | None
    assigned_to: UUID | None
    # convenience fields
    asset_value: str | None = None
    asset_type: str | None = None
    vuln_title: str | None = None
    vuln_cve_id: str | None = None


class FindingUpdate(BaseModel):
    status: str | None = None
    severity_override: str | None = None
    cvss_score_override: float | None = None
    resolution_note: str | None = None
    assigned_to: UUID | None = None
    extra: dict | None = None


class FindingActivityOut(BaseModel):
    id: UUID
    action: str
    actor_id: UUID | None
    detail: dict
    comment: str | None
    created_at: datetime


class FindingEvidenceOut(BaseModel):
    id: UUID
    kind: str
    filename: str
    mime: str
    size: int
    sha256: str
    note: str | None
    created_at: datetime
    download_url: str | None = None


class TriageAction(BaseModel):
    action: str = Field(
        pattern=r"^(confirm|reject|mark_remediated|mark_in_remediation|accept_risk|defer|reassign|comment)$"
    )
    comment: str | None = None
    severity_override: str | None = None
    assigned_to: UUID | None = None


class BulkTriageRequest(BaseModel):
    finding_ids: list[UUID]
    action: TriageAction
