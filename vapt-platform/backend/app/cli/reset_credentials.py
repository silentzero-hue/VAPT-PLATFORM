"""Reset password + re-enroll TOTP for a user in one shot. Prints a
clean summary."""

from __future__ import annotations

import argparse
import asyncio
import io
import sys
from urllib.parse import quote

import qrcode
from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.security import generate_totp_secret, hash_password
from app.models.user import User


async def main(args: argparse.Namespace) -> int:
    async with SessionLocal() as db:
        u = await db.scalar(select(User).where(User.email == args.email.lower()))
        if not u:
            print(f"no such user: {args.email}", file=sys.stderr)
            return 1
        u.password_hash = hash_password(args.password)
        u.is_active = True
        u.failed_login_count = 0
        u.locked_until = None
        secret = generate_totp_secret()
        u.totp_secret = secret
        u.totp_enabled = True
        u.backup_codes = []
        await db.commit()
        uri = (
            f"otpauth://totp/VAPT%20Platform:{quote(u.email)}"
            f"?secret={secret}&issuer=VAPT%20Platform"
        )
        img = qrcode.make(uri)
        buf = io.BytesIO()
        img.save(buf, format="PNG")  # type: ignore[arg-type]
        import base64
        b64 = base64.b64encode(buf.getvalue()).decode()
        print()
        print("=" * 60)
        print(" CREDENTIALS RESET")
        print("=" * 60)
        print(f"  email:    {u.email}")
        print(f"  password: {args.password}")
        print(f"  TOTP secret (paste into your authenticator app):")
        print(f"    {secret}")
        print()
        print(f"  otpauth URI: {uri}")
        print()
        print("  Or scan this QR (data:image/png;base64,…) in 1Password/Authy:")
        print(f"  data:image/png;base64,{b64[:80]}...")
        print("=" * 60)
        return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--email", required=True)
    p.add_argument("--password", required=True)
    ns = p.parse_args()
    sys.exit(asyncio.run(main(ns)))
