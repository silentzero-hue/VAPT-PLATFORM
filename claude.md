# VAPT Platform — Project Memory

## What this is

A self-hosted **Vulnerability Assessment & Penetration Testing** platform. The product is
the rendered output: a **Technovage DMC VAPT report** generated from a scan, with
client-side WYSIWYG editing and a docx upload-edit cycle.

Source of truth for the report visual style: `/Users/phanha/Downloads/NESUS/_Internal_VAPT_DMC_Final-Report-EN_Q4.docx`
(treat as read-only). Every report must look like a senior consultant manually
edited that template.

## Repo layout

```
/Users/phanha/Documents/WORKSPACE/VAPT-SYS/
├── .gitignore                 (top-level; vapt-platform/ has its own)
├── vapt-platform/
│   ├── backend/               FastAPI + SQLAlchemy 2.0 async + PGVector + LibreOffice
│   ├── frontend/              React 18 + Vite + Tailwind + TanStack Query
│   ├── docker-compose.yml     full stack: postgres, redis, minio, backend, embedder, mcp,
│   │                          worker, frontend
│   ├── openspec/              spec-driven change tracking (proposal, design, specs, tasks)
│   └── .env.example           template for secrets
```

## Stack

| Layer       | Tech                                                            |
|-------------|-----------------------------------------------------------------|
| API         | FastAPI, Pydantic 2, slowapi rate limiting                      |
| DB          | PostgreSQL 16 + pgvector, async SQLAlchemy 2.0, Alembic          |
| Cache       | Redis 7                                                         |
| Storage     | MinIO (S3-compatible); evidence blobs + rendered report docx     |
| Auth        | Argon2id, TOTP (pyotp), JWT 15 min + refresh 7d                  |
| Frontend    | React 18, Vite, TanStack Query, Tailwind, lucide-react, sonner     |
| Report DOCX | python-docx + docxtpl against DMC Technovage template             |
| PDF preview | LibreOffice headless (in backend image) → PDF                    |
| HTML preview| mammoth (docx→html) + base64-embedded images                   |
| Embeddings  | Custom sentence-transformer wrapper for vuln dedup               |
| Background  | arq (Redis) for webhook delivery, threat-intel refresh, etc.     |
| LLM agent   | MCP server in `backend/app/mcp_server/` (separate container)    |
| CI          | GitHub Actions (`.github/workflows/ci.yml`)                      |

## Admin login (after fresh bootstrap)

- **Email:** `admin@vapt.example.com`
- **Password:** `VaptAdmin2026`
- **TOTP secret:** stored in DB encrypted with `DATA_ENCRYPTION_KEY` (Fernet).
  If you need to re-enroll, run in backend container:
  ```python
  from app.core.db import SessionLocal
  from app.core.secrets import encrypt_str, new_backup_code, set_backup_codes
  from app.core.security import generate_totp_secret
  from app.models.user import User
  from sqlalchemy import select
  import asyncio
  async def go():
      async with SessionLocal() as db:
          u = (await db.execute(select(User).where(User.email=='admin@vapt.example.com'))).scalar_one()
          secret = generate_totp_secret()
          u.totp_secret = encrypt_str(secret)
          u.totp_enabled = True
          u.totp_failed_count = 0
          u.totp_locked_until = None
          u.failed_login_count = 0
          u.locked_until = None
          set_backup_codes(u, [new_backup_code() for _ in range(10)])
          await db.commit()
          print('TOTP secret:', secret)
  asyncio.run(go())
  ```

## Run the stack

```bash
cd /Users/phanha/Documents/WORKSPACE/VAPT-SYS/vapt-platform
docker compose up -d
# Backend health:
curl http://localhost:8000/api/v1/health
# Frontend:
open http://localhost:5173
```

**Useful aliases** (set in your shell rc):
```bash
alias vapt-logs='cd ~/Documents/WORKSPACE/VAPT-SYS/vapt-platform && docker compose logs -f --tail=50'
alias vapt-backend='cd ~/Documents/WORKSPACE/VAPT-SYS/vapt-platform && docker compose exec backend bash'
alias vapt-psql='docker compose -p vapt-platform exec postgres psql -U vapt -d vapt'
alias vapt-rebuild='cd ~/Documents/WORKSPACE/VAPT-SYS/vapt-platform && docker compose build backend && docker compose up -d backend'
```

## Report rendering — the heart of the project

Files to know cold:
- `backend/app/services/reporting/render.py` (~1600 lines, the big one)
- `backend/app/services/reporting/suggestions.py` (per-category text templates)
- `backend/app/services/reporting/templates/dmc_vapt_report.docx` (BUNDLED; **never** modify the template — only `report_template_path` config can point elsewhere)
- `backend/app/api/v1/reports.py` (HTTP routes)
- `frontend/src/pages/reports/ReportEditPage.tsx` (the editor with PDF/HTML/Edit modes)

### Hard rules when working on the renderer

1. **Never recreate the template's tables / headings / cover page.** Only mutate
   cell text. `_clear_data_rows(table)` removes data rows but preserves the table's
   `tcPr` (borders, shading, widths) and the header row.
2. **Always re-build the backend image** after editing `render.py` so the
   embedded `__pycache__/render.cpython-312.pyc` doesn't shadow your source.
   `docker compose build backend && docker compose up -d backend` is the safe path.
   If you only restart, the `.pyc` may not be invalidated.
3. **TOTP secret encryption:** `User.totp_secret` holds a Fernet ciphertext, not
   raw base32. Decrypt with `app.core.secrets.get_totp_secret(user)`. Backups
   codes are Argon2id hashes, not plaintext.
4. **`UserCreate.is_platform_admin` was removed** from the public schema to
   prevent privilege escalation. Elevation goes through a separate internal path.
5. **The "MUST NOT REBUILD" rule** in the project root prompt is the dominant
   constraint for the renderer. When in doubt, mutate the existing template
   cells, don't add new structures.

### How `render_docx` flows

```
render_docx(ctx, signed=None, exec_summary=None)
├── _resolve_template_path()       (env > bundled > empty)
├── if no template:
│   └── _render_from_scratch()     (FALLBACK ONLY — never the primary path)
├── doc = Document(template_path)
├── _replace_template_literals(doc, ctx)   (Data Management Center, dates, etc.)
├── _fill_title_page(doc, ctx)             (cover page right cell)
├── _fill_scope_table(doc, ctx)            (assets)
├── _fill_summary_table(doc, ctx)          (per-host severity counts)
├── _inject_exec_summary(doc, ctx)         (analyst narrative)
├── _rebuild_detailed_findings(doc, ctx)    (clears rows, fills with merged findings)
└── _add_signature_footer_and_xml(doc, signed)
    (only if signed is provided — never in the preview)
```

### Finding merger (`_merge_similar_findings`)

Findings with the same software key (e.g. all "OpenSSH <X.Y>") are merged into
ONE row with combined CVEs. The key is computed by `_software_key(title)`:
- "OpenSSH < 7.8" → "openssh"
- "Apache ActiveMQ RCE (CVE-2023-46604)" → "apache activemq rce"
- "RHEL 8 : bzip2 (RHSA-2025:0733)" → "rhel 8"

If a finding has no extractable key, it gets a unique placeholder and is
preserved as-is.

### Scanner-output cleaning (`_clean_scanner_output`)

Strips from the rendered docx:
- `[/description]`, `[/synopsis]`, `[/plugin_output]`, `[/solution]`, `[/see_also]`, `[/risk_factor]`, `[/cvss_base_vector]`, `[/cvss3_base_vector]`
- `Plugin - <digits>` lines
- `Plugin ID: <digits>` lines (the `Tenable Plugin ID:` form is preserved)

Keeps:
- `CVE-YYYY-NNNN`
- `Tenable Plugin ID:`, `Tenable Reference:`
- `CWE:`

## Auth / RBAC (security-critical)

- Roles (in `app/models/user.py`): `platform_admin`, `admin`, `senior_analyst`, `analyst`, `viewer`
- The user object has `is_platform_admin` (boolean) AND a `WorkspaceMembership` per workspace
- **Centralized workspace check** lives in `_check_workspace_scope(current, wid)` in
  each router. **Never** use the broken `current.role in ADMIN_ROLES` shortcut
  for cross-workspace access — it lets any admin of any workspace mutate
  others. This was a P0 audit finding and is now fixed across 8 files.
- `current.workspace_id` for `platform_admin` is `None` — they have a
  pass-through in `_check_workspace_scope`. `platform_admin` also doesn't appear
  in `WorkspaceMembership` rows.
- `secret` derivation: `DATA_ENCRYPTION_KEY` is the Fernet key for `User.totp_secret`
  and `LdapConfig.bind_password_ciphertext` and `NessusServer.access_key_ciphertext`.
  It is **independent** of `JWT_SECRET` (so rotating JWT doesn't lose secrets).
- Login flow: `POST /auth/login` → 200 (sets `vapt_totp_challenge` cookie)
  → `POST /auth/login/totp` → 200 (sets `vapt_access` and `vapt_refresh` cookies)
  → 401 with no challenge cookie means the login expired.
- Login has per-account TOTP lockout (`totp_failed_count`, `totp_locked_until`)
  in addition to the password lockout.

## Database

Postgres connection from the host (not from inside Docker):
```bash
PGPASSWORD=changeme_postgres_pw psql -h 127.0.0.1 -p 5433 -U vapt -d vapt
```

From inside the backend container:
```bash
docker compose -p vapt-platform exec postgres psql -U vapt -d vapt
```

### Schema highlights

- `workspaces.settings` is JSONB. Don't use the generic `JSON` SQL type.
- `reports.draft_payload` is JSONB (the per-report analyst edits, see migration 0007).
- `reports.current_version_id` has FK to `report_versions.id` with `ondelete=SET NULL`
  (so deleting a version doesn't break the report pointer).
- `findings.evidence_ref` is `Text` (was `VARCHAR(500)` — long plugin output overflowed).
- `UserSession.refresh_token_hash` is SHA-256, not plaintext.
- `WorkspaceMembership.role` is `String(40)` — change to the `Role` enum if
  you change role semantics. There is also a CHECK constraint on
  `users.failed_login_count >= 0`.
- Partial unique indexes on `findings` and `assets` (port-IS-NULL vs
  port-IS-NOT-NULL) so dedup works correctly with nullable ports.
- `users.totp_secret` and `users.backup_codes` (Argon2id hashes) replaced the
  plaintext storage (was an audit finding).

### Migrations

```bash
docker compose -p vapt-platform exec backend alembic upgrade head
# Current head: 0007 (report draft_payload)
```

## API conventions

- All routes are under `/api/v1`
- All authenticated routes expect a JWT in the `Authorization: Bearer <token>`
  header OR a `vapt_access` cookie
- Workspace-scoped routes use `/workspaces/{wid}/...`
- Engagement-scoped routes use `/engagements/{eid}/...` (look up workspace via FK)
- All non-GET routes return 4xx with a body like `{"detail": "..."}`
- Time format: ISO 8601 with timezone
- `null` vs missing: `null` means explicit null, missing field means not set
- IDs are UUIDs, returned as strings

## Frontend conventions

- `useAuth()` for current user + workspace (`auth.activeWorkspace`)
- `useQuery` / `useMutation` from TanStack Query; **never** store in `useState`
- API client: `import { api } from "../../lib/api"` (axios with withCredentials +
  auto-401-logout via the global 401 handler in `App.tsx`)
- Editor page (`ReportEditPage.tsx`) is the most complex; the 3-mode preview
  toggle (PDF / HTML / Edit) is the right way to present fidelity options
- All WYSIWYG attributes use `data-field="..."` so the editor can map DOM
  mutations back to the draft
- `data-finding-id="<uuid>"` on each editable finding cell
- `data-field="exec_summary"` on the analyst narrative block
- `data-field="title"` on the first h1

## OpenSpec change tracking

`/Users/phanha/Documents/WORKSPACE/VAPT-SYS/vapt-platform/openspec/changes/<name>/`
holds:
- `proposal.md` — why, what, capabilities
- `design.md` — implementation
- `specs/<capability>/spec.md` — requirements
- `tasks.md` — checklist

The `full-audit-fixes` change tracks the original 825-issue audit + fixes
in 7 phases. Use it as a template for new changes.

## What the user cares about most (in priority order)

1. **Report visual fidelity** — the rendered docx + PDF preview must look
   exactly like the original DMC Technovage template. Any regression here is
   a P0.
2. **No scanner output leaks** — no `[/description]`, no `Plugin - 12345`, no
   "Apply vendor patch per Nessus" boilerplate in the client-facing report.
3. **No duplicate findings** — OpenSSH variants, OpenSSL variants, etc. must
   be merged into one row.
4. **Professional language** — no "The remote host contains..." starters;
   every paragraph reads as consultant prose.
5. **Cover page must show Technovage logo, "For/Type/From/Date" labels, client
   name, and date** — all editable via the title-page right cell.
6. **WYSIWYG editor must work** — contenteditable in iframe, changes flow
   into the structured draft state.
7. **Docx upload-edit cycle** — the user can edit the rendered docx in Word
   and upload it back; the executive narrative is extracted.

## Known sharp edges (don't get bitten)

- **Backend `__pycache__` shadows source after rebuild.** After editing
  `render.py`, the running container's `.pyc` file may not be invalidated. Always
  rebuild the image AND restart: `docker compose build backend && docker compose
  up -d backend`. Quick-restart-only is a trap.
- **TOTP lockout** can leave a user unable to log in. Reset via SQL:
  `UPDATE users SET totp_failed_count=0, totp_locked_until=NULL WHERE email='...'`
  and re-enroll.
- **Lockout** (password) is separate. Same SQL with `failed_login_count` and
  `locked_until`.
- **PDF preview** uses LibreOffice headless; first call may take 1-2s while
  the daemon spins up. Subsequent calls are ~200ms.
- **CORS** is hardcoded to `["http://localhost:5173"]` in `app/core/config.py`.
  Add new origins there for new deployment targets.
- **The `WorkerSession` model** has the refresh token stored as SHA-256, not
  plaintext. Rotate the access token; refresh tokens are family-revoked on
  theft detection.
- **Mammoth** (docx→html) is on version 1.x. Don't pass your own `img_element`
  callback as the **second positional arg** to `mammoth.convert_to_html` —
  that slot is `transform_document`, not `convert_image`. Use the default
  `images.data_uri` and post-process the HTML if you need custom image
  handling.
- **CSS issue** for the preview iframe: the inline `<style>` block in
  mammoth output sometimes gets wrapped in a `<table>` element. Don't rely
  on `table:first-of-type` matching the cover page; the FIRST `<table>` in
  the document tree can be a comment table, not the real one.
- **X-Frame-Options** is `SAMEORIGIN` (not `DENY`) in `frontend/nginx.conf`
  because the preview modal embeds the PDF in an iframe. Changing back to
  `DENY` will silently break the modal preview.

## Stylistic conventions (code)

- Python: type hints everywhere, `async def` for endpoints, Pydantic v2 schemas.
- Linter: ruff. Run `docker compose exec backend ruff check app/`.
- Type checker: mypy (excluded via `ignore_missing_imports`).
- No `print()` in app code; use the structured logger.
- Frontend: no `any` unless unavoidable (ESLint rule warns).
- Frontend: prefer `useQuery` over `useEffect`+`fetch`.
- The `Modal` component (`frontend/src/components/ui/Modal.tsx`) is the
  preferred way to build modals; do not invent new ones.

## Tests

```bash
docker compose -p vapt-platform exec backend pytest tests/ -v
```

Known unrelated failures on `main`:
- `test_features.py::test_sbom_parse` — parser issue
- `test_auth.py`, `test_dedup.py` — DB connection issues (try `localhost:5432`
  instead of the docker-internal `postgres:5432`)

The 13 preview tests in `test_report_preview.py` should always pass.

## Where things live (file map)

- `backend/app/main.py` — app factory, middleware, lifespan, route mounting
- `backend/app/api/v1/*.py` — 20+ router files (one per resource)
- `backend/app/services/` — domain logic (auth, dedup, ingestion, reporting, etc.)
- `backend/app/models/` — SQLAlchemy ORM (22 files)
- `backend/app/schemas/` — Pydantic schemas
- `backend/app/core/` — config, security, db, secrets, limiter
- `backend/app/workers/` — background jobs (arq)
- `backend/app/mcp_server/` — MCP server for the agent
- `frontend/src/api/` — axios client + custom hooks
- `frontend/src/components/` — UI primitives (Modal, Card, Toolbar, …)
- `frontend/src/hooks/` — useAuth, etc.
- `frontend/src/lib/` — cn, api, formatters
- `frontend/src/pages/` — one folder per feature
- `frontend/src/types/` — shared TS types

## What NOT to do

- Don't recreate the DMC template from scratch — use the bundled one
- Don't add new dependencies without justification (`pyproject.toml` is
  intentional; run `pip-audit` to check new ones)
- Don't bypass the `_check_workspace_scope` helper anywhere
- Don't add inline `style="..."` to mammoth output (the inline `<style>`
  block is enough; debug with `!important` rules)
- Don't store `is_platform_admin` in `UserCreate` (was a P0 audit finding)
- Don't return `User` model directly from a route (use `UserOut` schema)
- Don't make the editor page render a different layout per report
  (the editor is the same; only the data varies)
- Don't introduce new top-level folders without updating this file
- Don't commit `.env`, `__pycache__`, `node_modules/`, `*.log`, or the
  `.playwright-mcp/` directory
