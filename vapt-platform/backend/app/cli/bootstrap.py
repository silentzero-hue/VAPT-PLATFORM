"""First-boot bootstrap: platform admin + an empty default workspace.

Idempotent. Safe to re-run. The previous seed_demo.py also created
a fake client and demo engagement; that has been removed so analysts
start from a real, intentional engagement rather than a fictional one.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.security import hash_password
from app.models.user import Role, User, WorkspaceMembership
from app.models.workspace import Workspace


async def main(args: argparse.Namespace) -> int:
    async with SessionLocal() as db:
        # 1) Platform admin (idempotent)
        email = args.email.lower().strip()
        admin = await db.scalar(select(User).where(User.email == email))
        if not admin:
            admin = User(
                email=email,
                full_name=args.name or email.split("@")[0],
                password_hash=hash_password(args.password),
                is_active=True,
                is_platform_admin=True,
            )
            db.add(admin)
            await db.flush()
            print(f"created platform_admin: {email}")
        else:
            if not admin.is_platform_admin:
                admin.is_platform_admin = True
            admin.is_active = True
            print(f"existing user marked platform_admin: {email}")

        # 2) Default workspace (idempotent). Empty — no engagement seeded.
        ws = await db.scalar(
            select(Workspace).where(Workspace.slug == args.slug)
        )
        if not ws:
            ws = Workspace(
                name=args.workspace_name,
                slug=args.slug,
                description="",
                settings={},
            )
            db.add(ws)
            await db.flush()
            print(f"created workspace: {ws.name} ({ws.slug})")
        else:
            print(f"workspace exists: {ws.name} ({ws.slug})")

        # Ensure admin is a member with admin role.
        mem = await db.scalar(
            select(WorkspaceMembership).where(
                WorkspaceMembership.user_id == admin.id,
                WorkspaceMembership.workspace_id == ws.id,
            )
        )
        if not mem:
            db.add(WorkspaceMembership(
                user_id=admin.id, workspace_id=ws.id, role=Role.ADMIN.value,
            ))
            print(f"added admin as member of {ws.name}")
        await db.commit()
        print("done.")
        return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--email", default="admin@vapt.local")
    parser.add_argument("--password", required=False)
    parser.add_argument("--name", default="Admin")
    parser.add_argument("--workspace-name", default="Default Workspace")
    parser.add_argument("--slug", default="default")
    ns = parser.parse_args()
    if not ns.password:
        from getpass import getpass
        ns.password = getpass("Password: ")
    if len(ns.password) < 12:
        print("password must be at least 12 characters", file=sys.stderr)
        sys.exit(1)
    sys.exit(asyncio.run(main(ns)))
