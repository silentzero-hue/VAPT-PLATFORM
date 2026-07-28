"""Nessus API client. Same credential scheme as the legacy .env
(NESSUS_BASE_URL / NESSUS_ACCESS_KEY / NESSUS_SECRET_KEY) but pulled
from per-workspace NessusServer rows so each client can have their
own Nessus instance.

This is the missing piece that closes the loop: the spec said
"no scanner engine" — the platform ingests from an EXTERNAL scanner.
That external scanner can now be a live Nessus server, not just a
uploaded .nessus file.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx

from app.core.logging import get_logger
from app.services.ldap_sync import encrypt_password  # reuse the same Fernet scheme

log = get_logger(__name__)

DEFAULT_TIMEOUT = 30.0


def _decrypt(ciphertext: str) -> str:
    from app.services.ldap_sync import _decrypt_ciphertext
    return _decrypt_ciphertext(ciphertext)


class NessusClient:
    """Async wrapper around the Nessus REST API.

    Authentication: API keys (X-ApiKeys header) — the modern, preferred
    path. Legacy session-based auth is not supported; every Nessus
    build from 8.x onward supports API keys.
    """

    def __init__(
        self,
        base_url: str,
        access_key: str,
        secret_key: str,
        verify_ssl: bool = False,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.verify_ssl = verify_ssl
        self.timeout = timeout
        self._headers = {
            "X-ApiKeys": f"accessKey={access_key}; secretKey={secret_key}",
            "Accept": "application/json",
            "User-Agent": "vapt-platform/1.0",
        }
        self._sem = asyncio.Semaphore(5)

    async def _get(self, path: str, **params) -> Any:
        async with self._sem:
            async with httpx.AsyncClient(
                verify=self.verify_ssl, timeout=self.timeout, follow_redirects=True,
            ) as c:
                r = await c.get(f"{self.base_url}{path}", headers=self._headers, params=params)
                r.raise_for_status()
                return r.json()

    async def _post(self, path: str, body: dict | None = None) -> Any:
        async with self._sem:
            async with httpx.AsyncClient(
                verify=self.verify_ssl, timeout=self.timeout, follow_redirects=True,
            ) as c:
                r = await c.post(f"{self.base_url}{path}", headers=self._headers, json=body or {})
                r.raise_for_status()
                return r.json()

    # ------- public API (mirrors the legacy .env-driven tool) -------

    async def list_scans(self, only_completed: bool = True) -> list[dict]:
        """Return a list of scans. Each dict has id, name, status, etc."""
        data = await self._get("/scans")
        scans = data.get("scans", []) or []
        if only_completed:
            scans = [s for s in scans if s.get("status") == "completed"]
        return scans

    async def get_scan(self, scan_id: int) -> dict:
        return await self._get(f"/scans/{scan_id}")

    async def export_scan(self, scan_id: int, fmt: str = "nessus") -> str:
        """Request an export; returns the export token (the legacy
        pattern is: status -> ready -> download)."""
        data = await self._post(f"/scans/{scan_id}/export", {"format": fmt})
        return str(data.get("token") or data.get("file") or "")

    async def export_status(self, scan_id: int, token: str, fmt: str = "nessus") -> str:
        """Poll the export status. Returns the file id when ready, or ''."""
        data = await self._get(f"/scans/{scan_id}/export/{token}/status")
        if str(data.get("status", "")) == "ready":
            return str(data.get("file", ""))
        return ""

    async def download_export(self, scan_id: int, file_id: int) -> bytes:
        async with self._sem:
            async with httpx.AsyncClient(
                verify=self.verify_ssl, timeout=self.timeout, follow_redirects=True,
            ) as c:
                r = await c.get(
                    f"{self.base_url}/scans/{scan_id}/export/{file_id}/download",
                    headers=self._headers,
                )
                r.raise_for_status()
                return r.content

    async def health(self) -> dict:
        return await self._get("/server/status")


# ---------------------------------------------------------------------------
# High-level helpers used by the router / worker
# ---------------------------------------------------------------------------

async def client_for(server) -> NessusClient:
    """Build a NessusClient from a NessusServer ORM row."""
    return NessusClient(
        base_url=server.base_url,
        access_key=_decrypt(server.access_key_ciphertext),
        secret_key=_decrypt(server.secret_key_ciphertext),
        verify_ssl=server.verify_ssl,
        timeout=server.request_timeout,
    )


async def refresh_scan_cache(db, server, *, force: bool = False) -> int:
    """Pull scan list and upsert into nessus_scan_cache."""
    from app.models.nessus import NessusScanCache
    from sqlalchemy import select
    cli = await client_for(server)
    scans = await cli.list_scans(only_completed=server.only_completed_scans)
    now = datetime.now(timezone.utc)
    n = 0
    for s in scans:
        sid = int(s["id"])
        existing = await db.scalar(
            select(NessusScanCache).where(
                NessusScanCache.server_id == server.id,
                NessusScanCache.scan_id == sid,
            )
        )  # type: ignore[arg-type]
        if not existing:
            existing = NessusScanCache(server_id=server.id, scan_id=sid)
            db.add(existing)
        existing.name = s.get("name", "")[:400]
        existing.status = s.get("status", "")
        existing.policy = s.get("policy")
        existing.scan_type = s.get("scan_type")
        existing.target = s.get("target")
        existing.last_fetched_at = now
        n += 1
    server.last_sync_at = now
    server.last_sync_status = "ok"
    server.last_sync_error = None
    return n


async def export_and_ingest(db, server, scan_id: int, engagement_id: uuid.UUID) -> int:
    """Run the export → poll → download → parse → dedup → upsert pipeline.
    Returns the number of new findings created."""
    from app.services.ingestion import nessus
    from app.services.ingestion.service import process
    from app.models.ingestion import IngestionJob
    cli = await client_for(server)
    token = await cli.export_scan(scan_id, fmt="nessus")
    if not token:
        raise RuntimeError("export token missing")
    # poll for readiness (max 5 minutes)
    file_id = 0
    for _ in range(60):
        await asyncio.sleep(5)
        file_id_s = await cli.export_status(scan_id, token, fmt="nessus")
        if file_id_s:
            file_id = int(file_id_s)
            break
    if not file_id:
        raise RuntimeError("export did not become ready in time")
    blob = await cli.download_export(scan_id, file_id)
    job = IngestionJob(
        workspace_id=server.workspace_id, engagement_id=engagement_id,
        source="nessus_api", source_filename=f"nessus_scan_{scan_id}.nessus",
        format="nessus", status="queued",
    )
    db.add(job)
    await db.flush()
    await process(db, job=job, blob=blob)
    return job.new_findings
