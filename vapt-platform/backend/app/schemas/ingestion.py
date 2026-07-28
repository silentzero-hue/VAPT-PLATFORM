"""Ingestion schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class IngestionUploadResponse(BaseModel):
    job_id: UUID
    filename: str
    size: int
    format_detected: str


class IngestionJobOut(BaseModel):
    id: UUID
    engagement_id: UUID
    source: str
    source_filename: str | None
    format: str
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    raw_items: int
    parsed_items: int
    new_vulns: int
    merged_vulns: int
    new_findings: int
    updated_findings: int
    regressed_findings: int
    remediated_findings: int
    error: str | None
    log: list[dict]
    created_at: datetime
