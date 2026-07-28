"""Engagement + scope schemas."""

from __future__ import annotations

from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, Field


class EngagementCreate(BaseModel):
    code: str = Field(min_length=2, max_length=40)
    name: str = Field(min_length=2, max_length=200)
    client: str = Field(min_length=1, max_length=200)
    description: str | None = None
    type: str = "webapp"
    start_date: date | None = None
    end_date: date | None = None
    report_due_date: date | None = None
    methodology: str = "OWASP-WSTG"
    test_types: list[str] = Field(default_factory=list)
    lead_id: UUID | None = None


class EngagementUpdate(BaseModel):
    name: str | None = None
    client: str | None = None
    description: str | None = None
    type: str | None = None
    status: str | None = None
    start_date: date | None = None
    end_date: date | None = None
    report_due_date: date | None = None
    methodology: str | None = None
    test_types: list[str] | None = None
    lead_id: UUID | None = None
    ingestion_locked: bool | None = None


class EngagementOut(BaseModel):
    id: UUID
    workspace_id: UUID
    code: str
    name: str
    client: str
    description: str | None
    type: str
    status: str
    start_date: date | None
    end_date: date | None
    report_due_date: date | None
    methodology: str
    test_types: list[str]
    lead_id: UUID | None
    ingestion_locked: bool
    created_at: datetime
    updated_at: datetime
    severity_breakdown: dict[str, int] | None = None
    findings_total: int | None = None


class ScopeRuleCreate(BaseModel):
    kind: str = Field(pattern=r"^(cidr|hostname|url|app)$")
    pattern: str = Field(min_length=1, max_length=500)
    include: bool = True
    note: str | None = None


class ScopeRuleOut(BaseModel):
    id: UUID
    kind: str
    pattern: str
    include: bool
    note: str | None
