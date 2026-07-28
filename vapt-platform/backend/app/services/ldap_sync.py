"""LDAP / AD user sync. Opt-in per workspace. Uses ldap3 if available,
falls back to a stub that surfaces a clear error if not installed.

This is NOT SSO. It is user provisioning: synced users authenticate
via the same email+password+TOTP path. When LDAP is configured and
the bind_user/password is set, the password check can optionally
delegate to LDAP (BIND as the user) — see authenticate().

The spec forbids OIDC; LDAP is a user-directory source, not an
SSO/SAML/OIDC flow. The two are very different.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.core.security import hash_password
from app.models.ldap import LdapConfig, LdapUserMapping
from app.models.user import User, WorkspaceMembership
from app.models.workspace import Workspace

log = get_logger(__name__)


def _decrypt_ciphertext(ciphertext: str) -> str:
    """Reversible decryption. The encryption layer should use KMS/Vault in prod;
    here we use Fernet from cryptography with a key derived from JWT_SECRET.
    """
    from cryptography.fernet import Fernet
    import base64, hashlib
    from app.core.config import settings
    digest = hashlib.sha256(settings.jwt_secret.encode()).digest()
    f = Fernet(base64.urlsafe_b64encode(digest))
    return f.decrypt(ciphertext.encode()).decode()


def encrypt_password(plaintext: str) -> str:
    from cryptography.fernet import Fernet
    import base64, hashlib
    from app.core.config import settings
    digest = hashlib.sha256(settings.jwt_secret.encode()).digest()
    f = Fernet(base64.urlsafe_b64encode(digest))
    return f.encrypt(plaintext.encode()).decode()


def _ldap_client(cfg: LdapConfig):
    try:
        from ldap3 import Server, Connection, ALL
    except ImportError as e:
        raise RuntimeError(
            "ldap3 package not installed; add it to pyproject and rebuild"
        ) from e
    server = Server(cfg.server_url, use_ssl=cfg.use_tls, get_info=ALL)
    pw = _decrypt_ciphertext(cfg.bind_password_ciphertext)
    return Connection(server, user=cfg.bind_dn, password=pw, auto_bind=True)


async def sync_workspace(db: AsyncSession, workspace_id: uuid.UUID) -> dict:
    """Pull all users from the configured LDAP base and upsert into VAPT."""
    cfg = await db.scalar(
        select(LdapConfig).where(
            LdapConfig.workspace_id == workspace_id, LdapConfig.active.is_(True),
        )
    )
    if not cfg:
        return {"ok": False, "reason": "no active config"}
    try:
        from ldap3 import SUBTREE
    except ImportError:
        cfg.last_sync_status = "missing_dependency"
        cfg.last_sync_error = "ldap3 not installed"
        return {"ok": False, "reason": "ldap3 not installed"}

    try:
        conn = _ldap_client(cfg)
        conn.search(
            cfg.user_search_base, cfg.user_search_filter.replace("{username}", "*"),
            search_scope=SUBTREE,
            attributes=list((cfg.attribute_map or {}).values()),
        )
    except Exception as e:  # noqa: BLE001
        cfg.last_sync_status = "error"
        cfg.last_sync_error = str(e)
        return {"ok": False, "reason": f"ldap search: {e}"}

    amap = cfg.attribute_map or {"email": "mail", "full_name": "cn", "username": "uid"}
    seen_dns: set[str] = set()
    created = 0
    updated = 0
    for entry in conn.entries:
        dn = str(entry.entry_dn)
        seen_dns.add(dn)
        email = (getattr(entry, amap["email"], None) or [""])[0] if hasattr(entry, amap["email"]) else None
        full_name = (getattr(entry, amap["full_name"], None) or [""])[0] if hasattr(entry, amap["full_name"]) else None
        if not email:
            continue
        email = email.lower()
        # match by mapping
        m = await db.scalar(
            select(LdapUserMapping).where(LdapUserMapping.ldap_dn == dn)
        )
        if m:
            u = await db.get(User, m.user_id)
            if u:
                u.email = email
                u.full_name = full_name or u.full_name
                u.is_active = True
            updated += 1
        else:
            u = await db.scalar(select(User).where(User.email == email))
            if not u:
                u = User(
                    email=email, full_name=full_name or email.split("@")[0],
                    password_hash=hash_password(uuid.uuid4().hex),  # unusable; LDAP authenticates
                    is_active=True,
                )
                db.add(u)
                await db.flush()
                created += 1
            db.add(LdapUserMapping(
                user_id=u.id, workspace_id=workspace_id, ldap_dn=dn,
                last_seen_at=datetime.now(timezone.utc),
            ))
        # ensure membership
        mem = await db.scalar(
            select(WorkspaceMembership).where(
                WorkspaceMembership.user_id == u.id,
                WorkspaceMembership.workspace_id == workspace_id,
            )
        )
        if not mem:
            db.add(WorkspaceMembership(
                user_id=u.id, workspace_id=workspace_id, role=cfg.default_role,
            ))
    # mark missing DNs as disabled
    mappings = (await db.execute(
        select(LdapUserMapping).where(LdapUserMapping.workspace_id == workspace_id)
    )).scalars().all()
    for m in mappings:
        if m.ldap_dn not in seen_dns:
            m.disabled_in_ldap = True
    cfg.last_sync_at = datetime.now(timezone.utc)
    cfg.last_sync_status = "ok"
    cfg.last_sync_error = None
    return {"ok": True, "created": created, "updated": updated}


async def authenticate_via_ldap(
    db: AsyncSession, workspace_id: uuid.UUID, email: str, password: str
) -> bool:
    """Try to bind as the user. Returns True on success."""
    cfg = await db.scalar(
        select(LdapConfig).where(
            LdapConfig.workspace_id == workspace_id, LdapConfig.active.is_(True),
        )
    )
    if not cfg:
        return False
    try:
        conn = _ldap_client(cfg)
    except Exception:
        return False
    filt = cfg.user_search_filter.replace("{username}", email)
    try:
        conn.search(cfg.user_search_base, filt, attributes=["cn"])
        if not conn.entries:
            return False
        user_dn = str(conn.entries[0].entry_dn)
        from ldap3 import Server, Connection
        srv = Server(cfg.server_url, use_ssl=cfg.use_tls)
        user_bind = Connection(srv, user=user_dn, password=password, auto_bind=True)
        return user_bind.bound
    except Exception as e:  # noqa: BLE001
        log.warning("ldap_auth_failed", err=str(e))
        return False
