"""Workspace + membership schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class WorkspaceCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    slug: str = Field(min_length=2, max_length=60, pattern=r"^[a-z0-9][a-z0-9-]*$")
    description: str | None = None


class WorkspaceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    description: str | None = None
    default_sla_days: dict[str, int] | None = None
    settings: dict | None = None


class WorkspaceOut(BaseModel):
    id: UUID
    name: str
    slug: str
    description: str | None = None
    default_sla_days: dict = Field(default_factory=dict)
    settings: dict = Field(default_factory=dict)
    created_at: datetime
    updated_at: datetime | None = None


class MembershipCreate(BaseModel):
    user_id: UUID
    role: str = "viewer"


class MembershipUpdate(BaseModel):
    role: str
