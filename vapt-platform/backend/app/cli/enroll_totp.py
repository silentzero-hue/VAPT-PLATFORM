"""Enroll TOTP for a user and print the secret/QR. Dev convenience."""

from __future__ import annotations

import argparse
import asyncio
import io
import sys
from urllib.parse import quote

import qrcode
from sqlalchemy import select

from app.core.db import SessionLocal
from app.core.security import generate_totp_secret
from app.models.user import User


def _qr_data_uri(secret: str, email: str) -> str:
    uri = (
        f"otpauth://totp/VAPT%20Platform:{quote(email)}"
        f"?secret={secret}&issuer=VAPT%20Platform"
    )
    img = qrcode.make(uri)
    buf = io.BytesIO()
    img.save(buf, format="PNG")  # type: ignore[arg-type]
    import base64
    return base64.b64encode(buf.getvalue()).decode()


async def main(args: argparse.Namespace) -> int:
    async with SessionLocal() as db:
        u = await db.scalar(select(User).where(User.email == args.email.lower()))
        if not u:
            print("no such user", file=sys.stderr)
            return 1
        secret = generate_totp_secret()
        u.totp_secret = secret
        u.totp_enabled = True
        u.backup_codes = []
        await db.commit()
        print(f"email:        {u.email}")
        print(f"secret:       {secret}")
        print(f"otpauth URI:  otpauth://totp/VAPT%20Platform:{quote(u.email)}?secret={secret}&issuer=VAPT%20Platform")
        print()
        print("Scan the QR with Google Authenticator / 1Password / Bitwarden:")
        print(f"data:image/png;base64,{_qr_data_uri(secret, u.email)}")
        return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--email", required=True)
    ns = p.parse_args()
    sys.exit(asyncio.run(main(ns)))
