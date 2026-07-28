"""Users, sessions, RBAC, audit log."""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum as SAEnum,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import INET, JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.db import Base
from app.models.mixins import Timestamped, UUIDPK, utcnow


class Role(str, Enum):
    PLATFORM_ADMIN = "platform_admin"  # cross-workspace superuser
    ADMIN = "admin"  # workspace admin
    SENIOR_ANALYST = "senior_analyst"  # can approve & lock reports
    ANALYST = "analyst"  # triage, draft
    VIEWER = "viewer"  # read-only


class User(Base, UUIDPK, Timestamped):
    __tablename__ = "users"

    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    is_platform_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # TOTP
    # totp_secret holds a Fernet ciphertext (encrypted with DATA_ENCRYPTION_KEY).
    # Decrypt with app.core.secrets.get_totp_secret / set with set_totp_secret.
    totp_secret: Mapped[str | None] = mapped_column(String(512), nullable=True)
    totp_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # backup_codes holds Argon2id hashes; plaintext is shown to the user ONCE at
    # enrollment time and never recoverable.
    backup_codes: Mapped[list[str]] = mapped_column(JSONB, nullable=False, default=list)

    # Account lockout
    failed_login_count: Mapped[int] = mapped_column(default=0, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    # TOTP-specific lockout (parallel to password lockout).
    totp_failed_count: Mapped[int] = mapped_column(default=0, nullable=False)
    totp_locked_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    password_changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )

    memberships: Mapped[list["WorkspaceMembership"]] = relationship(
        "WorkspaceMembership", back_populates="user", cascade="all, delete-orphan"
    )
    sessions: Mapped[list["UserSession"]] = relationship(
        "UserSession", back_populates="user", cascade="all, delete-orphan"
    )


class WorkspaceMembership(Base, UUIDPK, Timestamped):
    __tablename__ = "workspace_memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "workspace_id", name="uq_membership"),
        Index("ix_membership_workspace", "workspace_id"),
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    workspace_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[Role] = mapped_column(
        SAEnum(Role, name="role", values_callable=lambda e: [m.value for m in e]),
        nullable=False,
        default=Role.VIEWER,
    )

    user: Mapped["User"] = relationship("User", back_populates="memberships")
    workspace: Mapped["Workspace"] = relationship(
        "Workspace", back_populates="memberships"
    )


class UserSession(Base, UUIDPK, Timestamped):
    """Refresh-token sessions, stored hashed for revocation support."""

    __tablename__ = "user_sessions"
    __table_args__ = (Index("ix_session_user", "user_id"),)

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    refresh_token_hash: Mapped[str] = mapped_column(
        String(128), nullable=False, unique=True, index=True
    )
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    ip: Mapped[str | None] = mapped_column(INET, nullable=True)
    issued_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    revoked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_used_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    user: Mapped["User"] = relationship("User", back_populates="sessions")


class AuditLog(Base, UUIDPK, Timestamped):
    """Immutable audit trail. Never updated, only inserted."""

    __tablename__ = "audit_log"
    __table_args__ = (
        Index("ix_audit_workspace_ts", "workspace_id", "created_at"),
        Index("ix_audit_actor", "actor_id"),
    )

    workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True
    )
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    actor_role: Mapped[str | None] = mapped_column(String(40), nullable=True)
    action: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    target_type: Mapped[str | None] = mapped_column(String(60), nullable=True)
    target_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), nullable=True
    )
    ip: Mapped[str | None] = mapped_column(INET, nullable=True)
    user_agent: Mapped[str | None] = mapped_column(String(500), nullable=True)
    extra: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Agent session correlation
    agent_session_id: Mapped[str | None] = mapped_column(
        String(80), nullable=True, index=True
    )


class LoginAttempt(Base, UUIDPK):
    """Rate-limit / lockout counter. Pruned by a periodic job."""

    __tablename__ = "login_attempts"
    __table_args__ = (Index("ix_login_email_ts", "email", "created_at"),)

    email: Mapped[str] = mapped_column(String(255), nullable=False)
    ip: Mapped[str | None] = mapped_column(INET, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    reason: Mapped[str | None] = mapped_column(String(60), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, nullable=False
    )
