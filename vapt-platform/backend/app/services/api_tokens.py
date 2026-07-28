"""API token service. Issue, validate, revoke. Hashed at rest."""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_token
from app.models.api_token import ApiToken


PREFIX_LIVE = "vapt_live_"
PREFIX_TEST = "vapt_test_"


def issue_raw_token(prefix: str = PREFIX_LIVE) -> str:
    return prefix + secrets.token_urlsafe(32)


async def create_token(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    name: str,
    scopes: list[str],
    expires_at: datetime | None,
    actor_id: uuid.UUID | None,
) -> tuple[ApiToken, str]:
    raw = issue_raw_token()
    tok = ApiToken(
        workspace_id=workspace_id,
        name=name,
        created_by=actor_id,
        token_hash=hash_token(raw),
        prefix=raw[:12],
        scopes=scopes,
        expires_at=expires_at,
    )
    db.add(tok)
    await db.flush()
    return tok, raw


async def validate_token(
    db: AsyncSession, raw: str, *, required_scope: str | None = None
) -> ApiToken | None:
    if not raw or not raw.startswith((PREFIX_LIVE, PREFIX_TEST)):
        return None
    h = hash_token(raw)
    tok = await db.scalar(select(ApiToken).where(ApiToken.token_hash == h))
    if not tok or tok.revoked_at:
        return None
    if tok.expires_at and tok.expires_at < datetime.now(timezone.utc):
        return None
    if required_scope and required_scope not in (tok.scopes or []) and "*" not in (tok.scopes or []):
        return None
    tok.use_count = (tok.use_count or 0) + 1
    tok.last_used_at = datetime.now(timezone.utc)
    return tok


async def revoke_token(db: AsyncSession, token_id: uuid.UUID) -> None:
    tok = await db.get(ApiToken, token_id)
    if tok and not tok.revoked_at:
        tok.revoked_at = datetime.now(timezone.utc)
