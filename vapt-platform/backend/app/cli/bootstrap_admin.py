"""Bootstrap the first platform admin.

Usage:
  docker compose exec backend python -m app.cli.bootstrap_admin \
      --email admin@example.com --password 'StrongPassword123!' --name 'Admin'

Idempotent: if a user with that email already exists and is a
platform_admin, this is a no-op. If they exist and aren't, they're
promoted. The first run creates the user.

This is the only path that exists outside of the API for the
initial admin — per spec, "admin-provisioned accounts only".
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from getpass import getpass

from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models.user import Role, User


async def main(args: argparse.Namespace) -> int:
    async with SessionLocal() as db:
        email = args.email.lower().strip()
        u = await db.scalar(select(User).where(User.email == email))
        if not u:
            u = User(
                email=email,
                full_name=args.name or email.split("@")[0],
                password_hash=hash_password(args.password),
                is_active=True,
                is_platform_admin=True,
            )
            db.add(u)
            await db.flush()
            print(f"created platform_admin: {email} (id={u.id})")
        else:
            if not u.is_platform_admin:
                u.is_platform_admin = True
                u.password_hash = hash_password(args.password)
                u.is_active = True
                print(f"promoted existing user to platform_admin: {email}")
            else:
                if args.reset_password:
                    u.password_hash = hash_password(args.password)
                    print(f"reset password for: {email}")
                else:
                    print(f"no-op: {email} is already platform_admin")
        await db.commit()
        return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", required=True)
    parser.add_argument("--password", required=False)
    parser.add_argument("--name", required=False, default="")
    parser.add_argument("--reset-password", action="store_true")
    ns = parser.parse_args()
    if not ns.password:
        ns.password = getpass("Password: ")
    if len(ns.password) < 12:
        print("password must be at least 12 characters", file=sys.stderr)
        sys.exit(1)
    sys.exit(asyncio.run(main(ns)))
