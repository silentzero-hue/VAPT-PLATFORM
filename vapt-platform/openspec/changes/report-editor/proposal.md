# Report editor (analyst-side)

## Why

Today, the only way to inject analyst edits into a VAPT report is to
edit `ai_draft_impact` / `ai_draft_recommendation` on the underlying
`Vulnerability` rows (which then pollutes every other engagement and
report that ever references that vulnerability). The render pipeline
has no concept of "this engagement's report says X" — the docx is
purely a function of the live `Finding` + `Vulnerability` state.

We need a per-report edit layer that a senior analyst can use BEFORE
rendering the docx, so that:

- The exec summary narrative is theirs, not the agent's
- The overall security rating can be overridden when the AI's choice
  is wrong (e.g. all the "critical" findings are actually false
  positives the analyst already triaged)
- Per-finding impact / recommendation can be overridden without
  touching the canonical `Vulnerability` row
- Analyst notes can be attached for the downstream reviewer

The edits are stored on the `Report` (so they survive across renders
and across changes-requested cycles) and merged into the auto-built
report context at render time.

## What changes

### Backend

- `app/models/report.py` → add `Report.draft_payload: JSONB` (default `{}`,
  nullable=False). The `ReportVersion.draft_payload` column already
  exists and is used for the per-version snapshot; this new column
  holds the *current editable* state of the report.
- `app/schemas/report.py` → new `FindingEdit`, `ReportEditRequest`;
  add `draft_payload: dict = Field(default_factory=dict)` to `ReportOut`.
- `app/api/v1/reports.py`
  - new `PATCH /reports/{rid}` — title, overall_rating, exec_summary,
    per-finding overrides. Role-gated to `APPROVE_ROLES`
    (senior_analyst+). 409 if `r.locked`.
  - extend `_to_out` to include `draft_payload`.
  - update `render` to merge `r.draft_payload` into the auto-built
    context before calling `render_docx`.
- `app/services/reporting/render.py`
  - new helper `_apply_draft(ctx, draft)` that:
    - sets `ctx["summary"]["overall_rating"]` from `draft.overall_rating`
    - overrides `impact` / `recommendation` on the matching finding
      rows (matched by `finding_id`) and on the matching
      `detailed_findings` group (matched by `vuln_id` + `port`)
    - injects `ctx["exec_summary"] = draft.exec_summary` so the
      renderer can drop it into the Executive Summary section
  - `render_docx` accepts `exec_summary: str | None` and inserts a
    new paragraph (or replaces the default summary text) in the
    Executive Summary section of the template; for the from-scratch
    fallback, a new paragraph is added under "1. Executive Summary".
- `alembic/versions/0007_report_draft.py` → add `draft_payload` column
  on `reports`, JSONB not-null with `default '{}'::jsonb`.

### Frontend

- `src/types/index.ts`
  - new `ReportDraft`, `FindingEdit`, `ReportEditRequest`
  - `Report.draft_payload: ReportDraft`
- `src/pages/reports/ReportEditPage.tsx` → new page at
  `/workspaces/:wid/reports/:rid/edit`. Sections:
  1. Title (editable input)
  2. Executive Summary (textarea + overall_rating select)
  3. Findings table (per-(vuln,port) row: severity override,
     impact, recommendation, analyst note)
  Sticky action bar: Save draft / Generate report / Discard.
- `src/App.tsx` → new route
  `/workspaces/:wid/reports/:rid/edit` → `<ReportEditPage />`
- `src/pages/reports/ReportDetailPage.tsx` → when status is
  `drafting` (or `pending_review` / `changes_requested`) and not
  locked, show an "Edit" button that navigates to the editor.

## Compatibility

- Existing render flow is unchanged when `draft_payload` is empty.
  `_apply_draft` is a no-op on an empty draft.
- Approval flow is unchanged: it already re-renders from
  `target_v.draft_payload` (the per-version snapshot). On approval,
  the approval path will copy the *current* `r.draft_payload` into
  the version's `draft_payload` so the approved version reflects the
  latest edits. (See "Migration of existing render" below.)
- The existing `RenderRequest.overrides` field is left in place for
  backward compatibility; it is not used by the new editor.

### Migration of existing render

Today, `render` does:
```
ctx = await build_report_context(...)
docx = render_docx(ctx, ...)
v = ReportVersion(..., draft_payload=ctx)
```

After this change:
```
ctx = await build_report_context(...)
_apply_draft(ctx, r.draft_payload or {})
docx = render_docx(ctx, exec_summary=(r.draft_payload or {}).get("exec_summary"))
v = ReportVersion(..., draft_payload=ctx)
```

The version's `draft_payload` still holds the *rendered* context (the
merged view), so approval re-rendering is unchanged.

## Validation

- `find backend -name "*.py" -exec python3 -m py_compile {} \;` passes.
- `alembic upgrade head` succeeds inside the backend container.
- `tsc --noEmit` on the frontend is clean.
- Manual: log in as senior_analyst, open a draft report, click Edit,
  change exec_summary + one finding's impact, Save draft, Generate
  report, download the docx and confirm the edits appear in the
  Executive Summary and Detailed Findings sections.
- Manual: PATCH on a locked report returns 409.
- Manual: PATCH as an `analyst` (not senior) returns 403.
