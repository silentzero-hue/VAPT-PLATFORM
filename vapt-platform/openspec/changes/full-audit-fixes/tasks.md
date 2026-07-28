# Tasks: full-audit-fixes

## Phase 1 — Security criticals (auth)

- [ ] 1.1 Rotate `JWT_SECRET` in `.env`; add root `.gitignore` excluding `.env`, `.env.*`, `*.local`; add `python-dotenv` to backend dev deps; re-encrypt stored creds on first boot
- [ ] 1.2 HMAC-sign the login challenge cookie (`app/api/v1/auth.py:148-165` set, `:194-201` read); verify signature on read
- [ ] 1.3 Add per-endpoint rate limits: `/auth/login` 10/min, `/auth/login/totp` 5/min, `/auth/refresh` 60/min, `/auth/logout` 30/min
- [ ] 1.4 Add per-account TOTP failure counter + lockout (parallel to `failed_login_count`)
- [ ] 1.5 Encrypt TOTP secret at rest (Fernet with `DATA_ENCRYPTION_KEY`); hash backup codes (Argon2); bump entropy to `token_urlsafe(10)` (10 codes per user)
- [ ] 1.6 Webhook URL validation: reject private/loopback/link-local IPs; disable `follow_redirects` on `httpx.AsyncClient`
- [ ] 1.7 Make `user_requires_totp` actually check `WorkspaceMembership.role` (analyst, senior_analyst, admin, platform_admin)
- [ ] 1.8 Family-revoke all `UserSession` on refresh-token hash mismatch
- [ ] 1.9 Drop `is_platform_admin` from `UserCreate`; keep only on internal admin path
- [ ] 1.10 Sanitize JWT decode errors and lockout messages (no internal state leak)
- [ ] 1.11 Pin `jwt_algorithm` to `Literal["HS256", "RS256"]` (reject `"none"`)
- [ ] 1.12 Remove `role` from JWT payload (derive server-side from membership)

## Phase 2 — Cross-workspace RBAC

- [ ] 2.1 Add `require_workspace` dependency in `app/api/deps.py`; refactor all routers
- [ ] 2.2 Fix `engagements.py` — `current.workspace_id != wid` check (drop `current.role in ADMIN_ROLES` exception)
- [ ] 2.3 Fix `workspaces.py` — same pattern in `add_member`, `update_member`, `remove_member`, `update_workspace`
- [ ] 2.4 Fix `comments.py:107` — `c.workspace_id == current.workspace_id` check for admins too
- [ ] 2.5 Fix `comments.py:62-76` — workspace check on `create_comment`
- [ ] 2.6 Fix `retests.py` — workspace check on `create`, `attach`, `summarise`
- [ ] 2.7 Fix `evidence.py:57-73` — workspace check on `get_evidence`
- [ ] 2.8 Fix `webhooks.py:81-92` — workspace check on `delete_wh`
- [ ] 2.9 Fix `webhooks.py:94-107` — scope `deliver_due` to test endpoint only
- [ ] 2.10 Fix `threat_intel.py:38-43` — scope findings to `wid`
- [ ] 2.11 Fix `findings.py:225-228` — return list of skipped IDs
- [ ] 2.12 Path-validate `db_path` in `multiscan.legacy_*` (allowlist `/var/lib/legacy-...`)
- [ ] 2.13 Fix `multiscan.py:39-50` — `compare_two` workspace check
- [ ] 2.14 Add file size cap to all `UploadFile` handlers (ingestion, evidence, sbom)
- [ ] 2.15 Add SSRF guard to `webhooks._post`

## Phase 3 — Data integrity

- [ ] 3.1 Wire real embeddings into `dedup.engine.find_or_create` (replace `fake_embedding` with `embeddings.service.embed_text`)
- [ ] 3.2 Fix reconciler key separator in `ingestion/service.py:296-331` (use `\x1f` not `|`)
- [ ] 3.3 Add agent-run reaper in `services/agent/runtime.py` (else-branch done event + cron)
- [ ] 3.4 Atomic portal view-count update in `services/portal.py:78-113`
- [ ] 3.5 Cache KEV catalog in `services/threat_intel/service.py` (module-level, 6h TTL)
- [ ] 3.6 Add `selectinload` to `findings.list_findings`, `vulnerabilities.list_vulns`, `_to_out` helpers
- [ ] 3.7 Fix dedup CVE case-sensitivity (`cve_id.upper()`)
- [ ] 3.8 Fix `legacy_db.import_legacy` (`app/services/legacy_db.py:103-119` 3 crashes)
- [ ] 3.9 Fix `_mark_remediated` (`ingestion/service.py:310-317`) — filter by worst status
- [ ] 3.10 Lock ingestion engagement via `SELECT ... FOR UPDATE` or row-lock
- [ ] 3.11 Add re-open / regress audit log entries on `_mark_remediated`
- [ ] 3.12 Fix Nessus `port=0` to `None` (or keep as 0 for "general")
- [ ] 3.13 Fix testssl port hard-coding
- [ ] 3.14 Fix `evidence.store.upload` S3-before-DB race (use INSERT ... ON CONFLICT)

## Phase 4 — Models & Schemas

- [ ] 4.1 Rename `NessusScanCache.created_at` → `scan_created_at`; add `created_at_meta` to model
- [ ] 4.2 Add `ForeignKey("report_versions.id", ondelete="SET NULL")` on `Report.current_version_id`
- [ ] 4.3 Use `JSONB` for `Workspace.settings` / `default_sla_days`
- [ ] 4.4 Add partial unique index for `port IS NOT NULL` on findings & assets
- [ ] 4.5 Drop redundant `index=True` where `unique=True` already creates the index
- [ ] 4.6 Add missing Pydantic schemas: `CommentOut`, `WebhookOut`, `ShareOut`, `ThreatIntelOut`, `TokenOut`, `AgentRunOut`
- [ ] 4.7 Convert free-form `setattr` writes to `Literal`/`Enum` (engagement status, finding status, asset criticality, role)
- [ ] 4.8 Add `lazy="selectin"` on relationships (avoid MissingGreenlet)
- [ ] 4.9 Make `WorkspaceMembership.role` use `Role` enum (not `String(40)`)
- [ ] 4.10 Add DB CHECK constraints: `port 0..65535`, `cvss_score 0..10`, `end_date >= start_date`
- [ ] 4.11 Add missing indexes on FKs: `LdapUserMapping.workspace_id`, `IngestionJob.submitted_by`, `RetestCycle.workspace_id`, etc.
- [ ] 4.12 Add `WorkspaceOut.settings` and `updated_at` fields
- [ ] 4.13 Add `VulnerabilityOut.fingerprint_hash`, `remediation_template`, `workspace_id`
- [ ] 4.14 Add `ReportOut.workspace_id`, `locked_at`, `template_id`
- [ ] 4.15 Add `EngagementOut.extra`, `ingestion_locked_at`
- [ ] 4.16 Standardize `__future__ import annotations` + add migration 0006 for all renames

## Phase 5 — Build & test hygiene

- [ ] 5.1 Add `frontend/eslint.config.js` (flat config)
- [ ] 5.2 Add `backend/tests/conftest.py` env loader (`load_dotenv("../.env")`)
- [ ] 5.3 Rename `app/services/ingestion/nessus.py` → `nessus_parser.py`
- [ ] 5.4 Add `SettingsConfigDict(env_file="../.env")` to `pydantic_settings.BaseSettings`
- [ ] 5.5 Fix 73 mypy errors in 37 files
- [ ] 5.6 Fix 113 ruff errors (`ruff check --fix` for 98 auto-fixable; manual for 15)
- [ ] 5.7 Add `vitest.config.ts` + 1 smoke test
- [ ] 5.8 Delete `StatusBar.tsx` and `SEVERITY_BG` export (or use them)
- [ ] 5.9 Enable `noUnusedLocals` / `noUnusedParameters` in `tsconfig.json`
- [ ] 5.10 Add `[tool.ruff]` and `[tool.mypy]` to `pyproject.toml`
- [ ] 5.11 Install missing type stubs (`types-defusedxml`, `types-python-jose`, etc.)
- [ ] 5.12 Pin `python-jose>=3.4.0` or migrate to `pyjwt[crypto]`

## Phase 6 — Frontend critical bugs

- [ ] 6.1 Fix `SettingsPage.tsx:21` — capture real `challenge_token` from TOTP enroll response
- [ ] 6.2 Fix `useAuth.refreshMe` — preserve user-selected workspace
- [ ] 6.3 Fix `DashboardPage` N+1 (use `summary` endpoint or paginate)
- [ ] 6.4 Fix `VulnerabilityDetailPage` — guard against empty AI draft wipe
- [ ] 6.5 Fix `EngagementDetailPage` cache key on upload
- [ ] 6.6 Add `onError` to all mutations (15+ missing)
- [ ] 6.7 Add `wid`-required guard component
- [ ] 6.8 Debounce search inputs (`useDeferredValue`)
- [ ] 6.9 Replace `window.prompt` in `ReportsPage` with proper select
- [ ] 6.10 Fix TOTP verify endpoint
- [ ] 6.11 Add `ai_draft_reviewed_at` to backend `VulnerabilityOut` (or remove from frontend type)
- [ ] 6.12 Fix WebSocket race in `AgentLivePage`
- [ ] 6.13 Convert `any[]` casts to typed responses
- [ ] 6.14 Move all `interface X {}` from pages to `types/index.ts`
- [ ] 6.15 Fix `FindingsPage` debounce on `q` search
- [ ] 6.16 Fix `EngagementDetailPage` lock toggle staleness
- [ ] 6.17 Fix all `?limit=N` silent truncation (add summary endpoints)

## Phase 7 — Frontend quality

- [ ] 7.1 Add aria-labels to all interactive elements
- [ ] 7.2 Add keyboard handlers to `Card` (`onKeyDown` Enter/Space)
- [ ] 7.3 Add focus traps to modals
- [ ] 7.4 Add CSP header to backend responses
- [ ] 7.5 Memoize expensive computations in DashboardPage
- [ ] 7.6 Stable IDs in keys (no array index)
- [ ] 7.7 Toast on every mutation success
- [ ] 7.8 URL-driven view state (grid/table, tab)
- [ ] 7.9 Standardize on `useAuth.activeWorkspace` everywhere (drop `wid ?? auth.activeWorkspace` duplication)
- [ ] 7.10 Convert `STATUS_LABEL` / `STATUS_PILL` maps to a single `REPORT_STATUS` registry
- [ ] 7.11 Add error boundaries per page
- [ ] 7.12 Add loading skeletons (not just "Loading…")

## Verification after each phase

```bash
cd vapt-platform

# Backend
docker compose -p vapt-platform restart backend
cd backend && ruff check app/ && mypy app/ && pytest -x  # all green

# Frontend
cd ../frontend
npx tsc --noEmit
npx eslint .
npx vitest run

# E2E
# Login → upload .nessus → check findings → check reports → check agent
```
