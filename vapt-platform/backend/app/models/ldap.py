"""LDAP / Active Directory sync. Opt-in per workspace.

Strictly opt-in: when a workspace has no LdapConfig row, behavior is
unchanged (email+password+TOTP). This is the only "ready for SSO"
feature we add, and the spec's no-OIDC constraint is preserved —
LDAP is a user-provisioning channel, not an SSO/SAML flow.
"""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, DateTime, ForeignKey, Index, Integer, String, Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.mixins import Timestamped, UUIDPK


class LdapConfig(Base, UUIDPK, Timestamped):
    """One row per workspace. Encrypted bind password stored separately."""

    __tablename__ = "ldap_configs"
    __table_args__ = (Index("ix_lc_workspace", "workspace_id", unique=True),)

    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    server_url: Mapped[str] = mapped_column(String(500), nullable=False)  # ldap://host:389
    use_tls: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    bind_dn: Mapped[str] = mapped_column(String(500), nullable=False)
    bind_password_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    user_search_base: Mapped[str] = mapped_column(String(500), nullable=False)
    user_search_filter: Mapped[str] = mapped_column(
        String(500), nullable=False, default="(uid={username})"
    )
    group_search_base: Mapped[str | None] = mapped_column(String(500), nullable=True)
    group_member_attr: Mapped[str] = mapped_column(
        String(60), nullable=False, default="member"
    )
    attribute_map: Mapped[dict] = mapped_column(
        JSONB, nullable=False,
        default=lambda: {"email": "mail", "full_name": "cn", "username": "uid"},
    )
    # When a synced user logs in for the first time, give them this role
    default_role: Mapped[str] = mapped_column(String(40), nullable=False, default="viewer")
    # Optional: map LDAP group CN → VAPT role
    group_role_map: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    sync_interval_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=60)
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    last_sync_status: Mapped[str | None] = mapped_column(String(40), nullable=True)
    last_sync_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class LdapUserMapping(Base, UUIDPK, Timestamped):
    """Maps an LDAP DN to a VAPT user. Preserves the link across renames."""

    __tablename__ = "ldap_user_mappings"
    __table_args__ = (
        Index("ix_lum_user", "user_id", unique=True),
        Index("ix_lum_dn", "ldap_dn", unique=True),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    ldap_dn: Mapped[str] = mapped_column(String(500), nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    disabled_in_ldap: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
