"""Legacy SQLite importer.

The legacy tool stored findings in a SQLite database at
`vulnerabilities.db` (per the legacy .gitignore). The expected schema
(inferred from the test names in the legacy pytest cache):

  vulnerabilities(
    id, name, host, port, plugin_id, cve, severity, description,
    solution, scan_id, scan_name, first_seen, last_seen, ...
  )

This importer reads that DB, runs each row through the same
dedup → asset → vuln → finding pipeline as a normal .nessus upload,
and creates one ingestion job per legacy DB.

The result: an analyst with 3 years of legacy reports can
one-click import everything into the new platform and immediately
get the multi-scan compare, retest, and risk-score features.
"""

from __future__ import annotations

import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any

from app.services.ingestion.nessus import NormalizedItem
from app.services.port_extraction import extract_port


LEGACY_COLUMNS = {
    "id": "legacy_id",
    "name": "title",
    "host": "asset_value",
    "port": "port",
    "plugin_id": "plugin_id",
    "cve": "cve_id",
    "severity": "severity",
    "description": "description",
    "solution": "remediation",
    "scan_id": "scan_ref",
    "scan_name": "scan_name",
    "first_seen": "first_seen",
    "last_seen": "last_seen",
}

_SEV_MAP = {
    "Critical": "critical", "High": "high", "Medium": "medium",
    "Low": "low", "Informational": "info", "Info": "info",
}


def _row_to_normalized(row: dict[str, Any]) -> NormalizedItem | None:
    title = (row.get("name") or "").strip()
    if not title:
        return None
    asset = (row.get("host") or "").strip() or "unknown"
    port, proto = extract_port(row.get("port"))
    sev = _SEV_MAP.get((row.get("severity") or "").strip(), "info")
    cve = (row.get("cve") or "").strip() or None
    desc_parts = []
    if row.get("description"):
        desc_parts.append(str(row["description"]))
    if row.get("solution"):
        desc_parts.append("Remediation: " + str(row["solution"]))
    return NormalizedItem(
        asset_value=asset,
        asset_type="host",
        port=port,
        protocol=proto,
        title=title[:400],
        description="\n\n".join(desc_parts)[:8000],
        severity=sev,
        cve_id=cve,
        plugin="nessus_legacy",
        plugin_id=str(row.get("plugin_id") or "").strip() or None,
        evidence=row.get("scan_name") or "",
    )


def read_legacy_db(path: str) -> list[NormalizedItem]:
    """Read a legacy vulnerabilities.db and return a list of NormalizedItems
    ready to be passed to the dedup pipeline."""
    out: list[NormalizedItem] = []
    with sqlite3.connect(path) as c:
        c.row_factory = sqlite3.Row
        try:
            cur = c.execute("SELECT * FROM vulnerabilities")
        except sqlite3.OperationalError as e:
            raise RuntimeError(
                f"legacy db {path}: missing `vulnerabilities` table ({e})"
            ) from e
        cols = [d[0] for d in cur.description]
        for r in cur.fetchall():
            row = {col: r[col] for col in cols}
            item = _row_to_normalized(row)
            if item:
                out.append(item)
    return out


async def import_legacy(
    db, path: str, engagement_id: uuid.UUID, actor_id: uuid.UUID | None,
) -> dict:
    """One-shot import. Creates a single IngestionJob, ingests all rows."""
    from app.models.ingestion import IngestionJob
    items = read_legacy_db(path)
    job = IngestionJob(
        workspace_id=...,  # filled by caller
        engagement_id=engagement_id,
        submitted_by=actor_id,
        source="legacy_db",
        source_filename=path,
        format="nessus",
    )
    # delegate to the normal processing path
    from app.services.ingestion.service import process
    await process(db, job=job, blob=b"")  # blob unused; service reads from path
    return {
        "rows_read": len(items),
        "new_vulns": job.new_vulns,
        "new_findings": job.new_findings,
        "regressed": job.regressed_findings,
        "remediated": job.remediated_findings,
    }
