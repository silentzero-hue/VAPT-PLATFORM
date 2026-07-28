"""Threat intel enrichment. Calls NVD, FIRST EPSS, CISA KEV and caches
the result per (workspace, cve_id) for 24h.

The HTTP clients are lazy-imported so the test suite can run without
network and the package is importable in air-gapped environments.
"""

from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.logging import get_logger
from app.models.threat_intel import ThreatIntelCache

log = get_logger(__name__)

NVD_URL = "https://services.nvd.nist.gov/rest/json/cves/2.0"
EPSS_URL = "https://api.first.org/data/v1/epss"
KEV_URL = "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json"

CACHE_TTL = timedelta(hours=24)
NVD_TIMEOUT = 30.0

_KEV_CACHE: dict[str, Any] = {"data": None, "fetched_at": 0.0}
_KEV_TTL_SEC = 6 * 3600
_KEV_LOCK = asyncio.Lock()


async def _http_get_json(url: str, params: dict | None = None) -> dict:
    async with httpx.AsyncClient(timeout=NVD_TIMEOUT, follow_redirects=True) as c:
        r = await c.get(url, params=params or {})
        r.raise_for_status()
        return r.json()


async def fetch_nvd(cve_id: str) -> dict[str, Any]:
    """Return a normalized NVD record. Empty dict on failure."""
    try:
        data = await _http_get_json(NVD_URL, {"cveId": cve_id})
    except Exception as e:  # noqa: BLE001
        log.warning("nvd_fetch_failed", cve=cve_id, err=str(e))
        return {}
    vulns = data.get("vulnerabilities") or []
    if not vulns:
        return {}
    c = vulns[0].get("cve", {})
    metrics = c.get("metrics", {})
    cvss3 = (metrics.get("cvssMetricV31") or [{}])[0].get("cvssData", {}) if metrics.get("cvssMetricV31") else {}
    cvss2 = (metrics.get("cvssMetricV2") or [{}])[0].get("cvssData", {}) if metrics.get("cvssMetricV2") else {}
    descs = c.get("descriptions", [])
    desc_en = next((d["value"] for d in descs if d.get("lang") == "en"), "")
    refs = [r.get("url") for r in (c.get("references") or []) if r.get("url")]
    return {
        "cvss_v3_vector": cvss3.get("vectorString"),
        "cvss_v3_score": cvss3.get("baseScore"),
        "cvss_v2_score": cvss2.get("baseScore"),
        "nvd_published": c.get("published"),
        "nvd_description": (desc_en or "")[:2000],
        "nvd_references": refs,
    }


async def fetch_epss(cve_id: str) -> dict[str, Any]:
    try:
        data = await _http_get_json(EPSS_URL, {"cve": cve_id})
    except Exception as e:  # noqa: BLE001
        log.warning("epss_fetch_failed", cve=cve_id, err=str(e))
        return {}
    rows = data.get("data") or []
    if not rows:
        return {}
    r = rows[0]
    return {
        "epss_score": float(r.get("epss", 0) or 0),
        "epss_percentile": float(r.get("percentile", 0) or 0),
        "epss_updated": r.get("date"),
    }


async def _get_kev_catalog() -> dict:
    import time
    now = time.time()
    if _KEV_CACHE["data"] is not None and (now - _KEV_CACHE["fetched_at"]) <= _KEV_TTL_SEC:
        return _KEV_CACHE["data"]
    async with _KEV_LOCK:
        now = time.time()
        if _KEV_CACHE["data"] is not None and (now - _KEV_CACHE["fetched_at"]) <= _KEV_TTL_SEC:
            return _KEV_CACHE["data"]
        data = await _http_get_json(KEV_URL)
        _KEV_CACHE["data"] = data
        _KEV_CACHE["fetched_at"] = now
        return data


async def fetch_kev(cve_id: str) -> dict[str, Any]:
    try:
        data = await _get_kev_catalog()
    except Exception as e:  # noqa: BLE001
        log.warning("kev_fetch_failed", err=str(e))
        return {}
    for v in data.get("vulnerabilities", []):
        if v.get("cveID") == cve_id:
            return {
                "kev_listed": True,
                "kev_added_at": v.get("dateAdded"),
                "kev_due_date": v.get("dueDate"),
                "kev_ransomware_use": "Known" in (v.get("knownRansomwareCampaignUse") or ""),
            }
    return {"kev_listed": False}


async def enrich_one(db: AsyncSession, workspace_id: uuid.UUID, cve_id: str) -> ThreatIntelCache:
    """Enrich a single CVE; cache the result."""
    existing = await db.scalar(
        select(ThreatIntelCache).where(
            ThreatIntelCache.workspace_id == workspace_id,
            ThreatIntelCache.cve_id == cve_id,
        )
    )
    now = datetime.now(timezone.utc)
    if existing and existing.next_refresh_after > now:
        return existing

    # fan out
    nvd, epss, kev = await asyncio.gather(
        fetch_nvd(cve_id), fetch_epss(cve_id), fetch_kev(cve_id),
    )
    rec = existing or ThreatIntelCache(
        workspace_id=workspace_id, cve_id=cve_id,
        fetched_at=now, next_refresh_after=now,
    )
    rec.nvd_description = nvd.get("nvd_description") or rec.nvd_description
    rec.nvd_references = nvd.get("nvd_references") or rec.nvd_references or []
    if nvd.get("cvss_v3_vector"):
        rec.cvss_v3_vector = nvd["cvss_v3_vector"]
        rec.cvss_v3_score = nvd.get("cvss_v3_score")
    if nvd.get("cvss_v2_score"):
        rec.cvss_v2_score = nvd["cvss_v2_score"]
    if nvd.get("nvd_published"):
        np = nvd["nvd_published"]
        if isinstance(np, str):
            try:
                np = datetime.fromisoformat(np.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                np = None
        rec.nvd_published = np
    if epss.get("epss_score") is not None:
        rec.epss_score = epss["epss_score"]
        rec.epss_percentile = epss.get("epss_percentile")
        eu = epss.get("epss_updated")
        if isinstance(eu, str):
            try:
                eu = datetime.fromisoformat(eu.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                eu = None
        rec.epss_updated = eu
    if kev:
        rec.kev_listed = bool(kev.get("kev_listed", rec.kev_listed))
        ka = kev.get("kev_added_at") or rec.kev_added_at
        if isinstance(ka, str):
            try:
                ka = datetime.fromisoformat(ka.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass
        rec.kev_added_at = ka
        kd = kev.get("kev_due_date") or rec.kev_due_date
        if isinstance(kd, str):
            try:
                kd = datetime.fromisoformat(kd.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                pass
        rec.kev_due_date = kd
        rec.kev_ransomware_use = bool(kev.get("kev_ransomware_use", rec.kev_ransomware_use))
    rec.fetched_at = now
    rec.next_refresh_after = now + CACHE_TTL
    rec.fetch_attempts = (rec.fetch_attempts or 0) + 1
    if not existing:
        db.add(rec)
    await db.flush()
    return rec


async def enrich_workspace_cves(db: AsyncSession, workspace_id: uuid.UUID, cves: list[str]) -> int:
    """Enrich a batch of CVEs with bounded concurrency. Returns count."""
    sem = asyncio.Semaphore(4)
    async def _one(c: str):
        async with sem:
            try:
                await enrich_one(db, workspace_id, c)
            except Exception as e:  # noqa: BLE001
                log.warning("enrich_failed", cve=c, err=str(e))
    await asyncio.gather(*[_one(c) for c in cves])
    return len(cves)
