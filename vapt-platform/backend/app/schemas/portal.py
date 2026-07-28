"""Client portal share schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class PortalShareOut(BaseModel):
    id: UUID
    workspace_id: UUID
    report_id: UUID
    token: str
    created_at: datetime
    expires_at: datetime | None
    max_views: int | None
    current_views: int
    require_password: bool
    allowed_emails: list[str]
    watermark_with_viewer: bool
