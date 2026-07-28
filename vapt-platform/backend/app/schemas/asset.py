"""Asset schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class AssetCreate(BaseModel):
    type: str = "host"
    value: str = Field(min_length=1, max_length=500)
    port: int | None = Field(default=None, ge=0, le=65535)
    protocol: str | None = None
    fqdn: str | None = None
    ip: str | None = None
    environment: str | None = None
    criticality: str = "medium"
    owner: str | None = None
    business_unit: str | None = None
    tags: list[str] = Field(default_factory=list)


class AssetUpdate(BaseModel):
    criticality: str | None = None
    owner: str | None = None
    business_unit: str | None = None
    environment: str | None = None
    tags: list[str] | None = None
    extra: dict | None = None


class AssetOut(BaseModel):
    id: UUID
    type: str
    value: str
    port: int | None
    protocol: str | None
    fqdn: str | None
    ip: str | None
    environment: str | None
    criticality: str
    owner: str | None
    business_unit: str | None
    tags: list[str]
    first_seen: datetime
    last_seen: datetime
    findings_count: int | None = None
