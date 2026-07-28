"""Threat intel cache schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class ThreatIntelOut(BaseModel):
    cve_id: str
    cvss_v3_score: float | None
    cvss_v3_vector: str | None
    epss_score: float | None
    epss_percentile: float | None
    kev_listed: bool
    kev_due_date: datetime | None
    kev_ransomware_use: bool
    fetched_at: datetime
    next_refresh_after: datetime
