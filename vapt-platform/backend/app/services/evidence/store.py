"""Content-addressed evidence store. Same SHA-256 is uploaded once and
referenced by many findings. Big win for retests — the same PoC
screenshot for "log4shell on Tomcat" links to 20 findings but
occupies one S3 object."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import BinaryIO

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.evidence_blob import EvidenceBlob
from app.services import storage


def sha256_of_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


async def upload(
    db: AsyncSession,
    *,
    workspace_id: uuid.UUID,
    actor_id: uuid.UUID | None,
    data: bytes,
    mime: str,
    kind: str,
    filename: str,
) -> EvidenceBlob:
    sha = sha256_of_bytes(data)
    existing = await db.scalar(
        select(EvidenceBlob).where(EvidenceBlob.sha256 == sha)
    )
    now = datetime.now(timezone.utc)
    if existing:
        existing.ref_count += 1
        existing.last_referenced_at = now
        return existing
    key = f"evidence/{workspace_id}/{sha[:2]}/{sha}"
    await storage.put_bytes(key, data, content_type=mime)
    blob = EvidenceBlob(
        sha256=sha, mime=mime, size=len(data), s3_key=key, kind=kind,
        uploaded_by=actor_id, ref_count=1, last_referenced_at=now,
    )
    db.add(blob)
    await db.flush()
    return blob


async def deref(db: AsyncSession, blob: EvidenceBlob) -> None:
    blob.ref_count = max(0, blob.ref_count - 1)
    blob.last_referenced_at = datetime.now(timezone.utc)
    # Optional: a periodic GC job purges blobs with ref_count=0 older than N days
