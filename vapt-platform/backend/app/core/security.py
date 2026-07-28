"""Password hashing (Argon2id), TOTP, JWT issuance & verification."""

from __future__ import annotations

import base64
import hashlib
import hmac
import io
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import jwt
import pyotp
import qrcode
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from app.core.config import settings


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------
_hasher = PasswordHasher(
    time_cost=settings.argon2_time_cost,
    memory_cost=settings.argon2_memory_cost,
    parallelism=settings.argon2_parallelism,
)


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    try:
        _hasher.verify(password_hash, password)
        return True
    except VerifyMismatchError:
        return False
    except Exception:
        return False


def needs_rehash(password_hash: str) -> bool:
    return _hasher.check_needs_rehash(password_hash)


# ---------------------------------------------------------------------------
# TOTP
# ---------------------------------------------------------------------------
def generate_totp_secret() -> str:
    return pyotp.random_base32()


def totp_provisioning_uri(secret: str, email: str) -> str:
    return pyotp.totp.TOTP(secret).provisioning_uri(
        name=email, issuer_name=settings.totp_issuer
    )


def totp_qr_data_uri(secret: str, email: str) -> str:
    uri = totp_provisioning_uri(secret, email)
    img = qrcode.make(uri)
    buf = io.BytesIO()
    if hasattr(img, "save"):
        img.save(buf, format="PNG")  # type: ignore[arg-type]
    else:  # pragma: no cover - SVG branch
        buf.write(img.to_string())  # type: ignore[union-attr]
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/png;base64,{b64}"


def verify_totp(secret: str, code: str) -> bool:
    if not code or not secret:
        return False
    totp = pyotp.TOTP(secret)
    # window=1 to allow ±30s skew
    return totp.verify(code, valid_window=1)


# ---------------------------------------------------------------------------
# JWT
# ---------------------------------------------------------------------------
def _now() -> datetime:
    return datetime.now(timezone.utc)


def _encode(payload: dict[str, Any]) -> str:
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def _decode(token: str) -> dict[str, Any]:
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


def create_access_token(
    *, sub: str, workspace_id: str | None, session_id: str
) -> str:
    """Issue a short-lived access token.

    SECURITY: The `role` claim is intentionally NOT in the payload. The role
    is derived server-side from `is_platform_admin` and the user's
    WorkspaceMembership in `get_current_user`. Putting `role` in the token
    would create a privilege-escalation footgun if any consumer ever trusts
    the claim.
    """
    now = _now()
    payload = {
        "sub": sub,
        "wid": workspace_id,
        "sid": session_id,
        "iat": int(now.timestamp()),
        "exp": int(
            (now + timedelta(minutes=settings.access_token_ttl_min)).timestamp()
        ),
        "typ": "access",
        "jti": secrets.token_urlsafe(16),
    }
    return _encode(payload)


def create_refresh_token(*, sub: str, session_id: str) -> tuple[str, str]:
    """Return (token, token_hash). The hash is what we store; the raw token is
    given to the client once and never persisted in cleartext."""
    now = _now()
    jti = secrets.token_urlsafe(32)
    payload = {
        "sub": sub,
        "sid": session_id,
        "jti": jti,
        "iat": int(now.timestamp()),
        "exp": int(
            (now + timedelta(days=settings.refresh_token_ttl_days)).timestamp()
        ),
        "typ": "refresh",
    }
    token = _encode(payload)
    return token, hash_token(token)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def decode_token(token: str) -> dict[str, Any]:
    return _decode(token)


def constant_time_eq(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())
