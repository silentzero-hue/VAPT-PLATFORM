"""Evidence blobs — content-addressed storage. The same SHA-256 file
is uploaded once and referenced by many findings. Includes per-blob
metadata (mime, size, kind classification, reference count)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.db import Base
from app.models.mixins import Timestamped, UUIDPK


class EvidenceBlob(Base, UUIDPK, Timestamped):
    """Deduplicated content store. The DB unique constraint on sha256
    is the canonical dedup key. S3 holds the actual bytes."""

    __tablename__ = "evidence_blobs"
    __table_args__ = (
        Index("ix_eb_sha256", "sha256", unique=True),
    )

    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    mime: Mapped[str] = mapped_column(String(120), nullable=False)
    size: Mapped[int] = mapped_column(Integer, nullable=False)
    s3_key: Mapped[str] = mapped_column(String(500), nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)  # screenshot|request|log|binary
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    ref_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_referenced_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
