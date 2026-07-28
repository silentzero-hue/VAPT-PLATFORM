"""Report router: create, render, approve, download, publish.

Hard rule: ONLY a human (with senior_analyst+ role) can transition a
report to APPROVED. The agent runtime ends at PENDING_REVIEW and never
calls /approve.
"""

from __future__ import annotations

import asyncio
import io
import os
import subprocess
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Query, Request, Response, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import (
    APPROVE_ROLES, ANALYST_ROLES, CurrentUser,
    can_approve_report, can_triage, get_current_user,
)
from app.core.db import get_session
from app.core.logging import get_logger
from app.models.engagement import Engagement
from app.models.finding import Finding
from app.models.report import Report, ReportStatus, ReportVersion
from app.models.user import AuditLog, Role
from app.models.vulnerability import Vulnerability
from app.schemas.report import (
    FindingEdit, FindingSuggestion, ReportApproveRequest, ReportCreate,
    ReportEditRequest, ReportOut, ReportVersionOut, RenderRequest,
    SuggestRequest, SuggestResponse,
)
from app.services import storage
from app.services.reporting.render import (
    _apply_draft, build_report_context, render_docx, render_preview_html,
)

router = APIRouter(prefix="/reports", tags=["reports"])
log = get_logger(__name__)


async def _to_out(r: Report) -> ReportOut:
    from sqlalchemy import inspect
    from sqlalchemy.orm.base import NO_VALUE
    inspected = inspect(r)
    versions_attr = inspected.attrs.versions if "versions" in inspected.attrs else None
    if versions_attr and versions_attr.loaded_value is not NO_VALUE:
        versions = list(versions_attr.loaded_value or [])
    else:
        versions = []
    return ReportOut(
        id=r.id, engagement_id=r.engagement_id, title=r.title,
        status=r.status.value, current_version_id=r.current_version_id,
        signed_sha256=r.signed_sha256, signed_at=r.signed_at, signed_by=r.signed_by,
        locked=r.locked, created_at=r.created_at, updated_at=r.updated_at,
        draft_payload=r.draft_payload or {},
        versions=[ReportVersionOut(
            id=v.id, version_no=v.version_no, status=v.status.value,
            author_id=v.author_id, agent_session_id=v.agent_session_id,
            note=v.note, s3_key=v.s3_key, sha256=v.sha256, size=v.size,
            created_at=v.created_at,
        ) for v in versions],
    )


def _merge_finding_overrides(existing: dict, edits: list[FindingEdit]) -> dict:
    """Merge a list of FindingEdit entries into the existing override map.

    Each entry is keyed by the finding's UUID (string). Setting a field
    to None in the edit removes that field from the stored override.
    Missing fields leave the existing value untouched.
    """
    out = dict(existing or {})
    for ed in edits:
        key = str(ed.finding_id)
        cur = dict(out.get(key) or {})
        for field in ("severity_override", "impact", "recommendation", "note"):
            v = getattr(ed, field)
            if v is None:
                cur.pop(field, None)
            else:
                cur[field] = v
        if cur:
            out[key] = cur
        else:
            out.pop(key, None)
    return out


@router.post("", response_model=ReportOut, status_code=201)
async def create_report(
    body: ReportCreate, request: Request,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    if not can_triage(current.role):
        raise HTTPException(403, "analyst+ required")
    e = await db.get(Engagement, body.engagement_id)
    if not e or e.workspace_id != current.workspace_id:
        raise HTTPException(404, "engagement not found")
    title = body.title or f"{e.name} — Report"
    r = Report(
        workspace_id=current.workspace_id,
        engagement_id=body.engagement_id, template_id=body.template_id,
        title=title, status=ReportStatus.DRAFTING,
    )
    db.add(r)
    db.add(AuditLog(
        workspace_id=current.workspace_id, actor_id=current.user.id,
        actor_role=current.role, action="report.create",
        target_type="report", target_id=r.id,
        ip=request.client.host if request.client else None,
    ))
    await db.flush()
    return await _to_out(r)


@router.get("", response_model=list[ReportOut])
async def list_reports(
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
    engagement_id: uuid.UUID | None = None,
):
    stmt = select(Report).where(Report.workspace_id == current.workspace_id).options(selectinload(Report.versions))
    if engagement_id:
        stmt = stmt.where(Report.engagement_id == engagement_id)
    rows = (await db.execute(stmt.order_by(Report.created_at.desc()))).scalars().all()
    return [await _to_out(r) for r in rows]


@router.get("/{rid}", response_model=ReportOut)
async def get_report(
    rid: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    r = await db.get(Report, rid, options=[selectinload(Report.versions)])
    if not r or r.workspace_id != current.workspace_id:
        raise HTTPException(404, "not found")
    return await _to_out(r)


@router.patch("/{rid}", response_model=ReportOut)
async def edit_report(
    rid: uuid.UUID, body: ReportEditRequest, request: Request,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    """Analyst-side editor: save title, exec summary, overall rating,
    and per-finding overrides. Senior_analyst+ only; locked reports
    cannot be edited."""
    if current.role not in APPROVE_ROLES:
        raise HTTPException(403, "edit requires senior_analyst+")
    r = await db.get(Report, rid, options=[selectinload(Report.versions)])
    if not r or r.workspace_id != current.workspace_id:
        raise HTTPException(404, "not found")
    if r.locked:
        raise HTTPException(409, "report is locked")

    if body.title is not None:
        r.title = body.title
    draft = dict(r.draft_payload or {})
    if body.overall_rating is not None:
        draft["overall_rating"] = body.overall_rating
    if body.exec_summary is not None:
        draft["exec_summary"] = body.exec_summary
    if body.findings is not None:
        draft["finding_overrides"] = _merge_finding_overrides(
            draft.get("finding_overrides") or {}, body.findings,
        )
        # If the override map is now empty, drop the key entirely.
        if not draft["finding_overrides"]:
            draft.pop("finding_overrides")
    r.draft_payload = draft
    db.add(AuditLog(
        workspace_id=r.workspace_id, actor_id=current.user.id, actor_role=current.role,
        action="report.edit", target_type="report", target_id=r.id,
        extra={"has_exec_summary": bool(draft.get("exec_summary")),
               "finding_overrides": len(draft.get("finding_overrides") or {})},
        ip=request.client.host if request.client else None,
    ))
    await db.flush()
    return await _to_out(r)


@router.get("/{rid}/context")
async def report_context(
    rid: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    """Return the auto-built report context for the editor's findings
    table. Draft overrides are NOT applied here — the editor needs the
    original AI-drafted values to show alongside the analyst's edits."""
    r = await db.get(Report, rid)
    if not r or r.workspace_id != current.workspace_id:
        raise HTTPException(404, "not found")
    if not can_triage(current.role):
        raise HTTPException(403, "analyst+ required")
    ctx = await build_report_context(db, r.engagement_id)
    return ctx


@router.get("/{rid}/preview", response_class=Response)
async def preview_report(
    rid: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    """Return an HTML preview of the report, mirroring the docx layout.

    The preview reflects the report's current draft (if any). The analyst
    can iterate on edits and re-fetch the preview to see the result
    without burning a version number.
    """
    r = await db.get(Report, rid)
    if not r or r.workspace_id != current.workspace_id:
        raise HTTPException(404, "not found")
    if not can_triage(current.role):
        raise HTTPException(403, "analyst+ required")
    ctx = await build_report_context(db, r.engagement_id)
    _apply_draft(ctx, r.draft_payload or {})
    html = render_preview_html(ctx)
    return Response(content=html, media_type="text/html; charset=utf-8")


@router.get("/{rid}/preview.pdf", response_class=Response)
async def preview_pdf(
    rid: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    """Return a PDF rendering of the report for high-fidelity preview.

    This is the pixel-perfect preview that mirrors the original DMC
    Technovage docx exactly. The HTML preview at /{rid}/preview stays
    the live-editing surface; this PDF endpoint is the "View in PDF" /
    "Download PDF" action.

    Implementation: render the docx in-memory, write it to a tempdir,
    and call ``libreoffice --headless --convert-to pdf``. Conversion
    typically takes 2-5 seconds; that's acceptable for a deliberate,
    user-initiated action.

    LibreOffice creates a profile under $HOME/.config/libreoffice, so
    we point HOME at the tempdir to avoid touching the real filesystem
    and to isolate concurrent conversions.
    """
    r = await db.get(Report, rid)
    if not r or r.workspace_id != current.workspace_id:
        raise HTTPException(404, "not found")
    if not can_triage(current.role):
        raise HTTPException(403, "analyst+ required")

    ctx = await build_report_context(db, r.engagement_id)
    _apply_draft(ctx, r.draft_payload or {})
    docx_bytes = render_docx(ctx, signed=None)

    with tempfile.TemporaryDirectory() as tmpdir:
        docx_path = Path(tmpdir) / f"{rid}.docx"
        docx_path.write_bytes(docx_bytes)

        def _convert() -> subprocess.CompletedProcess:
            return subprocess.run(
                ["libreoffice", "--headless", "--convert-to", "pdf",
                 "--outdir", tmpdir, str(docx_path)],
                capture_output=True, timeout=60,
                env={**os.environ, "HOME": tmpdir},
            )

        # Don't block the event loop on a 2-5s subprocess.
        result = await asyncio.to_thread(_convert)

        if result.returncode != 0:
            stderr = result.stderr.decode("utf-8", errors="replace")
            log.error("libreoffice_failed", rid=str(rid), stderr=stderr[:1000])
            raise HTTPException(500, "PDF conversion failed")

        pdf_path = docx_path.with_suffix(".pdf")
        if not pdf_path.exists():
            log.error("pdf_not_generated", rid=str(rid), tmpdir=tmpdir)
            raise HTTPException(500, "PDF not generated")

        pdf_bytes = pdf_path.read_bytes()

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="report-{rid}.pdf"'},
    )


@router.post("/{rid}/upload-docx")
async def upload_docx(
    request: Request,
    rid: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
    file: UploadFile = File(...),
):
    """Accept a docx edited externally and extract its narrative back into
    the draft_payload. This is the "edit in Word, upload here" workflow
    that complements the in-app WYSIWYG editor.

    Workflow:
      1. User downloads the rendered docx (POST /reports/{rid}/download).
      2. User edits the docx in Word / LibreOffice / Google Docs.
      3. User uploads the modified docx here.
      4. Backend extracts the "1. Analyst Executive Narrative" section
         (paragraphs following the heading) and updates draft_payload.
      5. User clicks "Preview" to see the changes in the WYSIWYG editor.
    """
    r = await db.get(Report, rid)
    if not r or r.workspace_id != current.workspace_id:
        raise HTTPException(404, "not found")
    if r.locked:
        raise HTTPException(409, "report is locked")
    if not can_triage(current.role):
        raise HTTPException(403, "analyst+ required")
    if not file.filename or not file.filename.lower().endswith(".docx"):
        raise HTTPException(400, "a .docx file is required")

    docx_bytes = await file.read()
    if not docx_bytes:
        raise HTTPException(400, "empty file")

    try:
        from docx import Document as _Doc
        doc = _Doc(io.BytesIO(docx_bytes))
    except Exception as e:
        log.warning("upload_docx_parse_failed", rid=str(rid), error=str(e)[:300])
        raise HTTPException(400, "could not parse .docx file")

    # The narrative is injected by _inject_exec_summary() as a series of
    # paragraphs following the bold heading paragraph
    # "1. Analyst Executive Narrative". We walk the body paragraphs,
    # collect everything after that heading until we hit
    # "DETAILED FINDINGS" (the next major section).
    in_narrative = False
    narrative_paras: list[str] = []
    for p in doc.paragraphs:
        text = p.text.strip()
        if not text:
            continue
        if "Analyst Executive Narrative" in text:
            in_narrative = True
            continue
        if in_narrative:
            # Stop at the next major section. Match either a Heading 1
            # paragraph (preferred — covers "2. DETAILED FINDINGS" and
            # similar numbered headings) or the literal "DETAILED FINDINGS"
            # text (in case the user typed it as a bold paragraph instead
            # of applying a real heading style).
            style_name = ""
            try:
                if p.style is not None:
                    style_name = p.style.name or ""
            except (AttributeError, KeyError):
                style_name = ""
            if style_name.startswith("Heading 1"):
                break
            if "DETAILED FINDINGS" in text.upper():
                break
            narrative_paras.append(text)

    new_exec_summary = "\n\n".join(narrative_paras) if narrative_paras else None

    new_draft = dict(r.draft_payload or {})
    if new_exec_summary:
        new_draft["exec_summary"] = new_exec_summary
    r.draft_payload = new_draft

    db.add(AuditLog(
        workspace_id=r.workspace_id, actor_id=current.user.id,
        actor_role=current.role, action="report.upload_docx",
        target_type="report", target_id=r.id,
        extra={"exec_summary_chars": len(new_exec_summary or "")},
        ip=request.client.host if request.client else None,
    ))

    return {
        "ok": True,
        "exec_summary": new_exec_summary,
        "narrative_paragraphs": len(narrative_paras),
    }


@router.get("/{rid}/suggest/{fid}")
async def suggest_for_finding(
    rid: uuid.UUID,
    fid: uuid.UUID,
    severity: str | None = None,
    db: Annotated[AsyncSession, Depends(get_session)] = ...,  # type: ignore
    current: Annotated[CurrentUser, Depends(get_current_user)] = ...,  # type: ignore
):
    """Return auto-suggested impact / recommendation / action-urgency for a
    single finding, based on its severity, CVSS, and detected category.

    The analyst can then accept the suggestion (it becomes the override)
    or ignore it and write custom text. Suggestions are heuristic; they
    describe the realistic worst-case impact and the standard remediation
    pattern for that class of bug.
    """
    r = await db.get(Report, rid)
    if not r or r.workspace_id != current.workspace_id:
        raise HTTPException(404, "not found")
    if not can_triage(current.role):
        raise HTTPException(403, "analyst+ required")
    f = await db.get(Finding, fid)
    if not f or f.workspace_id != current.workspace_id:
        raise HTTPException(404, "finding not found")
    # Load the vulnerability (may be missing if the join drifted)
    v = await db.get(Vulnerability, f.vulnerability_id) if f.vulnerability_id else None
    from app.services.reporting.suggestions import suggest_for_finding as _suggest
    sug = _suggest(f, v, severity_override=severity)
    return {
        "finding_id": str(fid),
        "impact": sug["impact"],
        "recommendation": sug["recommendation"],
        "action_urgency": sug["action_urgency"],
        "category": (sug.get("category") if isinstance(sug, dict) else None),
    }


@router.post("/{rid}/suggest/bulk", response_model=SuggestResponse)
async def suggest_bulk(
    rid: uuid.UUID, body: SuggestRequest,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    """Bulk suggest endpoint. Two modes:

    1. `finding_ids` provided — compute suggestions for those specific
       findings.
    2. `category` provided — compute suggestions for every finding in
       the report's engagement and return only those whose detected
       category matches.

    In both modes, vulns are loaded in a single query and `suggest_for_finding`
    is called per finding. Findings outside the workspace are silently
    skipped. The response is a dict keyed by finding_id (string).
    """
    r = await db.get(Report, rid)
    if not r or r.workspace_id != current.workspace_id:
        raise HTTPException(404, "not found")
    if not can_triage(current.role):
        raise HTTPException(403, "analyst+ required")
    if not body.finding_ids and not body.category:
        raise HTTPException(400, "finding_ids or category required")

    from app.services.reporting.suggestions import suggest_for_finding as _suggest

    # Decide which findings to consider. If we have explicit finding_ids
    # we still scope to the workspace; if we have a category we need to
    # consider all findings in this report's engagement.
    target_ids: set[str] | None = None
    if body.finding_ids:
        target_ids = {str(fid) for fid in body.finding_ids}
        stmt = select(Finding).where(
            Finding.id.in_(list(target_ids)),
            Finding.workspace_id == current.workspace_id,
        )
    else:
        stmt = select(Finding).where(
            Finding.workspace_id == current.workspace_id,
            Finding.engagement_id == r.engagement_id,
        )
    findings = (await db.execute(stmt)).scalars().all()

    # Bulk-load all referenced vulns in one query.
    vuln_ids = {f.vulnerability_id for f in findings if f.vulnerability_id}
    vuln_map: dict[uuid.UUID, Vulnerability] = {}
    if vuln_ids:
        vstmt = select(Vulnerability).where(Vulnerability.id.in_(list(vuln_ids)))
        vuln_map = {v.id: v for v in (await db.execute(vstmt)).scalars().all()}

    out: dict[str, FindingSuggestion] = {}
    for f in findings:
        fid = str(f.id)
        if target_ids is not None and fid not in target_ids:
            continue
        v = vuln_map.get(f.vulnerability_id) if f.vulnerability_id else None
        sev_override = body.severity_overrides.get(fid)
        sug = _suggest(f, v, severity_override=sev_override)
        if body.category and sug.get("category") != body.category:
            continue
        out[fid] = FindingSuggestion(
            finding_id=f.id,
            impact=sug["impact"],
            recommendation=sug["recommendation"],
            action_urgency=sug["action_urgency"],
            category=sug["category"],
        )
    return SuggestResponse(suggestions=out)


@router.post("/{rid}/render", response_model=ReportOut)
async def render(
    rid: uuid.UUID, body: RenderRequest, request: Request,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    if not can_triage(current.role):
        raise HTTPException(403, "analyst+ required")
    r = await db.get(Report, rid, options=[selectinload(Report.versions)])
    if not r or r.workspace_id != current.workspace_id:
        raise HTTPException(404, "not found")
    if r.locked:
        raise HTTPException(409, "report is locked")
    if r.status not in (ReportStatus.DRAFTING, ReportStatus.PENDING_REVIEW,
                        ReportStatus.CHANGES_REQUESTED):
        raise HTTPException(409, f"cannot render in status {r.status.value}")

    ctx = await build_report_context(db, r.engagement_id)
    _apply_draft(ctx, r.draft_payload or {})
    draft = r.draft_payload or {}
    signed = {
        "workspace_id": str(r.workspace_id),
        "engagement_id": str(r.engagement_id),
        "report_id": str(r.id),
        "signer": current.user.email,
        "signed_at": None,  # populated at approve time
        "note": body.note,
        "version_no": len(r.versions) + 1,
    }
    docx = render_docx(
        ctx, signed=signed, exec_summary=draft.get("exec_summary"),
    )
    key = f"reports/{r.engagement_id}/{r.id}/v{len(r.versions)+1}.docx"
    sha, size = await storage.put_bytes(
        key, docx,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )

    last = max((v.version_no for v in r.versions), default=0)
    v = ReportVersion(
        report_id=r.id,
        version_no=last + 1,
        status=ReportStatus.PENDING_REVIEW,
        author_id=current.user.id,
        note=body.note,
        s3_key=key, sha256=sha, size=size,
        draft_payload=ctx,
    )
    db.add(v)
    r.status = ReportStatus.PENDING_REVIEW
    await db.flush()
    db.add(AuditLog(
        workspace_id=r.workspace_id, actor_id=current.user.id, actor_role=current.role,
        action="report.render", target_type="report", target_id=r.id,
        extra={"version": v.version_no, "sha": sha},
        ip=request.client.host if request.client else None,
    ))
    return await _to_out(r)


@router.post("/{rid}/approve", response_model=ReportOut)
async def approve(
    rid: uuid.UUID, body: ReportApproveRequest, request: Request,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    """HUMAN-ONLY approval gate. Role-gated to senior_analyst+."""
    if not can_approve_report(current.role):
        raise HTTPException(403, "approval requires senior_analyst+")
    r = await db.get(Report, rid, options=[selectinload(Report.versions)])
    if not r or r.workspace_id != current.workspace_id:
        raise HTTPException(404, "not found")
    if r.locked:
        raise HTTPException(409, "already locked")
    if r.status not in (ReportStatus.PENDING_REVIEW,):
        raise HTTPException(409, f"cannot approve in status {r.status.value}")
    target_v = None
    if body.version_id:
        target_v = await db.get(ReportVersion, body.version_id)
    elif r.versions:
        target_v = max(r.versions, key=lambda v: v.version_no)
    if not target_v:
        raise HTTPException(409, "no version to approve")
    if target_v.status != ReportStatus.PENDING_REVIEW:
        raise HTTPException(409, f"version not pending review ({target_v.status.value})")

    # Pre-approval invariants:
    # 1) Engagement is still in a state that permits a report
    e = await db.get(Engagement, r.engagement_id)
    if e and e.status.value == "cancelled":
        raise HTTPException(409, "engagement cancelled")

    r.status = ReportStatus.APPROVED
    target_v.status = ReportStatus.APPROVED
    r.signed_sha256 = target_v.sha256
    r.signed_at = datetime.now(timezone.utc)
    r.signed_by = current.user.id
    r.locked = True
    r.locked_at = datetime.now(timezone.utc)
    r.current_version_id = target_v.id

    # Re-render the docx with the final signature embedded so the
    # file itself is verifiable on its own.
    from app.services.reporting.render import render_docx
    ctx = target_v.draft_payload or {}
    signed = {
        "workspace_id": str(r.workspace_id),
        "engagement_id": str(r.engagement_id),
        "report_id": str(r.id),
        "version_id": str(target_v.id),
        "version_no": target_v.version_no,
        "signer": current.user.email,
        "signed_at": r.signed_at.isoformat(),
        "sha256": r.signed_sha256,
        "note": body.note,
    }
    final = render_docx(ctx, signed=signed)
    from app.services import storage
    key = f"reports/{r.engagement_id}/{r.id}/v{target_v.version_no}-signed.docx"
    sha, size = await storage.put_bytes(
        key, final,
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    )
    target_v.s3_key = key
    target_v.sha256 = sha
    target_v.size = size
    db.add(AuditLog(
        workspace_id=r.workspace_id, actor_id=current.user.id, actor_role=current.role,
        action="report.approve", target_type="report", target_id=r.id,
        extra={"version": target_v.version_no, "sha": target_v.sha256},
        ip=request.client.host if request.client else None,
    ))
    return await _to_out(r)


@router.post("/{rid}/request-changes", response_model=ReportOut)
async def request_changes(
    rid: uuid.UUID, body: ReportApproveRequest, request: Request,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    if not can_approve_report(current.role):
        raise HTTPException(403, "approval role required")
    r = await db.get(Report, rid, options=[selectinload(Report.versions)])
    if not r or r.workspace_id != current.workspace_id:
        raise HTTPException(404, "not found")
    if r.locked:
        raise HTTPException(409, "locked")
    r.status = ReportStatus.CHANGES_REQUESTED
    db.add(AuditLog(
        workspace_id=r.workspace_id, actor_id=current.user.id, actor_role=current.role,
        action="report.changes_requested", target_type="report", target_id=r.id,
        extra={"note": body.note},
        ip=request.client.host if request.client else None,
    ))
    return await _to_out(r)


@router.get("/{rid}/download")
async def download(
    rid: uuid.UUID,
    db: Annotated[AsyncSession, Depends(get_session)],
    current: Annotated[CurrentUser, Depends(get_current_user)],
):
    """Only allowed for approved/published reports."""
    r = await db.get(Report, rid, options=[selectinload(Report.versions)])
    if not r or r.workspace_id != current.workspace_id:
        raise HTTPException(404, "not found")
    if r.status not in (ReportStatus.APPROVED, ReportStatus.PUBLISHED):
        raise HTTPException(403, "report not approved yet")
    v = next((x for x in r.versions if x.id == r.current_version_id), None) \
        or max(r.versions, key=lambda x: x.version_no) if r.versions else None
    if not v or not v.s3_key:
        raise HTTPException(404, "no rendered version")
    data = await storage.get_bytes(v.s3_key)
    return StreamingResponse(
        iter([data]),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f'attachment; filename="{r.title}.docx"',
            "X-VAPT-SHA256": r.signed_sha256 or "",
        },
    )
