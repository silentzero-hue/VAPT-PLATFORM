"""Ingestion orchestrator: parse → dedup → upsert (asset, vuln, finding)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset
from app.models.engagement import Engagement
from app.models.finding import Finding, FindingActivity, FindingStatus
from app.models.ingestion import (
    IngestionFormat,
    IngestionJob,
    IngestionStatus,
)
from app.models.vulnerability import Vulnerability
from app.services.dedup.engine import find_or_create
from app.services.risk.score import compute_risk
from app.services.ingestion.formats import detect_format
from app.services.ingestion import (
    aws_inspector,
    burp,
    kube_bench,
    metasploit,
    nessus,
    nikto,
    nmap,
    nuclei,
    openvas,
    prowler,
    qualys,
    sarif,
    sbom,
    snyk,
    testssl,
    trivy,
    wpscan,
    zap,
)


# Re-export detect_format so existing callers keep working.
__all__ = ["detect_format", "process"]


def _parse_for_format(fmt: IngestionFormat, blob: bytes):
    if fmt == IngestionFormat.NESSUS:
        return nessus.parse(blob)
    if fmt == IngestionFormat.NMAP:
        return nmap.parse(blob)
    if fmt == IngestionFormat.BURP:
        return burp.parse(blob)
    if fmt == IngestionFormat.ZAP:
        return zap.parse(blob)
    if fmt == IngestionFormat.SARIF:
        return sarif.parse(blob)
    if fmt == IngestionFormat.NUCLEI:
        return nuclei.parse(blob)
    if fmt == IngestionFormat.OPENVAS:
        return openvas.parse(blob)
    if fmt == IngestionFormat.QUALYS:
        return qualys.parse(blob)
    if fmt == IngestionFormat.TRIVY:
        return trivy.parse(blob)
    if fmt == IngestionFormat.SNYK:
        return snyk.parse(blob)
    if fmt == IngestionFormat.PROWLER:
        return prowler.parse(blob)
    if fmt == IngestionFormat.TESTSSL:
        return testssl.parse(blob)
    if fmt == IngestionFormat.WPSCAN:
        return wpscan.parse(blob)
    if fmt == IngestionFormat.NIKTO:
        return nikto.parse(blob)
    if fmt == IngestionFormat.METASPLOIT:
        return metasploit.parse(blob)
    if fmt == IngestionFormat.AWS_INSPECTOR:
        return aws_inspector.parse(blob)
    if fmt == IngestionFormat.KUBE_BENCH:
        return kube_bench.parse(blob)
    if fmt == IngestionFormat.CYCLONEDX:
        # SBOM is a different shape; not a NormalizedItem list.
        # Convert each component to an info-level NormalizedItem so the
        # dedup pipeline can still record the asset surface.
        return _sbom_to_items(blob, "cyclonedx")
    if fmt == IngestionFormat.SPDX:
        return _sbom_to_items(blob, "spdx")
    raise ValueError(f"unsupported format: {fmt}")


def _sbom_to_items(blob: bytes, which: str):
    """Map a CycloneDX/SPDX component list to NormalizedItem info-severity
    entries so the dedup pipeline still records the surface area. Real
    vulnerability matching is a background job (per sbom.py docstring)."""
    if which == "cyclonedx":
        components = sbom.parse_cyclonedx(blob)
    else:
        components = sbom.parse_spdx(blob)
    out = []
    for c in components:
        out.append({
            "asset_value": c.name,
            "asset_type": "package",
            "title": f"Component: {c.name}" + (f" {c.version}" if c.version else ""),
            "description": (c.purl or "") + ("\n" + c.cpe if c.cpe else ""),
            "severity": "info",
            "plugin": which,
            "plugin_id": c.purl or c.name,
            "extra": {"ecosystem": c.ecosystem, "licenses": c.licenses},
        })
    return _coerce_items(out)


def _coerce_items(raw: list) -> list:
    """SBOM items are plain dicts; normalise to NormalizedItem."""
    from app.services.ingestion.nessus import NormalizedItem
    out = []
    for it in raw:
        if isinstance(it, NormalizedItem):
            out.append(it)
            continue
        if isinstance(it, dict):
            out.append(NormalizedItem(
                asset_value=it["asset_value"],
                asset_type=it.get("asset_type", "host"),
                title=it.get("title", ""),
                description=it.get("description", ""),
                severity=it.get("severity", "info"),
                plugin=it.get("plugin"),
                plugin_id=it.get("plugin_id"),
                extra=it.get("extra", {}),
            ))
    return out


async def process(
    db: AsyncSession,
    *,
    job: IngestionJob,
    blob: bytes,
) -> None:
    """The worker's main entrypoint. Idempotent. Re-running on the
    same data must converge to the same final state."""
    job.status = IngestionStatus.PARSING
    job.started_at = datetime.now(timezone.utc)
    job.log.append({"ts": job.started_at.isoformat(), "msg": "parsing started"})

    engagement = await db.scalar(
        select(Engagement)
        .where(Engagement.id == job.engagement_id)
        .with_for_update()
    )
    if not engagement:
        job.status = IngestionStatus.FAILED
        job.error = "engagement not found"
        return
    if engagement.ingestion_locked:
        job.status = IngestionStatus.FAILED
        job.error = "engagement ingestion is locked"
        return

    # 1) Parse to NormalizedItem
    try:
        items = _parse_for_format(job.format, blob)
    except ValueError as e:
        job.status = IngestionStatus.FAILED
        job.error = str(e)
        return
    except Exception as e:  # noqa: BLE001
        job.status = IngestionStatus.FAILED
        job.error = f"parse error: {e}"
        return

    job.raw_items = len(items)
    job.parsed_items = len(items)
    job.status = IngestionStatus.DEDUPING
    job.log.append({"ts": datetime.now(timezone.utc).isoformat(),
                    "msg": f"parsed {len(items)} items, starting dedup"})

    # 2) Dedup & upsert
    new_v = new_f = upd_f = reg_f = rem_f = 0
    for it in items:
        vuln, created, requires_review = await find_or_create(
            db, workspace_id=job.workspace_id,
            title=it.title, description=it.description,
            cve_id=it.cve_id, cwe_id=it.cwe_id,
            plugin=it.plugin, plugin_id=it.plugin_id,
            severity=it.severity, cvss_score=it.cvss_score, extra=it.extra,
        )
        if created:
            new_v += 1

        asset = await _upsert_asset(db, job.workspace_id, it)

        finding = await db.scalar(
            select(Finding).where(
                Finding.vulnerability_id == vuln.id,
                Finding.asset_id == asset.id,
                Finding.engagement_id == job.engagement_id,
                Finding.port == it.port,
            )
        )
        now = datetime.now(timezone.utc)
        if not finding:
            finding = Finding(
                workspace_id=job.workspace_id,
                engagement_id=job.engagement_id,
                vulnerability_id=vuln.id, asset_id=asset.id,
                port=it.port, protocol=it.protocol,
                evidence_ref=it.evidence,
                raw_output=it.evidence,
                status=FindingStatus.NEW,
                first_seen=now, last_seen=now,
                extra=it.extra,
            )
            if requires_review:
                finding.extra["dedup_requires_review"] = True
            db.add(finding)
            await db.flush()
            db.add(FindingActivity(
                finding_id=finding.id, actor_id=job.submitted_by,
                action="create", detail={"source": "ingestion"},
            ))
            new_f += 1
        else:
            finding.last_seen = now
            finding.raw_output = it.evidence or finding.raw_output
            if finding.status in (FindingStatus.RESOLVED, FindingStatus.FALSE_POSITIVE,
                                  FindingStatus.RESOLVED_PENDING_CONFIRMATION):
                finding.status = FindingStatus.REGRESSED
                db.add(FindingActivity(
                    finding_id=finding.id, actor_id=job.submitted_by,
                    action="regressed", detail={"source": "ingestion"},
                ))
                reg_f += 1
            else:
                upd_f += 1

        age_days = (datetime.now(timezone.utc) - finding.first_seen).days if finding.first_seen else None
        sev_val = finding.severity_override if finding.severity_override else (vuln.severity.value if hasattr(vuln.severity, 'value') else vuln.severity)
        crit_val = asset.criticality.value if hasattr(asset.criticality, 'value') else asset.criticality
        cvss_val = finding.cvss_score_override if finding.cvss_score_override else vuln.cvss_score
        r = compute_risk(
            severity=sev_val,
            asset_criticality=crit_val,
            cvss_score=cvss_val,
            epss_score=None,
            kev_listed=False,
            age_days=age_days,
        )
        finding.risk_score = r.final
        finding.risk_components = r.to_dict()

    rem_f = await _mark_remediated(db, job, items)

    job.new_vulns = new_v
    job.merged_vulns = 0
    job.new_findings = new_f
    job.updated_findings = upd_f
    job.regressed_findings = reg_f
    job.remediated_findings = rem_f
    job.status = IngestionStatus.DONE
    job.finished_at = datetime.now(timezone.utc)
    job.log.append({"ts": job.finished_at.isoformat(),
                    "msg": f"done: new_v={new_v} new_f={new_f} upd={upd_f} "
                           f"reg={reg_f} rem={rem_f}"})


async def _upsert_asset(
    db: AsyncSession, workspace_id: uuid.UUID, it
) -> Asset:
    existing = await db.scalar(
        select(Asset).where(
            Asset.workspace_id == workspace_id,
            Asset.type == it.asset_type,
            Asset.value == it.asset_value,
            Asset.port == it.port,
        )
    )
    now = datetime.now(timezone.utc)
    if existing:
        existing.last_seen = now
        if it.port is not None:
            existing.port = it.port
        return existing
    a = Asset(
        workspace_id=workspace_id,
        type=it.asset_type, value=it.asset_value,
        port=it.port, protocol=it.protocol,
        first_seen=now, last_seen=now,
    )
    db.add(a)
    await db.flush()
    return a


async def _mark_remediated(db, job, items) -> int:
    eng = await db.get(Engagement, job.engagement_id)
    if not eng:
        return 0
    prior = (eng.extra or {}).get("last_ingest_keys", [])
    _SEP = "\x1f"
    current = sorted({
        f"{i.asset_type}{_SEP}{i.asset_value}{_SEP}{i.port}" for i in items
    })
    missing = set(prior) - set(current)
    rem_count = 0
    if missing:
        for m in missing:
            t, v, p = m.split(_SEP, 2)
            port = int(p) if p.isdigit() else None
            finding = await db.scalar(
                select(Finding).where(
                    Finding.engagement_id == eng.id,
                    Finding.workspace_id == eng.workspace_id,
                ).join(Asset, Asset.id == Finding.asset_id).where(
                    Asset.type == t, Asset.value == v, Asset.port == port,
                )
            )
            if finding and finding.status not in (
                FindingStatus.RESOLVED,
                FindingStatus.FALSE_POSITIVE,
                FindingStatus.RESOLVED_PENDING_CONFIRMATION,
                FindingStatus.REGRESSED,
            ):
                finding.status = FindingStatus.RESOLVED_PENDING_CONFIRMATION
                db.add(FindingActivity(
                    finding_id=finding.id, actor_id=job.submitted_by,
                    action="remediated_pending_confirmation",
                    detail={"source": "ingestion"},
                ))
                rem_count += 1
    eng.extra = {**(eng.extra or {}), "last_ingest_keys": current}
    return rem_count
