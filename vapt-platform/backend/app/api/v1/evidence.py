"""Evidence + API tokens routers."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, Path, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ADMIN_ROLES, ANALYST_ROLES, CurrentUser, get_current_user
from app.core.db import get_session
from app.models.evidence_blob import EvidenceBlob
from app.models.finding import Finding, FindingEvidence
from app.models.api_token import ApiToken
from app.models.user import Role
from app.services.evidence.store import upload as upload_blob
from app.services.api_tokens import create_token, revoke_token

router = APIRouter(tags=["evidence"])

MAX_EVIDENCE_BYTES = 50 * 1024 * 1024


def _enforce_size_cap(request: Request) -> None:
    cl = request.headers.get("content-length")
    if cl and cl.isdigit() and int(cl) > MAX_EVIDENCE_BYTES:
        raise HTTPException(413, "file too large")


def _check_workspace_scope(current: CurrentUser, workspace_id) -> None:
    if current.role == Role.PLATFORM_ADMIN.value:
        return
    if current.workspace_id != workspace_id:
        raise HTTPException(403, "no access")


@router.post("/findings/{fid}/evidence", status_code=201)
async def upload_evidence(
    request: Request,
    fid: Annotated[uuid.UUID, Path(...)],
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
    file: UploadFile = File(...),
    kind: str = Form(default="screenshot"),
    note: str | None = Form(default=None),
):
    _enforce_size_cap(request)
    if current.role not in (Role.PLATFORM_ADMIN.value, *ANALYST_ROLES):
        raise HTTPException(403, "forbidden")
    f = await db.get(Finding, fid)
    if not f:
        raise HTTPException(404, "finding not found")
    _check_workspace_scope(current, f.workspace_id)
    data = await file.read()
    blob = await upload_blob(
        db, workspace_id=f.workspace_id, actor_id=current.user.id,
        data=data, mime=file.content_type or "application/octet-stream",
        kind=kind, filename=file.filename or "upload.bin",
    )
    fe = FindingEvidence(
        finding_id=f.id, evidence_blob_id=blob.id, kind=kind,
        filename=file.filename or "upload.bin", note=note,
    )
    db.add(fe)
    await db.flush()
    return {"id": str(fe.id), "blob_id": str(blob.id), "size": blob.size}


@router.get("/evidence/{eid}")
async def get_evidence(
    eid: Annotated[uuid.UUID, Path(...)],
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    fe = await db.get(FindingEvidence, eid)
    if not fe or not fe.evidence_blob_id:
        raise HTTPException(404, "not found")
    f = await db.get(Finding, fe.finding_id)
    if not f:
        raise HTTPException(404, "not found")
    _check_workspace_scope(current, f.workspace_id)
    blob = await db.get(EvidenceBlob, fe.evidence_blob_id)
    if not blob:
        raise HTTPException(404, "blob not found")
    return {
        "id": str(fe.id), "filename": fe.filename, "kind": fe.kind,
        "sha256": blob.sha256, "size": blob.size, "mime": blob.mime,
        "ref_count": blob.ref_count, "s3_key": blob.s3_key, "note": fe.note,
    }


# ---------------------------------------------------------------------------
# API tokens
# ---------------------------------------------------------------------------
tokens_router = APIRouter(prefix="/workspaces/{wid}/tokens", tags=["api-tokens"])


class TokenOut(BaseModel):
    id: uuid.UUID
    name: str
    prefix: str
    scopes: list[str]
    expires_at: datetime | None
    created_at: datetime
    last_used_at: datetime | None
    use_count: int
    revoked: bool


class TokenCreate(BaseModel):
    name: str = Field(min_length=2, max_length=120)
    scopes: list[str] = Field(default_factory=lambda: ["*"])
    expires_at: datetime | None = None


@tokens_router.get("", response_model=list[TokenOut])
async def list_tok(
    wid: Annotated[uuid.UUID, Path(...)],
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    _check_workspace_scope(current, wid)
    rows = (await db.execute(
        select(ApiToken).where(ApiToken.workspace_id == wid)
        .order_by(ApiToken.created_at.desc())
    )).scalars().all()
    return [TokenOut(
        id=t.id, name=t.name, prefix=t.prefix, scopes=t.scopes or [],
        expires_at=t.expires_at, created_at=t.created_at,
        last_used_at=t.last_used_at, use_count=t.use_count,
        revoked=t.revoked_at is not None,
    ) for t in rows]


@tokens_router.post("", status_code=201)
async def issue_tok(
    wid: Annotated[uuid.UUID, Path(...)], body: TokenCreate,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    _check_workspace_scope(current, wid)
    tok, raw = await create_token(
        db, workspace_id=wid, name=body.name, scopes=body.scopes,
        expires_at=body.expires_at, actor_id=current.user.id,
    )
    # The raw token is shown ONCE. Caller must store it.
    return {
        "id": str(tok.id), "name": tok.name, "prefix": tok.prefix,
        "scopes": tok.scopes, "expires_at": tok.expires_at,
        "raw_token": raw,
        "warning": "Save this token now — it cannot be retrieved later.",
    }


@tokens_router.delete("/{tid}", status_code=204)
async def revoke_tok(
    wid: Annotated[uuid.UUID, Path(...)],
    tid: Annotated[uuid.UUID, Path(...)],
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    _check_workspace_scope(current, wid)
    await revoke_token(db, tid)
