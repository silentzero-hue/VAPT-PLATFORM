"""Webhook endpoint + delivery schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class WebhookEndpointOut(BaseModel):
    id: UUID
    workspace_id: UUID
    name: str
    url: str
    events: list[str]
    active: bool
    created_at: datetime


class WebhookDeliveryOut(BaseModel):
    id: UUID
    workspace_id: UUID
    endpoint_id: UUID
    event: str
    payload: dict
    status: str
    response_status: int | None
    attempt: int
    last_error: str | None
    created_at: datetime
    delivered_at: datetime | None
