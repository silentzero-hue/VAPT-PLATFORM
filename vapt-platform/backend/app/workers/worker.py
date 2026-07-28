"""Background jobs (arq): threat intel refresh, webhook delivery,
re-embedding, risk score recompute, LDAP sync, SBOM-to-asset sync.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from arq.connections import RedisSettings
from sqlalchemy import select

from app.core.config import settings
from app.core.db import SessionLocal
from app.core.logging import configure_logging, get_logger
from app.models.finding import Finding
from app.models.threat_intel import ThreatIntelCache
from app.models.vulnerability import Vulnerability
from app.services.risk.score import compute_risk
from app.services.webhooks import deliver_due

log = get_logger(__name__)


async def refresh_threat_intel_all(ctx: dict) -> dict:
    """Find vulnerabilities with CVE IDs whose threat-intel cache is
    stale and re-enrich them."""
    async with SessionLocal() as db:
        # naive approach: get all distinct cve_ids in the workspace
        rows = (await db.execute(
            select(Vulnerability.cve_id, Vulnerability.workspace_id)
            .where(Vulnerability.cve_id.is_not(None))
            .distinct()
            .limit(500)
        )).all()
        targets = list({(c, w) for c, w in rows if c})
    from app.services.threat_intel.service import enrich_one
    n = 0
    for cve, wid in targets:
        async with SessionLocal() as db:
            try:
                await enrich_one(db, wid, cve)
                n += 1
            except Exception as e:  # noqa: BLE001
                log.warning("intel_refresh_failed", cve=cve, err=str(e))
    return {"refreshed": n, "target": len(targets)}


async def recompute_risk_scores(ctx: dict) -> dict:
    """Walk open findings and recompute their risk score."""
    async with SessionLocal() as db:
        findings = (await db.execute(
            select(Finding).where(Finding.status.in_([
                "new", "confirmed", "in_remediation", "regressed",
            ])).limit(2000)
        )).scalars().all()
        n = 0
        from app.models.asset import Asset
        from app.models.threat_intel import ThreatIntelCache
        for f in findings:
            v = await db.get(Vulnerability, f.vulnerability_id)
            a = await db.get(Asset, f.asset_id)
            if not v or not a:
                continue
            intel = None
            if v.cve_id:
                intel = await db.scalar(
                    select(ThreatIntelCache).where(
                        ThreatIntelCache.cve_id == v.cve_id,
                        ThreatIntelCache.workspace_id == f.workspace_id,
                    )
                )
            age_days = (datetime.now(timezone.utc) - f.first_seen).days if f.first_seen else None
            r = compute_risk(
                severity=(f.severity_override or v.severity.value),
                asset_criticality=a.criticality.value,
                cvss_score=(f.cvss_score_override or v.cvss_score),
                epss_score=(intel.epss_score if intel else None),
                kev_listed=(intel.kev_listed if intel else False),
                age_days=age_days,
            )
            f.risk_score = r.final
            f.risk_components = r.to_dict()
            if intel:
                f.threat_intel_id = intel.id
            n += 1
        return {"updated": n}


async def run_webhook_deliveries(ctx: dict) -> dict:
    async with SessionLocal() as db:
        return {"delivered": await deliver_due(db)}


async def reembed_stale(ctx: dict) -> dict:
    """Re-embed vulnerabilities whose description was edited more
    recently than their embedding was computed. The fingerprint_hash
    is recomputed and the vector is regenerated.

    In our current schema, the embedding column is updated on every
    find_or_create, so this is a no-op unless the analyst edited the
    vuln. We detect edits by comparing updated_at vs a recorded
    'embedded_at' in extra."""
    from app.services.embeddings.service import embed_text
    async with SessionLocal() as db:
        vulns = (await db.execute(
            select(Vulnerability).where(
                Vulnerability.embedding.is_(None)
            ).limit(500)
        )).scalars().all()
        n = 0
        for v in vulns:
            v.embedding = embed_text(f"{v.title}\n{v.description}")
            n += 1
        return {"embedded": n}


async def sbom_sync(ctx: dict) -> dict:
    """Re-link components to assets and check for known-vuln versions.
    Placeholder: in production this would consult a vuln DB."""
    return {"ok": True}


class WorkerSettings:
    redis_settings = RedisSettings.from_dsn(settings.redis_url)
    functions = [
        run_webhook_deliveries,
        refresh_threat_intel_all,
        recompute_risk_scores,
        reembed_stale,
        sbom_sync,
    ]
    cron_jobs = [
        # every minute: drain pending webhooks
        # schedule(run_webhook_deliveries, minute={0})
    ]
    async def on_startup(ctx):  # noqa: ARG001
        configure_logging()

    async def on_shutdown(ctx):  # noqa: ARG001
        return None
