"""MinIO / S3 storage helper."""

from __future__ import annotations

import hashlib
import io
import uuid
from typing import BinaryIO

import aioboto3

from app.core.config import settings


_session = aioboto3.Session()


def _client():
    import os
    return _session.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        region_name=settings.s3_region,
        aws_access_key_id=settings.s3_access_key or os.environ.get("MINIO_ROOT_USER", "vapt"),
        aws_secret_access_key=settings.s3_secret_key or os.environ.get("MINIO_ROOT_PASSWORD", "changeme"),
    )


async def ensure_bucket() -> None:
    async with _client() as s3:
        try:
            await s3.head_bucket(Bucket=settings.s3_bucket)
        except Exception:
            try:
                await s3.create_bucket(Bucket=settings.s3_bucket)
            except Exception:
                pass


async def put_bytes(
    key: str, data: bytes, content_type: str = "application/octet-stream"
) -> tuple[str, int]:
    sha = hashlib.sha256(data).hexdigest()
    async with _client() as s3:
        await s3.put_object(
            Bucket=settings.s3_bucket, Key=key, Body=data,
            ContentType=content_type,
        )
    return sha, len(data)


async def get_bytes(key: str) -> bytes:
    async with _client() as s3:
        obj = await s3.get_object(Bucket=settings.s3_bucket, Key=key)
        async with obj["Body"] as stream:
            return await stream.read()


async def presigned_get(key: str, expires: int = 600) -> str:
    async with _client() as s3:
        return await s3.generate_presigned_url(
            "get_object",
            Params={"Bucket": settings.s3_bucket, "Key": key},
            ExpiresIn=expires,
        )
