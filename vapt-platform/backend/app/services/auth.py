"""Auth service: login, lockout, TOTP, refresh, logout."""

from __future__ import annotations

import secrets
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.secrets import (
    decrypt_str,
    encrypt_str,
    hash_backup_code,
    new_backup_code,
    verify_backup_code,
)
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    hash_token,
    needs_rehash,
    verify_password,
    verify_totp,
)
from app.models.user import LoginAttempt, User, UserSession, WorkspaceMembership
from app.models.mixins import utcnow


class AuthError(Exception):
    def __init__(self, reason: str, code: str = "auth_failed"):
        self.reason = reason
        self.code = code
        super().__init__(reason)


async def _record_attempt(
    db: AsyncSession, email: str, ip: str | None, success: bool, reason: str | None
) -> None:
    db.add(
        LoginAttempt(
            email=email.lower(),
            ip=ip,
            success=success,
            reason=reason,
        )
    )


async def _is_locked(user: User) -> bool:
    return user.locked_until is not None and user.locked_until > utcnow()


async def _maybe_lock(db: AsyncSession, user: User) -> None:
    if user.failed_login_count >= settings.login_max_attempts:
        user.locked_until = utcnow() + timedelta(minutes=settings.login_lockout_minutes)
        user.failed_login_count = 0


async def _is_totp_locked(user: User) -> bool:
    return user.totp_locked_until is not None and user.totp_locked_until > utcnow()


async def _maybe_totp_lock(db: AsyncSession, user: User) -> None:
    if user.totp_failed_count >= settings.login_totp_max_attempts:
        user.totp_locked_until = utcnow() + timedelta(
            minutes=settings.login_totp_lockout_minutes
        )
        user.totp_failed_count = 0


def get_totp_secret(user: User) -> str | None:
    """Decrypt the user's TOTP secret at the application layer.

    The column holds a Fernet ciphertext; consumers never see the raw secret.
    """
    if not user.totp_secret:
        return None
    return decrypt_str(user.totp_secret)


def set_totp_secret(user: User, plaintext: str | None) -> None:
    """Encrypt and store the user's TOTP secret. Pass None to clear."""
    if plaintext is None:
        user.totp_secret = None
    else:
        user.totp_secret = encrypt_str(plaintext)


def get_backup_codes(user: User) -> list[str]:
    """Backup codes are stored as Argon2id hashes. We cannot recover the
    plaintext — only verify a candidate against each hash. This is the
    intended behavior: the server has no way to leak what it doesn't have.

    For UX (e.g. "show me my codes once after enrollment"), enrollment
    returns the plaintext codes directly to the user; the server only
    retains hashes.
    """
    return user.backup_codes or []


def set_backup_codes(user: User, plaintext_codes: list[str]) -> None:
    """Hash backup codes for at-rest storage."""
    user.backup_codes = [hash_backup_code(c) for c in plaintext_codes]


async def authenticate(
    db: AsyncSession,
    email: str,
    password: str,
    ip: str | None = None,
    workspace_id: uuid.UUID | None = None,
) -> User:
    """Verify email + password only. TOTP is a separate step.

    If the user belongs to a workspace with LDAP configured, the
    password is also validated against the directory. Local and
    LDAP must both succeed (defense in depth: a synced user can
    also fall back to their local password if it was set).
    """
    user = await db.scalar(select(User).where(User.email == email.lower()))
    if not user or not user.is_active:
        await _record_attempt(db, email, ip, False, "no_user_or_disabled")
        raise AuthError("invalid credentials", "bad_creds")

    if await _is_locked(user):
        await _record_attempt(db, email, ip, False, "locked")
        raise AuthError("account locked", "locked")

    local_ok = verify_password(password, user.password_hash)
    if not local_ok and workspace_id:
        # try LDAP as a fallback (only when a workspace_id is given)
        from app.services.ldap_sync import authenticate_via_ldap
        ldap_ok = await authenticate_via_ldap(db, workspace_id, email.lower(), password)
        if not ldap_ok:
            user.failed_login_count += 1
            await _maybe_lock(db, user)
            await _record_attempt(db, email, ip, False, "bad_password")
            raise AuthError("invalid credentials", "bad_creds")
    elif not local_ok:
        user.failed_login_count += 1
        await _maybe_lock(db, user)
        await _record_attempt(db, email, ip, False, "bad_password")
        raise AuthError("invalid credentials", "bad_creds")

    # success — reset counters
    user.failed_login_count = 0
    user.locked_until = None
    user.last_login_at = utcnow()
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    await _record_attempt(db, email, ip, True, None)
    return user


def user_requires_totp(user: User, membership_role: str | None) -> bool:
    """TOTP is mandatory for: platform_admin, admin, senior_analyst, analyst.

    Viewers: optional but recommended (only required if explicitly enabled).
    """
    if user.is_platform_admin:
        return True
    if membership_role in (
        Role.ADMIN.value,
        Role.SENIOR_ANALYST.value,
        Role.ANALYST.value,
    ):
        return True
    return user.totp_enabled


async def issue_tokens(
    db: AsyncSession,
    user: User,
    workspace_id: uuid.UUID | None,
    role: str,
    ip: str | None,
    user_agent: str | None,
) -> tuple[str, str, int, uuid.UUID]:
    """Returns (access_token, refresh_token, expires_in_seconds, session_id)."""
    session_id = uuid.uuid4()
    access = create_access_token(
        sub=str(user.id),
        workspace_id=str(workspace_id) if workspace_id else None,
        session_id=str(session_id),
    )
    refresh, refresh_hash = create_refresh_token(sub=str(user.id), session_id=str(session_id))

    sess = UserSession(
        id=session_id,
        user_id=user.id,
        refresh_token_hash=refresh_hash,
        ip=ip,
        user_agent=user_agent,
        expires_at=utcnow() + timedelta(days=settings.refresh_token_ttl_days),
    )
    db.add(sess)
    return access, refresh, settings.access_token_ttl_min * 60, session_id


async def _revoke_user_sessions(db: AsyncSession, user_id: uuid.UUID) -> int:
    """Revoke all non-revoked sessions for a user. Returns the count."""
    from sqlalchemy import update as sa_update
    result = await db.execute(
        sa_update(UserSession)
        .where(UserSession.user_id == user_id, UserSession.revoked_at.is_(None))
        .values(revoked_at=utcnow())
    )
    return getattr(result, "rowcount", 0) or 0


async def rotate_refresh(
    db: AsyncSession,
    refresh_token: str,
    ip: str | None,
    user_agent: str | None,
) -> tuple[str, str, int, uuid.UUID, uuid.UUID, str]:
    """Verify & rotate refresh. Returns (new_access, new_refresh, expires_in,
    new_session_id, user_id, role). On theft detection, revokes the entire
    session family (RFC 6819 §5.2.2.3)."""
    payload = decode_token(refresh_token) if refresh_token else None
    if not payload or payload.get("typ") != "refresh":
        raise AuthError("invalid refresh", "bad_refresh")

    session_id = payload.get("sid")
    user_id = payload.get("sub")
    if not session_id or not user_id:
        raise AuthError("malformed refresh", "bad_refresh")

    sess = await db.get(UserSession, uuid.UUID(session_id))
    if not sess or sess.revoked_at is not None:
        raise AuthError("refresh revoked", "revoked")
    if sess.expires_at < utcnow():
        raise AuthError("refresh expired", "expired")
    if not secrets.compare_digest(sess.refresh_token_hash, hash_token(refresh_token)):
        # Token hash mismatch — possible theft, revoke the WHOLE family.
        # The legitimate user will be forced to re-authenticate on all devices.
        await _revoke_user_sessions(db, uuid.UUID(user_id))
        raise AuthError("refresh mismatch", "stolen")

    user = await db.get(User, uuid.UUID(user_id))
    if not user or not user.is_active:
        raise AuthError("user disabled", "disabled")

    # pick a role from the user's first membership
    mem = await db.scalar(
        select(WorkspaceMembership).where(WorkspaceMembership.user_id == user.id)
    )
    role = "platform_admin" if user.is_platform_admin else (mem.role if mem else "viewer")
    wid = mem.workspace_id if mem else None

    # revoke the old session, issue a new one
    sess.revoked_at = utcnow()
    access, refresh, ttl, new_sid = await issue_tokens(db, user, wid, role, ip, user_agent)
    return access, refresh, ttl, new_sid, user.id, role


async def logout(db: AsyncSession, session_id: uuid.UUID) -> None:
    sess = await db.get(UserSession, session_id)
    if sess and sess.revoked_at is None:
        sess.revoked_at = utcnow()


def verify_totp_or_backup(user: User, code: str) -> tuple[bool, bool]:
    """Returns (ok, totp_used). The caller is responsible for incrementing
    totp_failed_count on (False, _) and resetting on (True, _)."""
    plaintext = get_totp_secret(user)
    if plaintext and verify_totp(plaintext, code):
        return True, True
    # Verify against each Argon2id hash of stored backup codes.
    for code_hash in user.backup_codes or []:
        if verify_backup_code(code, code_hash):
            return True, False
    return False, False


async def consume_backup_code(user: User, code: str) -> None:
    """Remove the matched backup code hash from the user (single-use)."""
    user.backup_codes = [
        h for h in (user.backup_codes or []) if not verify_backup_code(code, h)
    ]


def new_totp_code() -> str:
    """Wrapper for symmetry with other auth helpers."""
    return new_backup_code()  # Not used here; see new_backup_code in core.secrets


# Re-export the enum for use in user_requires_totp checks
from app.models.user import Role  # noqa: E402  (circular-safe)
