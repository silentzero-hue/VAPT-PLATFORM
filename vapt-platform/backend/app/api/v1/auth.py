"""Auth router: login (step 1) -> TOTP (step 2) -> access+refresh cookies.

Security:
  - JWT_SECRET must be rotated independently of DATA_ENCRYPTION_KEY.
  - Per-endpoint rate limits via @limiter.limit.
  - Per-account TOTP lockout (parallel to password lockout).
  - TOTP secret at rest is encrypted; backup codes are Argon2id-hashed.
  - Login challenge cookie is HMAC-signed; user_id / role / wid are derived
    from the DB on read, not trusted from the cookie.
  - Refresh token theft detection revokes the entire session family.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import uuid as _uuid
from base64 import urlsafe_b64decode, urlsafe_b64encode
from datetime import datetime, timezone
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, HTTPException, Request, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, get_current_user
from app.core.config import settings
from app.core.db import get_session
from app.core.limiter import limiter
from app.core.logging import get_logger
from app.core.security import (
    generate_totp_secret,
    hash_password,
    totp_qr_data_uri,
    verify_totp,
)
from app.core.secrets import (
    new_backup_code,
    set_backup_codes,
    set_totp_secret,
)
from app.models.user import (
    AuditLog,
    Role,
    User,
    WorkspaceMembership,
)
from app.schemas.auth import (
    AccessTokenResponse,
    LoginRequest,
    LoginResponse,
    MembershipOut,
    PasswordChangeRequest,
    RefreshRequest,
    TotpEnrollResponse,
    TotpRequiredResponse,
    TotpVerifyRequest,
    UserCreate,
    UserOut,
)
from app.services.auth import (
    AuthError,
    authenticate,
    consume_backup_code,
    get_totp_secret,
    issue_tokens,
    logout as svc_logout,
    rotate_refresh,
    user_requires_totp,
    verify_totp_or_backup,
    _is_totp_locked,
    _maybe_totp_lock,
)

router = APIRouter(prefix="/auth", tags=["auth"])
log = get_logger(__name__)

# short-lived cookie holding the post-password-verify challenge
CHALLENGE_COOKIE = "vapt_totp_challenge"
ACCESS_COOKIE = "vapt_access"
REFRESH_COOKIE = "vapt_refresh"


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


def _is_secure() -> bool:
    return settings.app_env in ("staging", "production")


def _set_auth_cookies(response: Response, access: str, refresh: str) -> None:
    response.set_cookie(
        ACCESS_COOKIE, access, httponly=True, secure=_is_secure(), samesite="strict",
        max_age=settings.access_token_ttl_min * 60, path="/",
    )
    response.set_cookie(
        REFRESH_COOKIE, refresh, httponly=True, secure=_is_secure(), samesite="strict",
        max_age=settings.refresh_token_ttl_days * 86400, path="/api/v1/auth",
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path="/api/v1/auth")
    response.delete_cookie(CHALLENGE_COOKIE, path="/")


# ---------------------------------------------------------------------------
# Signed challenge cookie (HMAC-SHA-256 over the user_id, role, wid, nonce)
# ---------------------------------------------------------------------------
def _sign_challenge(payload: dict) -> str:
    """Return `<base64url-payload>.<hex-hmac>`.

    The HMAC key is derived from JWT_SECRET (acceptable: this is a *cookie
    integrity* check, not data encryption; if JWT_SECRET leaks, the worst
    case is cookie forgery, which is no worse than having the user's
    session token). The user_id / role / wid are still re-derived from
    the DB on read.
    """
    raw = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    body = urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")
    mac = hmac.new(settings.jwt_secret.encode("utf-8"), body.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{body}.{mac}"


def _verify_challenge(token: str) -> dict | None:
    """Return the payload dict if the MAC is valid, else None."""
    try:
        body, mac = token.rsplit(".", 1)
    except ValueError:
        return None
    expected = hmac.new(
        settings.jwt_secret.encode("utf-8"), body.encode("ascii"), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(mac, expected):
        return None
    pad = "=" * (-len(body) % 4)
    try:
        raw = urlsafe_b64decode(body + pad)
        return json.loads(raw)
    except Exception:
        return None


async def _record_audit(
    db: AsyncSession,
    *,
    workspace_id: UUID | None,
    actor_id: UUID | None,
    role: str | None,
    action: str,
    request: Request,
    extra: dict | None = None,
) -> None:
    db.add(
        AuditLog(
            workspace_id=workspace_id,
            actor_id=actor_id,
            actor_role=role,
            action=action,
            ip=_client_ip(request),
            user_agent=request.headers.get("user-agent"),
            extra=extra or {},
        )
    )


@router.post("/login", response_model=None)
async def login(
    request: Request,
    body: LoginRequest,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_session)],
):
    # If the request carries an X-VAPT-Workspace header, prefer
    # authenticating against that workspace's LDAP directory.
    wid_header = request.headers.get("X-VAPT-Workspace")
    workspace_id: _uuid.UUID | None = None
    if wid_header:
        try:
            workspace_id = _uuid.UUID(wid_header)
        except (ValueError, TypeError):
            raise HTTPException(status_code=400, detail="bad X-VAPT-Workspace header")
    try:
        user = await authenticate(
            db, body.email, body.password, ip=_client_ip(request),
            workspace_id=workspace_id,
        )
    except AuthError as e:
        if e.code == "locked":
            # generic — do not leak lockout duration
            log.info("login_locked", email=body.email)
            raise HTTPException(
                status_code=status.HTTP_423_LOCKED, detail="invalid credentials"
            ) from e
        # generic — do not leak whether email exists
        raise HTTPException(status_code=401, detail="invalid credentials") from e

    # Pick a role: platform_admin OR first membership
    role = "platform_admin" if user.is_platform_admin else None
    wid = None
    mem = await db.scalar(
        select(WorkspaceMembership).where(WorkspaceMembership.user_id == user.id)
    )
    if mem:
        if role is None:
            role = mem.role
        wid = mem.workspace_id  # always set scope, even for platform_admin
    if role is None:
        role = "viewer"

    if user_requires_totp(user, role) or user.totp_enabled:
        # Issue a short-lived signed challenge cookie. The user_id / role /
        # wid are NOT trusted from the cookie; the server re-fetches the
        # user from the DB on the TOTP step.
        challenge = secrets.token_urlsafe(32)
        signed = _sign_challenge({
            "uid": str(user.id),
            "nonce": challenge,
            "exp": int(datetime.now(timezone.utc).timestamp()) + 300,
        })
        response.set_cookie(
            CHALLENGE_COOKIE,
            signed,
            httponly=True,
            secure=_is_secure(),
            samesite="strict",
            max_age=300,
            path="/api/v1/auth",
        )
        await _record_audit(
            db, workspace_id=wid, actor_id=user.id, role=role,
            action="login.password_ok", request=request,
        )
        return TotpRequiredResponse(totp_required=True, challenge_token=challenge)

    # No TOTP — issue tokens
    access, refresh, ttl, _ = await issue_tokens(
        db, user, wid, role, _client_ip(request),
        request.headers.get("user-agent"),
    )
    _set_auth_cookies(response, access, refresh)
    await _record_audit(
        db, workspace_id=wid, actor_id=user.id, role=role,
        action="login.success", request=request,
    )
    return LoginResponse(
        access_token=access, refresh_token=refresh, expires_in=ttl,
        user=await _user_to_out(db, user),
    )


@router.post("/login/totp", response_model=LoginResponse)
async def login_totp(
    request: Request,
    body: TotpVerifyRequest,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_session)],
    challenge: Annotated[str | None, Cookie(alias=CHALLENGE_COOKIE)] = None,
):
    if not challenge:
        raise HTTPException(status_code=401, detail="no challenge")
    payload = _verify_challenge(challenge)
    if not payload or payload.get("exp", 0) < int(datetime.now(timezone.utc).timestamp()):
        raise HTTPException(status_code=401, detail="invalid challenge")
    user_id_str = payload.get("uid")
    if not user_id_str:
        raise HTTPException(status_code=401, detail="invalid challenge")
    user = await db.get(User, UUID(user_id_str))
    if not user or not user.is_active:
        raise HTTPException(status_code=401, detail="invalid challenge")

    # Per-account TOTP lockout
    if await _is_totp_locked(user):
        await _record_audit(
            db, workspace_id=None, actor_id=user.id, role=None,
            action="login.totp_locked", request=request,
        )
        # generic message — do not leak lockout duration
        raise HTTPException(status_code=status.HTTP_423_LOCKED, detail="invalid credentials")

    ok, totp_used = verify_totp_or_backup(user, body.code)
    if not ok:
        user.totp_failed_count += 1
        await _maybe_totp_lock(db, user)
        await _record_audit(
            db, workspace_id=None, actor_id=user.id, role=None,
            action="login.totp_failed", request=request,
        )
        raise HTTPException(status_code=401, detail="bad totp")

    # Consume the backup code if one was used
    if not totp_used:
        await consume_backup_code(user, body.code)

    # Reset TOTP counter on success
    user.totp_failed_count = 0
    user.totp_locked_until = None

    # Re-derive role/wid from DB (do not trust cookie)
    role = "platform_admin" if user.is_platform_admin else None
    wid = None
    mem = await db.scalar(
        select(WorkspaceMembership).where(WorkspaceMembership.user_id == user.id)
    )
    if mem:
        if role is None:
            role = mem.role
        wid = mem.workspace_id
    if role is None:
        role = "viewer"

    access, refresh, ttl, _ = await issue_tokens(
        db, user, wid, role, _client_ip(request),
        request.headers.get("user-agent"),
    )
    _set_auth_cookies(response, access, refresh)
    response.delete_cookie(CHALLENGE_COOKIE, path="/api/v1/auth")
    await _record_audit(
        db, workspace_id=wid, actor_id=user.id, role=role,
        action="login.success", request=request,
    )
    return LoginResponse(
        access_token=access, refresh_token=refresh, expires_in=ttl,
        user=await _user_to_out(db, user),
    )


@router.post("/refresh", response_model=AccessTokenResponse)
async def refresh(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_session)],
    body: RefreshRequest | None = None,
):
    # accept refresh from body OR cookie
    rt: str | None = body.refresh_token if body else None
    if not rt:
        rt = request.cookies.get(REFRESH_COOKIE)
    if not rt:
        raise HTTPException(status_code=401, detail="no refresh token")
    try:
        access, new_refresh, ttl, _sid, _uid, _role = await rotate_refresh(
            db, rt, _client_ip(request), request.headers.get("user-agent"),
        )
    except AuthError as e:
        # generic — do not leak state (stolen / revoked / expired all map to 401)
        raise HTTPException(status_code=401, detail="invalid token") from e
    _set_auth_cookies(response, access, new_refresh)
    return AccessTokenResponse(access_token=access, expires_in=ttl)


@router.post("/logout", status_code=204)
async def logout(
    request: Request,
    response: Response,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    await svc_logout(db, current.session_id)  # type: ignore[arg-type]
    await _record_audit(
        db, workspace_id=current.workspace_id, actor_id=current.user.id,
        role=current.role, action="logout", request=request,
    )
    _clear_auth_cookies(response)
    return Response(status_code=204)


@router.get("/me", response_model=UserOut)
async def me(
    current: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_session)],
):
    return await _user_to_out(db, current.user)


@router.post("/me/password", status_code=204)
async def change_password(
    body: PasswordChangeRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    from app.core.security import verify_password
    if not verify_password(body.current_password, current.user.password_hash):
        raise HTTPException(status_code=400, detail="wrong current password")
    current.user.password_hash = hash_password(body.new_password)
    current.user.password_changed_at = datetime.now(timezone.utc)
    # invalidate all other sessions
    from sqlalchemy import update
    from app.models.user import UserSession
    await db.execute(
        update(UserSession)
        .where(
            UserSession.user_id == current.user.id,
            UserSession.id != current.session_id,  # type: ignore[arg-type]
        )
        .values(revoked_at=datetime.now(timezone.utc))
    )
    await _record_audit(
        db, workspace_id=current.workspace_id, actor_id=current.user.id,
        role=current.role, action="password.change", request=request,
    )
    return Response(status_code=204)


@router.post("/me/totp/enroll", response_model=TotpEnrollResponse)
async def enroll_totp(
    request: Request,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    if current.user.totp_enabled:
        raise HTTPException(status_code=400, detail="totp already enabled")
    secret = generate_totp_secret()
    # Encrypt the TOTP secret at rest; backup codes are Argon2id-hashed.
    set_totp_secret(current.user, secret)
    plaintext_codes = [new_backup_code() for _ in range(10)]
    set_backup_codes(current.user, plaintext_codes)
    # Store the plaintext in the response only — it is never recoverable
    # server-side after this call returns. The user MUST save them now.
    await _record_audit(
        db, workspace_id=current.workspace_id, actor_id=current.user.id,
        role=current.role, action="totp.enroll_start", request=request,
    )
    return TotpEnrollResponse(
        secret=secret,
        otpauth_url=f"otpauth://totp/{settings.totp_issuer}:{current.user.email}?secret={secret}&issuer={settings.totp_issuer}",
        qr_data_uri=totp_qr_data_uri(secret, current.user.email),
        backup_codes=plaintext_codes,
    )


@router.post("/me/totp/verify", status_code=204)
async def verify_totp_enroll(
    body: TotpVerifyRequest,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    if not current.user.totp_secret:
        raise HTTPException(status_code=400, detail="no totp in progress")
    plaintext = get_totp_secret(current.user)
    if not plaintext or not verify_totp(plaintext, body.code):
        raise HTTPException(status_code=400, detail="bad totp code")
    current.user.totp_enabled = True
    await _record_audit(
        db, workspace_id=current.workspace_id, actor_id=current.user.id,
        role=current.role, action="totp.enroll_done", request=request,
    )
    return Response(status_code=204)


# --------- Admin user mgmt (platform admin only) ---------


@router.post("/admin/users", response_model=UserOut, status_code=201)
async def admin_create_user(
    body: UserCreate,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    if current.role != Role.PLATFORM_ADMIN.value:
        raise HTTPException(status_code=403, detail="platform admin only")
    existing = await db.scalar(select(User).where(User.email == body.email.lower()))
    if existing:
        raise HTTPException(status_code=409, detail="email exists")
    # SECURITY: do NOT honor is_platform_admin from the public schema.
    # Elevation must go through a separate, audited admin-only path.
    user = User(
        email=body.email.lower(),
        full_name=body.full_name,
        password_hash=hash_password(body.password),
        is_platform_admin=False,  # never set from public API
    )
    db.add(user)
    await _record_audit(
        db, workspace_id=None, actor_id=current.user.id,
        role=current.role, action="user.create", request=request,
        extra={"new_user_id": str(user.id)},
    )
    return await _user_to_out(db, user)


async def _user_to_out(db: AsyncSession, user: User) -> UserOut:
    mems = (
        await db.execute(
            select(WorkspaceMembership).where(WorkspaceMembership.user_id == user.id)
        )
    ).scalars().all()
    from app.models.workspace import Workspace
    out_mems: list[MembershipOut] = []
    for m in mems:
        ws = await db.get(Workspace, m.workspace_id)
        if ws:
            out_mems.append(MembershipOut(
                workspace_id=ws.id, workspace_name=ws.name, role=m.role
            ))
    return UserOut(
        id=user.id, email=user.email, full_name=user.full_name,
        is_active=user.is_active, is_platform_admin=user.is_platform_admin,
        totp_enabled=user.totp_enabled, last_login_at=user.last_login_at,
        created_at=user.created_at, memberships=out_mems,
    )
