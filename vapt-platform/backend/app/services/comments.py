"""Finding comment service: @mentions, threading, edit history."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Iterable

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.comment import CommentMention, FindingComment
from app.models.finding import Finding
from app.models.user import User
from app.models.notification import Notification, NotificationKind

log = get_logger(__name__)

MENTION_RE = re.compile(r"@([a-zA-Z0-9._+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})")


def extract_mentions(body: str) -> list[str]:
    return list({m.group(1).lower() for m in MENTION_RE.finditer(body or "")})


async def create_comment(
    db: AsyncSession,
    *,
    finding_id: uuid.UUID,
    author_id: uuid.UUID,
    body: str,
    parent_id: uuid.UUID | None = None,
) -> FindingComment:
    f = await db.get(Finding, finding_id)
    if not f:
        raise ValueError("finding not found")
    mentions = extract_mentions(body)
    c = FindingComment(
        finding_id=finding_id,
        workspace_id=f.workspace_id,
        parent_id=parent_id,
        author_id=author_id,
        body=body,
        mentions=mentions,
    )
    db.add(c)
    await db.flush()
    # resolve @mentioned emails to user IDs and create CommentMention rows
    if mentions:
        users = (await db.execute(
            select(User).where(User.email.in_(mentions))
        )).scalars().all()
        for u in users:
            db.add(CommentMention(comment_id=c.id, user_id=u.id))
            db.add(Notification(
                workspace_id=f.workspace_id, user_id=u.id,
                kind=NotificationKind.MENTION,
                title=f"You were mentioned in a comment",
                body=body[:500],
                target_type="finding", target_id=f.id,
                extra={"comment_id": str(c.id)},
            ))
    return c


async def list_for_finding(
    db: AsyncSession, finding_id: uuid.UUID, *, include_deleted: bool = False
) -> list[FindingComment]:
    q = select(FindingComment).where(FindingComment.finding_id == finding_id)
    if not include_deleted:
        q = q.where(FindingComment.deleted_at.is_(None))
    return (await db.execute(q.order_by(FindingComment.created_at))).scalars().all()


async def edit(db: AsyncSession, comment_id: uuid.UUID, body: str) -> FindingComment:
    c = await db.get(FindingComment, comment_id)
    if not c:
        raise ValueError("not found")
    c.body = body
    c.edited_at = datetime.now(timezone.utc)
    c.mentions = extract_mentions(body)
    return c


async def soft_delete(db: AsyncSession, comment_id: uuid.UUID) -> None:
    c = await db.get(FindingComment, comment_id)
    if c and not c.deleted_at:
        c.deleted_at = datetime.now(timezone.utc)
        c.body = "[deleted]"
