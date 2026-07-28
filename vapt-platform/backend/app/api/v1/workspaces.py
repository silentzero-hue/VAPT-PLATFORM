"""Workspaces + memberships router.

SECURITY: every workspace-scoped handler enforces that the caller's
`current.workspace_id` matches the `workspace_id` in the URL. The
`role in ADMIN_ROLES` shortcut is removed — only `platform_admin` can act
across workspaces.
"""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Path, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user, require_role
from app.core.db import get_session
from app.core.logging import get_logger
from app.models.user import AuditLog, Role, User, WorkspaceMembership
from app.models.workspace import Workspace
from app.schemas.workspace import (
    MembershipCreate,
    MembershipUpdate,
    WorkspaceCreate,
    WorkspaceOut,
    WorkspaceUpdate,
)

router = APIRouter(prefix="/workspaces", tags=["workspaces"])
log = get_logger(__name__)


def _check_workspace_scope(current: CurrentUser, workspace_id: UUID) -> None:
    """Raise 403 if the caller cannot access this workspace.

    Only `platform_admin` may act across workspaces. A workspace `admin`
    is restricted to their own workspace.
    """
    if current.role == Role.PLATFORM_ADMIN.value:
        return
    if current.workspace_id != workspace_id:
        raise HTTPException(403, "no access")


@router.post("", response_model=WorkspaceOut, status_code=201)
async def create_workspace(
    body: WorkspaceCreate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(require_role(Role.PLATFORM_ADMIN.value))],
):
    if await db.scalar(select(Workspace).where(Workspace.slug == body.slug)):
        raise HTTPException(409, "slug exists")
    ws = Workspace(name=body.name, slug=body.slug, description=body.description)
    db.add(ws)
    await db.flush()
    db.add(WorkspaceMembership(user_id=current.user.id, workspace_id=ws.id, role=Role.ADMIN.value))
    db.add(AuditLog(
        actor_id=current.user.id, actor_role=current.role, action="workspace.create",
        target_type="workspace", target_id=ws.id,
        ip=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    ))
    return WorkspaceOut(
        id=ws.id, name=ws.name, slug=ws.slug, description=ws.description,
        default_sla_days=ws.default_sla_days, created_at=ws.created_at,
    )


@router.get("", response_model=list[WorkspaceOut])
async def list_workspaces(
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    if current.role == Role.PLATFORM_ADMIN.value:
        ws_list = (await db.execute(select(Workspace))).scalars().all()
    else:
        ws_list = (
            await db.execute(
                select(Workspace).join(WorkspaceMembership).where(
                    WorkspaceMembership.user_id == current.user.id
                )
            )
        ).scalars().all()
    return [
        WorkspaceOut(
            id=w.id, name=w.name, slug=w.slug, description=w.description,
            default_sla_days=w.default_sla_days, created_at=w.created_at,
        )
        for w in ws_list
    ]


@router.get("/{workspace_id}", response_model=WorkspaceOut)
async def get_workspace(
    workspace_id: Annotated[UUID, Path(...)],
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    _check_workspace_scope(current, workspace_id)
    w = await db.get(Workspace, workspace_id)
    if not w:
        raise HTTPException(404, "not found")
    return WorkspaceOut(
        id=w.id, name=w.name, slug=w.slug, description=w.description,
        default_sla_days=w.default_sla_days, created_at=w.created_at,
    )


@router.patch("/{workspace_id}", response_model=WorkspaceOut)
async def update_workspace(
    workspace_id: Annotated[UUID, Path(...)],
    body: WorkspaceUpdate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    _check_workspace_scope(current, workspace_id)
    w = await db.get(Workspace, workspace_id)
    if not w:
        raise HTTPException(404, "not found")
    # SECURITY: only allow updating fields explicitly whitelisted in the schema.
    # The free-form setattr was a footgun that allowed callers to write any
    # column (e.g. id, created_at).
    allowed_fields = {"name", "slug", "description", "default_sla_days"}
    for k, v in body.model_dump(exclude_unset=True).items():
        if k not in allowed_fields:
            log.warning("workspace.update.ignored_field", field=k)
            continue
        setattr(w, k, v)
    db.add(AuditLog(
        workspace_id=w.id, actor_id=current.user.id, actor_role=current.role,
        action="workspace.update", target_type="workspace", target_id=w.id,
        ip=request.client.host if request.client else None,
    ))
    return WorkspaceOut(
        id=w.id, name=w.name, slug=w.slug, description=w.description,
        default_sla_days=w.default_sla_days, created_at=w.created_at,
    )


@router.post("/{workspace_id}/members", status_code=201)
async def add_member(
    workspace_id: Annotated[UUID, Path(...)],
    body: MembershipCreate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    _check_workspace_scope(current, workspace_id)
    if not await db.get(User, body.user_id):
        raise HTTPException(404, "user not found")
    if not await db.get(Workspace, workspace_id):
        raise HTTPException(404, "workspace not found")
    existing = await db.scalar(
        select(WorkspaceMembership).where(
            WorkspaceMembership.user_id == body.user_id,
            WorkspaceMembership.workspace_id == workspace_id,
        )
    )
    if existing:
        raise HTTPException(409, "already a member")
    db.add(WorkspaceMembership(
        user_id=body.user_id, workspace_id=workspace_id, role=body.role,
    ))
    db.add(AuditLog(
        workspace_id=workspace_id, actor_id=current.user.id, actor_role=current.role,
        action="workspace.add_member", target_type="user", target_id=body.user_id,
        ip=request.client.host if request.client else None,
    ))
    return {"ok": True}


@router.patch("/{workspace_id}/members/{user_id}")
async def update_member(
    workspace_id: Annotated[UUID, Path(...)],
    user_id: UUID,
    body: MembershipUpdate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    _check_workspace_scope(current, workspace_id)
    # Only workspace admins (or platform_admin) can change membership roles.
    if current.role not in (Role.PLATFORM_ADMIN.value, Role.ADMIN.value):
        raise HTTPException(403, "admin only")
    mem = await db.scalar(
        select(WorkspaceMembership).where(
            WorkspaceMembership.user_id == user_id,
            WorkspaceMembership.workspace_id == workspace_id,
        )
    )
    if not mem:
        raise HTTPException(404, "not a member")
    mem.role = body.role
    db.add(AuditLog(
        workspace_id=workspace_id, actor_id=current.user.id, actor_role=current.role,
        action="workspace.update_member", target_type="user", target_id=user_id,
        extra={"new_role": body.role},
        ip=request.client.host if request.client else None,
    ))
    return {"ok": True}


@router.delete("/{workspace_id}/members/{user_id}", status_code=204)
async def remove_member(
    workspace_id: Annotated[UUID, Path(...)],
    user_id: UUID,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    _check_workspace_scope(current, workspace_id)
    if current.role not in (Role.PLATFORM_ADMIN.value, Role.ADMIN.value):
        raise HTTPException(403, "admin only")
    mem = await db.scalar(
        select(WorkspaceMembership).where(
            WorkspaceMembership.user_id == user_id,
            WorkspaceMembership.workspace_id == workspace_id,
        )
    )
    if not mem:
        raise HTTPException(404, "not a member")
    await db.delete(mem)
    db.add(AuditLog(
        workspace_id=workspace_id, actor_id=current.user.id, actor_role=current.role,
        action="workspace.remove_member", target_type="user", target_id=user_id,
        ip=request.client.host if request.client else None,
    ))
