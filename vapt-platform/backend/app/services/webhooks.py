"""Webhook delivery: HMAC-SHA256 signed, with exponential-backoff retry.

Every delivery is a row in webhook_deliveries for auditability. The
worker (services.worker.deliveries) picks up PENDING rows whose
next_retry_at is in the past and posts them.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.webhook import WebhookDelivery, WebhookEndpoint, WebhookEvent, WebhookStatus

log = get_logger(__name__)

RETRY_BACKOFF = [60, 300, 900, 3600, 21600]  # 1m, 5m, 15m, 1h, 6h
HTTP_TIMEOUT = 15.0


def sign(secret: str, body: bytes, ts: str) -> str:
    mac = hmac.new(secret.encode(), f"{ts}.".encode() + body, hashlib.sha256)
    return mac.hexdigest()


async def enqueue(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    event: WebhookEvent,
    target_type: str | None,
    target_id: uuid.UUID | None,
    payload: dict,
) -> int:
    """Create one WebhookDelivery row per matching endpoint."""
    endpoints = (
        await db.execute(
            select(WebhookEndpoint).where(
                WebhookEndpoint.workspace_id == workspace_id,
                WebhookEndpoint.active.is_(True),
            )
        )
    ).scalars().all()
    n = 0
    for ep in endpoints:
        if not ep.events or (event.value not in ep.events and "*" not in ep.events):
            continue
        d = WebhookDelivery(
            endpoint_id=ep.id,
            workspace_id=workspace_id,
            event=event.value,
            target_type=target_type,
            target_id=target_id,
            payload=payload,
            status=WebhookStatus.PENDING,
        )
        db.add(d)
        n += 1
    await db.flush()
    return n


async def deliver_due(
    db: AsyncSession, batch: int = 25, *,
    endpoint_id: uuid.UUID | None = None,
) -> int:
    """Run a delivery pass. Worker calls this on a cron.

    If ``endpoint_id`` is given, only deliveries for that endpoint are
    processed. Used by the test-fire endpoint to avoid leaking
    cross-tenant deliveries.
    """
    now = datetime.now(timezone.utc)
    stmt = select(WebhookDelivery).where(
        WebhookDelivery.status.in_([WebhookStatus.PENDING, WebhookStatus.FAILED]),
        WebhookDelivery.next_retry_at.is_(None) | (WebhookDelivery.next_retry_at <= now),
    )
    if endpoint_id is not None:
        stmt = stmt.where(WebhookDelivery.endpoint_id == endpoint_id)
    stmt = stmt.limit(batch)
    due = (await db.execute(stmt)).scalars().all()
    sent = 0
    for d in due:
        ok = await _post(db, d)
        if ok:
            sent += 1
    return sent


async def _post(db: AsyncSession, d: WebhookDelivery) -> bool:
    ep = await db.get(WebhookEndpoint, d.endpoint_id)
    if not ep or not ep.active:
        d.status = WebhookStatus.GIVEN_UP
        return False
    body = json.dumps({
        "event": d.event,
        "target_type": d.target_type,
        "target_id": str(d.target_id) if d.target_id else None,
        "data": d.payload,
    }, default=str).encode()
    ts = str(int(datetime.now(timezone.utc).timestamp()))
    sig = sign(ep.secret, body, ts)
    headers = {
        "Content-Type": "application/json",
        "X-VAPT-Signature": f"t={ts},v1={sig}",
        "X-VAPT-Event": d.event,
        "User-Agent": "vapt-platform-webhook/1.0",
    }
    d.attempts = (d.attempts or 0) + 1
    d.last_attempt_at = datetime.now(timezone.utc)
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=False) as c:
            r = await c.post(ep.url, content=body, headers=headers)
        d.response_status = r.status_code
        d.response_body = (r.text or "")[:4000]
        if 200 <= r.status_code < 300:
            d.status = WebhookStatus.SUCCEEDED
            d.delivered_at = datetime.now(timezone.utc)
            ep.failure_count = 0
            ep.last_delivery_at = d.delivered_at
            return True
    except Exception as e:  # noqa: BLE001
        d.response_body = f"error: {e}"
    d.status = WebhookStatus.FAILED
    ep.failure_count = (ep.failure_count or 0) + 1
    if ep.failure_count >= 20:
        ep.active = False
        ep.disabled_at = datetime.now(timezone.utc)
        d.status = WebhookStatus.GIVEN_UP
    else:
        idx = min(d.attempts - 1, len(RETRY_BACKOFF) - 1)
        d.next_retry_at = datetime.now(timezone.utc) + timedelta(seconds=RETRY_BACKOFF[idx])
    return False


def new_secret() -> str:
    return "whsec_" + secrets.token_urlsafe(32)
