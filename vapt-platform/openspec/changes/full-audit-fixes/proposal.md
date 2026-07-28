## Why

The VAPT platform has reached a feature-complete state with 25+ API endpoints, 19+ parsers, AI-driven MCP agent, and a polished UI. A comprehensive audit (6 parallel agents, ~825 distinct findings) revealed that production deployment is blocked by:

- **8 critical security issues** (committed JWT secret, SSRF, plaintext TOTP, missing rate limits, cross-tenant privilege escalation patterns)
- **~50 cross-workspace RBAC bugs** (admin-of-any-workspace pattern repeated across 8+ files)
- **Broken dedup** (fake_embedding is hash-based, never matches semantically)
- **Build/lint/test entirely broken** (no eslint config, 73 mypy errors, pytest can't load settings)
- **TOTP enrollment completely broken in UI** (`challenge_token: "x"`)

This change implements the top-priority fixes in 7 phases.

## What Changes

### Phase 1 — Security criticals (auth)
- Rotate `JWT_SECRET`; add root `.gitignore` (block .env from git); remove committed secrets
- HMAC-sign the post-password challenge cookie (`user_id:role:wid:challenge`)
- Add per-endpoint rate limits: `/auth/login` 10/min, `/auth/login/totp` 5/min, `/auth/refresh` 60/min
- Webhook URL validation: reject private/loopback/link-local IPs, disable redirects
- Encrypt TOTP secrets at rest (column-level); hash backup codes (Argon2); bump entropy to `token_urlsafe(10)`
- Make `user_requires_totp` actually check membership role (currently only `is_platform_admin`)
- Family-revoke all sessions on refresh-token hash mismatch (RFC 6819 §5.2.2.3)

### Phase 2 — Cross-workspace RBAC
- Centralize workspace-scope check into `require_workspace` dependency
- Fix admin-of-any-workspace pattern in: `engagements`, `workspaces`, `comments`, `retests`, `evidence`, `webhooks`, `threat_intel`, `findings`
- Path-validate `db_path` in `multiscan.legacy_*` (allowlist `/var/lib/legacy-...` only)
- Add workspace check to `evidence.get_evidence` (currently unauthenticated cross-tenant read)
- Scope `webhooks.test_wh.deliver_due` to the test endpoint only (no cross-tenant side effect)

### Phase 3 — Data integrity
- Wire real embeddings into `dedup.engine.find_or_create` (replace `fake_embedding`)
- Fix reconciler key separator (`|` → `\x1f`) to avoid URL/IPv6 collisions
- Add agent-run reaper (sweep runs with `started_at < now-30min` and `status='running'`)
- Atomic portal view-count UPDATE with `WHERE current_views < max_views`
- Cache KEV catalog in module memory with 6h TTL
- `N+1` elimination: `selectinload` on `Finding→Vulnerability/Asset/Evidence`, `Vulnerability→Findings`, `Engagement→Findings`

### Phase 4 — Models & Schemas
- Rename `NessusScanCache.created_at` → `scan_created_at`; add `created_at_meta` to model
- Add `ForeignKey("report_versions.id", ondelete="SET NULL")` on `Report.current_version_id`
- Use `JSONB` (not generic `JSON`) for `Workspace.settings` / `default_sla_days`
- Add `partial unique index` for `port IS NOT NULL` on `findings` and `assets`
- Drop redundant `index=True` where `unique=True` already creates the index
- Add missing Pydantic schemas: `CommentOut`, `WebhookOut`, `ShareOut`, `ThreatIntelOut`, `TokenOut`, `AgentRunOut`
- Convert free-form `setattr` writes to `Literal`/`Enum` (engagement status, finding status, asset criticality, role, etc.)
- Drop `is_platform_admin` from `UserCreate` (no public elevation path)

### Phase 5 — Build & test hygiene
- Add `frontend/eslint.config.js` (flat config)
- Add `backend/tests/conftest.py` env loader (`load_dotenv("../.env")`)
- Rename `app/services/ingestion/nessus.py` → `nessus_parser.py` (mypy collision)
- Add `pydantic_settings` `.env` loader to backend (`SettingsConfigDict(env_file="../.env")`)
- Fix 73 mypy errors in 37 files
- Fix 113 ruff errors (98 auto-fixable with `ruff check --fix`)
- Add `vitest.config.ts` + 1 smoke test (or remove `test` script)

### Phase 6 — Frontend critical
- Fix `SettingsPage.tsx:21` — capture real `challenge_token` from TOTP enroll response
- Fix `useAuth.refreshMe` — don't overwrite user-selected workspace
- Fix `DashboardPage` N+1 + silent truncation (use `summary` endpoint or paginate)
- Fix `VulnerabilityDetailPage` — guard against empty-string AI draft wipes
- Fix `EngagementDetailPage` cache key on upload (`["engagements", wid]`)
- Add `onError` to every mutation (currently 15+ missing)
- Add `wid`-required guard component (eliminates `/workspaces/undefined/...` URLs)
- Add `?limit` pagination to all list endpoints

### Phase 7 — Frontend quality
- Move all `interface X {}` from pages to `types/index.ts`
- Debounce search inputs (`useDeferredValue`)
- Convert `any[]` casts to typed responses
- Accessibility: aria-labels, keyboard nav, focus traps
- Replace `window.prompt` in `ReportsPage` with proper select
- Add CSP header to backend responses

### Out of scope (deferred to follow-up changes)
- Performance tuning beyond N+1
- Full test coverage
- Migration to `pyjwt` from `python-jose`
- Full UI redesign / refactor
- Caching layer (Redis) for embeddings
- WebSocket reconnection logic hardening
- Pagination on every list endpoint (only the most-trafficked)

## Capabilities

### New Capabilities
- `security-audit-fixes` — auth hardening, RBAC centralization, SSRF guards, secret encryption
- `data-integrity-fixes` — dedup engine, reconciler, agent reaper, portal atomicity, N+1 elimination
- `model-schema-fixes` — NessusScanCache rename, FK additions, JSONB, partial unique indexes, missing schemas
- `build-hygiene` — eslint config, conftest env loader, mypy/ruff fixes, vitest setup
- `frontend-critical-bugs` — TOTP enrollment, workspace reset, dashboard N+1, AI draft guard, cache keys
- `frontend-quality` — type tightening, debouncing, accessibility, prompt replacement

### Modified Capabilities
- (none — no spec-level requirements change in this fix pass; behavior is already documented in the existing openapi schema)

## Impact

### Code
- **Backend** (`backend/app/`): auth (1 file), all 8 affected routers (8 files), `dedup/engine.py`, `services/ingestion/service.py`, `services/threat_intel/service.py`, `services/agent/runtime.py`, `services/portal.py`, all 22 models, all 10 schemas
- **Frontend** (`frontend/src/`): `useAuth.tsx`, `App.tsx`, `AppShell.tsx`, all 22 pages, `types/index.ts`, `lib/api.ts`
- **Build**: `frontend/eslint.config.js` (new), `frontend/vitest.config.ts` (new), `backend/tests/conftest.py`, `backend/pyproject.toml`

### APIs
- `/auth/login` — response unchanged
- `/auth/login/totp` — response unchanged
- `/auth/me/totp/verify` — same endpoint, now functional
- All list endpoints — pagination added (backward compatible)
- All endpoints — proper 403 for cross-tenant access (was 200 in some cases)

### Data
- DB migrations: add `JSONB` to `Workspace.settings` (no-op, already JSONB), partial unique index on findings
- `UserCreate.is_platform_admin` field removed (no data loss, but platform admins must be created via direct DB or CLI)
- Existing TOTP secrets will need to be re-entered (encryption key is new)

### Security
- New `DATA_ENCRYPTION_KEY` env var (32 random bytes) — separate from `JWT_SECRET`
- `JWT_SECRET` rotation required (existing tokens invalidated)
- Refresh tokens now family-revoke on theft detection (forces re-login on suspicious activity)
- TOTP secrets now encrypted at rest; backup codes hashed

### Dependencies
- Add: `python-dotenv` to backend dev deps
- Add: `pip-audit` to CI
- Pin: `python-jose` to `>=3.4.0` (or migrate to `pyjwt[crypto]`)
