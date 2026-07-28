"""Comments, retests, evidence, API tokens, webhooks, portal, SBOM,
LDAP, agent feedback routers — one file each for clarity."""

# Comments
from __future__ import annotations
import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.core.db import get_session
from app.models.comment import FindingComment
from app.models.finding import Finding
from app.models.user import Role
from app.services.comments import (
    create_comment, edit as edit_comment, list_for_finding, soft_delete,
)

router = APIRouter(tags=["comments"])


def _check_workspace_scope(current: CurrentUser, workspace_id) -> None:
    if current.role == Role.PLATFORM_ADMIN.value:
        return
    if current.workspace_id != workspace_id:
        raise HTTPException(403, "no access")


class CommentOut(BaseModel):
    id: uuid.UUID
    body: str
    author_id: uuid.UUID | None
    parent_id: uuid.UUID | None
    mentions: list[str]
    created_at: datetime
    edited_at: datetime | None
    deleted: bool


class CommentIn(BaseModel):
    body: str = Field(min_length=1, max_length=10000)
    parent_id: uuid.UUID | None = None


@router.get("/findings/{fid}/comments", response_model=list[CommentOut])
async def list_comments(
    fid: Annotated[uuid.UUID, Path(...)],
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    f = await db.get(Finding, fid)
    if not f:
        raise HTTPException(404, "not found")
    _check_workspace_scope(current, f.workspace_id)
    rows = await list_for_finding(db, fid)
    return [CommentOut(
        id=c.id, body=c.body, author_id=c.author_id, parent_id=c.parent_id,
        mentions=c.mentions, created_at=c.created_at, edited_at=c.edited_at,
        deleted=c.deleted_at is not None,
    ) for c in rows]


@router.post("/findings/{fid}/comments", response_model=CommentOut, status_code=201)
async def post_comment(
    fid: Annotated[uuid.UUID, Path(...)], body: CommentIn,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    f = await db.get(Finding, fid)
    if not f:
        raise HTTPException(404, "not found")
    _check_workspace_scope(current, f.workspace_id)
    c = await create_comment(
        db, finding_id=fid, author_id=current.user.id,
        body=body.body, parent_id=body.parent_id,
    )
    return CommentOut(
        id=c.id, body=c.body, author_id=c.author_id, parent_id=c.parent_id,
        mentions=c.mentions, created_at=c.created_at, edited_at=c.edited_at,
        deleted=False,
    )


@router.patch("/comments/{cid}", response_model=CommentOut)
async def edit_one(
    cid: Annotated[uuid.UUID, Path(...)], body: CommentIn,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    c = await db.get(FindingComment, cid)
    if not c:
        raise HTTPException(404, "not found")
    _check_workspace_scope(current, c.workspace_id)
    if c.author_id != current.user.id:
        raise HTTPException(403, "only the author can edit")
    await edit_comment(db, cid, body.body)
    return CommentOut(
        id=c.id, body=c.body, author_id=c.author_id, parent_id=c.parent_id,
        mentions=c.mentions, created_at=c.created_at, edited_at=c.edited_at,
        deleted=False,
    )


@router.delete("/comments/{cid}", status_code=204)
async def delete_one(
    cid: Annotated[uuid.UUID, Path(...)],
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    c = await db.get(FindingComment, cid)
    if not c:
        raise HTTPException(404, "not found")
    _check_workspace_scope(current, c.workspace_id)
    if c.author_id != current.user.id and current.role not in (Role.PLATFORM_ADMIN.value, Role.ADMIN.value):
        raise HTTPException(403, "forbidden")
    await soft_delete(db, cid)
