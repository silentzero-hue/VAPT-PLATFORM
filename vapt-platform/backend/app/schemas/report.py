"""Report + render schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field

Severity = Literal["critical", "high", "medium", "low", "info"]


class ReportCreate(BaseModel):
    engagement_id: UUID
    template_id: UUID | None = None
    title: str | None = None


class ReportOut(BaseModel):
    id: UUID
    workspace_id: UUID | None = None
    engagement_id: UUID
    template_id: UUID | None = None
    title: str
    status: str
    current_version_id: UUID | None = None
    signed_sha256: str | None = None
    signed_at: datetime | None = None
    signed_by: UUID | None = None
    locked: bool = False
    locked_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    draft_payload: dict = Field(default_factory=dict)
    versions: list["ReportVersionOut"] = []


class ReportVersionOut(BaseModel):
    id: UUID
    version_no: int
    status: str
    author_id: UUID | None
    agent_session_id: str | None
    note: str | None
    s3_key: str | None
    sha256: str | None
    size: int | None
    created_at: datetime


class RenderRequest(BaseModel):
    template_id: UUID | None = None
    note: str | None = None
    # allow the analyst to override AI draft before rendering
    overrides: dict | None = None


class ReportApproveRequest(BaseModel):
    version_id: UUID | None = None
    note: str | None = None


class FindingEdit(BaseModel):
    """Per-finding override applied at render time.

    All fields are optional; only the ones the analyst set are merged
    into the draft payload. To clear a previously-set value, the
    frontend should send `null` (which Pydantic will then carry through
    and the merge step will treat as "remove").
    """
    finding_id: UUID
    severity_override: Severity | None = None
    impact: str | None = None
    recommendation: str | None = None
    note: str | None = None


class ReportEditRequest(BaseModel):
    """PATCH /reports/{rid} body."""
    title: str | None = None
    overall_rating: Severity | None = None
    exec_summary: str | None = None
    findings: list[FindingEdit] | None = None


# ---------------------------------------------------------------------------
# Suggestion schemas (auto-fill support for the report editor)
# ---------------------------------------------------------------------------

class FindingSuggestion(BaseModel):
    """One auto-generated suggestion block for a single finding."""
    finding_id: UUID
    impact: str
    recommendation: str
    action_urgency: str
    category: str


class SuggestRequest(BaseModel):
    """POST /reports/{rid}/suggest/bulk body.

    Either `finding_ids` (process these specific findings) or `category`
    (process all findings in the report whose detected category matches)
    must be provided. `severity_overrides` is an optional per-finding
    override map used to compute the suggestion text.
    """
    finding_ids: list[UUID] | None = None
    category: str | None = None
    severity_overrides: dict[str, Severity] = Field(default_factory=dict)


class SuggestResponse(BaseModel):
    """Map of finding_id -> suggestion. Findings not found in the
    workspace are silently skipped."""
    suggestions: dict[str, FindingSuggestion] = Field(default_factory=dict)


ReportOut.model_rebuild()
