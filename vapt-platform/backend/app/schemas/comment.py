"""Finding comment schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class CommentOut(BaseModel):
    id: UUID
    finding_id: UUID
    author_id: UUID | None
    body: str
    parent_id: UUID | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
