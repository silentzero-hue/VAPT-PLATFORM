"""Column-level encryption helpers (Fernet via DATA_ENCRYPTION_KEY).

The DATA_ENCRYPTION_KEY must be a real Fernet key (base64url-encoded 32 bytes)
loaded from env, NOT derived from JWT_SECRET. This means JWT rotation does NOT
invalidate stored ciphertexts and a JWT leak does NOT expose encrypted secrets.

Used for:
  - User.totp_secret (column-level encryption at rest)
  - User.backup_codes (hashed; see hash_backup_code)
  - LdapConfig.bind_password_ciphertext
  - NessusServer.access_key_ciphertext / secret_key_ciphertext
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
from functools import lru_cache

from argon2 import PasswordHasher
from cryptography.fernet import Fernet, InvalidToken

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)


_BACKUP_HASHER = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)


def _normalize_key(raw: str) -> bytes:
    """Accept either a raw 32-byte string or a base64url-encoded Fernet key.

    A real Fernet key is base64url(32 random bytes). We accept both forms for
    operator convenience: if `raw` decodes to exactly 32 bytes via
    urlsafe_b64decode (with padding), use that; otherwise sha256(raw)[:32].
    """
    if not raw:
        raise ValueError("DATA_ENCRYPTION_KEY is empty")
    # Try base64url-decode with padding
    try:
        padded = raw + "=" * (-len(raw) % 4)
        decoded = base64.urlsafe_b64decode(padded)
        if len(decoded) == 32:
            return base64.urlsafe_b64encode(decoded)
    except Exception:
        pass
    digest = hashlib.sha256(raw.encode()).digest()
    return base64.urlsafe_b64encode(digest)


@lru_cache(maxsize=1)
def _fernet() -> Fernet:
    key = _normalize_key(settings.data_encryption_key)
    return Fernet(key)


def encrypt_str(plaintext: str) -> str:
    """Encrypt a UTF-8 string. Returns url-safe base64 token."""
    if plaintext is None:
        return plaintext  # type: ignore[return-value]
    return _fernet().encrypt(plaintext.encode("utf-8")).decode("ascii")


def decrypt_str(ciphertext: str | None) -> str | None:
    """Decrypt a Fernet token. Returns None on invalid/empty input."""
    if not ciphertext:
        return None
    try:
        return _fernet().decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except InvalidToken:
        log.warning("decrypt_failed", hint="rotated data_encryption_key?")
        return None


# ---------------------------------------------------------------------------
# Backup code hashing (Argon2id, per code)
# ---------------------------------------------------------------------------
def hash_backup_code(code: str) -> str:
    """Hash a single backup code. Stored as Argon2id."""
    return _BACKUP_HASHER.hash(code)


def verify_backup_code(code: str, code_hash: str) -> bool:
    """Constant-time verification of a backup code against its Argon2id hash."""
    try:
        return _BACKUP_HASHER.verify(code_hash, code)
    except Exception:
        return False


def new_backup_code() -> str:
    """Generate a high-entropy backup code (~80 bits, urlsafe)."""
    return secrets.token_urlsafe(10)


# ---------------------------------------------------------------------------
# Model-level helpers (avoid leaking Fernet/Argon2 details into callers)
# ---------------------------------------------------------------------------
def set_totp_secret(user, plaintext: str | None) -> None:
    """Set a User's TOTP secret as a Fernet ciphertext, or clear it."""
    if plaintext is None:
        user.totp_secret = None
    else:
        user.totp_secret = encrypt_str(plaintext)


def get_totp_secret(user) -> str | None:
    """Decrypt a User's TOTP secret. Returns None if unset or invalid."""
    if not user.totp_secret:
        return None
    return decrypt_str(user.totp_secret)


def set_backup_codes(user, plaintext_codes: list[str]) -> None:
    """Hash backup codes for at-rest storage.

    Plaintext is shown to the user ONCE at enrollment and never recoverable.
    """
    user.backup_codes = [hash_backup_code(c) for c in plaintext_codes]
