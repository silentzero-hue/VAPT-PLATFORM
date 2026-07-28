"""Tests for the cross-workspace access enforcement helper.

The legacy `role in ADMIN_ROLES` shortcut was a P0 audit finding: it let
a workspace `admin` in workspace A mutate resources in workspace B. These
tests pin down the correct semantics: ONLY `platform_admin` may act
cross-workspace; everyone else must match the workspace AND have an
appropriate role.

These tests are pure (no DB) — they exercise the helper directly with
duck-typed stand-ins.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.deps import check_workspace_scope_or_admin
from app.models.user import Role


def _cu(role: str, workspace_id: uuid.UUID | None) -> SimpleNamespace:
    """Duck-typed CurrentUser stand-in. The helper only reads .role and
    .workspace_id so we don't need a real DB-backed User."""
    return SimpleNamespace(role=role, workspace_id=workspace_id)


def test_platform_admin_passes_any_workspace():
    pa = _cu(Role.PLATFORM_ADMIN.value, workspace_id=None)
    # No role gate: any workspace id is fine.
    check_workspace_scope_or_admin(pa, uuid.uuid4())


def test_platform_admin_passes_with_role_gate_too():
    pa = _cu(Role.PLATFORM_ADMIN.value, workspace_id=None)
    # Even if required_roles is set, platform_admin still short-circuits.
    check_workspace_scope_or_admin(
        pa, uuid.uuid4(), required_roles={Role.ANALYST.value}
    )


def test_workspace_admin_in_same_workspace_passes():
    wid = uuid.uuid4()
    admin = _cu(Role.ADMIN.value, workspace_id=wid)
    check_workspace_scope_or_admin(admin, wid, required_roles={Role.ADMIN.value})


def test_workspace_admin_in_other_workspace_blocked():
    """The P0 bug: a workspace admin from workspace A must NOT be allowed
    to act in workspace B just because they hold the admin role somewhere."""
    wid_a = uuid.uuid4()
    wid_b = uuid.uuid4()
    admin_a = _cu(Role.ADMIN.value, workspace_id=wid_a)
    with pytest.raises(HTTPException) as exc:
        check_workspace_scope_or_admin(
            admin_a, wid_b, required_roles={Role.ADMIN.value}
        )
    assert exc.value.status_code == 403
    assert "cross-workspace" in exc.value.detail


def test_workspace_senior_analyst_in_other_workspace_blocked():
    wid_a = uuid.uuid4()
    wid_b = uuid.uuid4()
    sa = _cu(Role.SENIOR_ANALYST.value, workspace_id=wid_a)
    with pytest.raises(HTTPException):
        check_workspace_scope_or_admin(
            sa, wid_b,
            required_roles={Role.ADMIN.value, Role.SENIOR_ANALYST.value},
        )


def test_workspace_viewer_in_matching_workspace_fails_role_gate():
    """Workspace match isn't enough — role gate still applies."""
    wid = uuid.uuid4()
    viewer = _cu("viewer", workspace_id=wid)
    with pytest.raises(HTTPException) as exc:
        check_workspace_scope_or_admin(
            viewer, wid, required_roles={Role.ADMIN.value}
        )
    assert exc.value.status_code == 403
    assert "role" in exc.value.detail


def test_workspace_viewer_no_role_gate_passes_when_in_workspace():
    """When required_roles is None, ANY role passes (workspace scope is
    the only constraint)."""
    wid = uuid.uuid4()
    viewer = _cu("viewer", workspace_id=wid)
    check_workspace_scope_or_admin(viewer, wid)
