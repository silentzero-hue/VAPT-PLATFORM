"""MCP server: 8 tools the agent can call.

These are the *only* way the AI agent touches the platform's data.
The agent must never hit the database directly. Every tool call is
written to audit_log with the agent session id.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

import uvicorn
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.config import settings
from app.core.db import SessionLocal
from app.core.logging import configure_logging, get_logger
from app.models.asset import Asset
from app.models.engagement import Engagement
from app.models.finding import Finding, FindingStatus
from app.models.report import Report, ReportStatus, ReportVersion
from app.models.user import AuditLog
from app.models.vulnerability import Vulnerability
from app.services.dedup.engine import similarity_search
from app.services.reporting.render import build_report_context, render_docx
from app.services import storage

log = get_logger(__name__)
app = FastAPI(title="VAPT MCP Server", version="0.1.0")


# ---------- request/response models (the wire contract) ----------

class ToolCall(BaseModel):
    tool: str
    args: dict = Field(default_factory=dict)
    agent_session_id: str = Field(min_length=1, max_length=80)
    workspace_id: str | None = None
    actor_id: str | None = None


class ToolResult(BaseModel):
    ok: bool
    data: Any = None
    error: str | None = None


# ---------- helpers ----------

async def _audit(agent_session_id: str, workspace_id: str | None, action: str, extra: dict):
    async with SessionLocal() as db:
        db.add(AuditLog(
            workspace_id=uuid.UUID(workspace_id) if workspace_id else None,
            actor_role="agent",
            action=f"mcp.{action}",
            agent_session_id=agent_session_id,
            extra=extra,
        ))
        await db.commit()


# ---------- tool implementations ----------

async def list_findings(args: dict) -> dict:
    engagement_id = uuid.UUID(args["engagement_id"])
    status = args.get("status")
    severity = args.get("severity")
    async with SessionLocal() as db:
        e = await db.get(Engagement, engagement_id)
        if not e:
            return {"error": "engagement not found"}
        stmt = select(Finding).where(Finding.engagement_id == engagement_id)
        if status:
            try:
                stmt = stmt.where(Finding.status == FindingStatus(status))
            except ValueError:
                return {"error": f"bad status {status}"}
        rows = (await db.execute(stmt.limit(2000))).scalars().all()
        out: list[dict] = []
        for f in rows:
            v = await db.get(Vulnerability, f.vulnerability_id)
            a = await db.get(Asset, f.asset_id)
            out.append({
                "finding_id": str(f.id),
                "vulnerability_id": str(f.vulnerability_id),
                "asset_value": a.value if a else None,
                "asset_type": a.type.value if a else None,
                "port": f.port,
                "status": f.status.value,
                "severity": (f.severity_override or (v.severity.value if v else "info")),
                "title": v.title if v else "(deleted)",
                "cve_id": v.cve_id if v else None,
            })
        if severity:
            out = [x for x in out if x["severity"] == severity]
        return {"items": out, "total": len(out)}


async def get_vulnerability(args: dict) -> dict:
    vid = uuid.UUID(args["vulnerability_id"])
    async with SessionLocal() as db:
        v = await db.get(Vulnerability, vid)
        if not v:
            return {"error": "vuln not found"}
        findings = (await db.execute(
            select(Finding).where(Finding.vulnerability_id == vid)
        )).scalars().all()
        linked: list[dict] = []
        for f in findings:
            a = await db.get(Asset, f.asset_id)
            linked.append({
                "asset_id": str(a.id) if a else None,
                "asset_value": a.value if a else None,
                "asset_type": a.type.value if a else None,
                "port": f.port,
                "engagement_id": str(f.engagement_id),
                "finding_id": str(f.id),
                "status": f.status.value,
            })
        return {
            "id": str(v.id),
            "title": v.title,
            "description": v.description,
            "cve_id": v.cve_id,
            "cwe_id": v.cwe_id,
            "severity": v.severity.value,
            "cvss_score": v.cvss_score,
            "confidence": v.confidence.value,
            "tags": v.tags,
            "references": v.references,
            "occurrence_count": v.occurrence_count,
            "linked_assets": linked,
            "ai_draft_impact": v.ai_draft_impact,
            "ai_draft_recommendation": v.ai_draft_recommendation,
        }


async def get_asset_context(args: dict) -> dict:
    aid = uuid.UUID(args["asset_id"])
    async with SessionLocal() as db:
        a = await db.get(Asset, aid)
        if not a:
            return {"error": "asset not found"}
        n = (await db.execute(
            select(Finding).where(Finding.asset_id == aid)
        )).scalars().all()
        return {
            "id": str(a.id),
            "value": a.value,
            "type": a.type.value,
            "criticality": a.criticality.value,
            "owner": a.owner,
            "business_unit": a.business_unit,
            "prior_findings_count": len(n),
            "first_seen": a.first_seen.isoformat(),
            "last_seen": a.last_seen.isoformat(),
        }


async def check_duplicate(args: dict) -> dict:
    title = args.get("title", "")
    description = args.get("description", "")
    workspace_id = args.get("workspace_id")
    if not workspace_id:
        return {"error": "workspace_id required"}
    async with SessionLocal() as db:
        sims = await similarity_search(
            db, uuid.UUID(workspace_id), title, description, threshold=0.5
        )
        if not sims:
            return {"is_duplicate": False, "similarity": 0.0}
        best_id, best_sim = sims[0]
        return {
            "is_duplicate": best_sim >= 0.93,
            "needs_review": 0.80 <= best_sim < 0.93,
            "similarity": float(best_sim),
            "matched_vulnerability_id": str(best_id),
            "top_matches": [{"id": str(i), "similarity": float(s)} for i, s in sims[:5]],
        }


async def draft_finding_narrative(args: dict) -> dict:
    vid = uuid.UUID(args["vulnerability_id"])
    impact = args.get("impact_text", "")
    recommendation = args.get("recommendation_text", "")
    async with SessionLocal() as db:
        v = await db.get(Vulnerability, vid)
        if not v:
            return {"error": "vuln not found"}
        v.ai_draft_impact = impact
        v.ai_draft_recommendation = recommendation
        from datetime import datetime, timezone
        v.ai_drafted_at = datetime.now(timezone.utc)
        v.ai_draft_approved = False  # human must approve
        await db.commit()
        return {"ok": True, "vulnerability_id": str(v.id)}


async def generate_exec_summary_stats(args: dict) -> dict:
    eid = uuid.UUID(args["engagement_id"])
    async with SessionLocal() as db:
        e = await db.get(Engagement, eid)
        if not e:
            return {"error": "engagement not found"}
        findings = (await db.execute(
            select(Finding).where(Finding.engagement_id == eid)
        )).scalars().all()
        sev: dict[str, int] = {}
        for f in findings:
            v = await db.get(Vulnerability, f.vulnerability_id)
            s = f.severity_override or (v.severity.value if v else "info")
            sev[s] = sev.get(s, 0) + 1
        # top risk assets
        asset_count: dict[str, int] = {}
        for f in findings:
            a = await db.get(Asset, f.asset_id)
            if a:
                asset_count[a.value] = asset_count.get(a.value, 0) + 1
        top_assets = sorted(asset_count.items(), key=lambda kv: -kv[1])[:10]
        return {
            "engagement_id": str(eid),
            "total_findings": len(findings),
            "by_severity": sev,
            "top_assets": [{"value": v, "count": c} for v, c in top_assets],
            "unique_vulns": len({f.vulnerability_id for f in findings}),
        }


async def render_report(args: dict) -> dict:
    eid = uuid.UUID(args["engagement_id"])
    template_id = args.get("template_id")
    async with SessionLocal() as db:
        e = await db.get(Engagement, eid)
        if not e:
            return {"error": "engagement not found"}
        if e.status.value == "cancelled":
            return {"error": "engagement cancelled"}
        # Find or create a Report
        rep = (await db.execute(
            select(Report).where(Report.engagement_id == eid).order_by(Report.created_at.desc())
        )).scalars().first()
        if not rep:
            rep = Report(
                workspace_id=e.workspace_id, engagement_id=eid,
                title=f"{e.name} — Report",
                status=ReportStatus.DRAFTING,
            )
            db.add(rep)
            await db.flush()
        rep.template_id = uuid.UUID(template_id) if template_id else None
        ctx = await build_report_context(db, eid)
        signed = {
            "workspace_id": str(rep.workspace_id),
            "engagement_id": str(eid),
            "report_id": str(rep.id),
            "signer": "agent (draft)",
            "signed_at": None,
            "version_no": max((v.version_no for v in rep.versions), default=0) + 1,
        }
        docx = render_docx(ctx, signed=signed)
        last_no = max((v.version_no for v in rep.versions), default=0)
        key = f"reports/{eid}/{rep.id}/v{last_no+1}.docx"
        sha, size = await storage.put_bytes(
            key, docx,
            content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )
        v = ReportVersion(
            report_id=rep.id, version_no=last_no+1,
            status=ReportStatus.PENDING_REVIEW,
            s3_key=key, sha256=sha, size=size,
            agent_session_id=args.get("_agent_session_id"),
            note="auto-drafted by agent",
            draft_payload=ctx,
        )
        db.add(v)
        rep.status = ReportStatus.PENDING_REVIEW
        rep.current_version_id = None  # assigned on approval
        await db.flush()
        return {
            "report_id": str(rep.id),
            "version_id": str(v.id),
            "file_ref": key,
            "sha256": sha,
            "size": size,
            "status": "draft",
        }


async def flag_for_human_review(args: dict) -> dict:
    rid = uuid.UUID(args["report_id"])
    notes = args.get("notes")
    async with SessionLocal() as db:
        r = await db.get(Report, rid)
        if not r:
            return {"error": "report not found"}
        if r.status == ReportStatus.APPROVED or r.locked:
            return {"error": "report already approved/locked"}
        if r.status not in (ReportStatus.PENDING_REVIEW, ReportStatus.DRAFTING):
            return {"error": f"cannot flag in status {r.status.value}"}
        r.status = ReportStatus.PENDING_REVIEW
        db.add(AuditLog(
            workspace_id=r.workspace_id, actor_role="agent",
            action="report.flag_for_human_review",
            target_type="report", target_id=r.id,
            extra={"notes": notes},
            agent_session_id=args.get("_agent_session_id"),
        ))
        return {"ok": True, "status": "pending_review"}


# ---------- dispatch ----------

TOOLS: dict[str, Any] = {
    "list_findings": list_findings,
    "get_vulnerability": get_vulnerability,
    "get_asset_context": get_asset_context,
    "check_duplicate": check_duplicate,
    "draft_finding_narrative": draft_finding_narrative,
    "generate_exec_summary_stats": generate_exec_summary_stats,
    "render_report": render_report,
    "flag_for_human_review": flag_for_human_review,
}


@app.get("/healthz")
async def healthz():
    return {"ok": True}


@app.post("/tools/call", response_model=ToolResult)
async def call_tool(req: ToolCall, request: Request):
    fn = TOOLS.get(req.tool)
    if not fn:
        raise HTTPException(404, f"unknown tool {req.tool}")
    args = dict(req.args)
    args["_agent_session_id"] = req.agent_session_id
    try:
        data = await fn(args)
    except Exception as e:  # noqa: BLE001
        log.exception("mcp_tool_error", tool=req.tool, err=str(e))
        await _audit(req.agent_session_id, req.workspace_id, f"tool.{req.tool}.error",
                     {"err": str(e), "args": req.args})
        return ToolResult(ok=False, error=str(e))
    await _audit(req.agent_session_id, req.workspace_id, f"tool.{req.tool}",
                 {"args": req.args, "result_keys": list(data.keys()) if isinstance(data, dict) else None})
    return ToolResult(ok=True, data=data)


@app.get("/tools")
async def list_tools():
    return {"tools": sorted(TOOLS.keys())}


def main():
    configure_logging()
    uvicorn.run(app, host="0.0.0.0", port=8081, log_level="info")


if __name__ == "__main__":
    main()
