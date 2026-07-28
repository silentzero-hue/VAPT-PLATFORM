# VAPT Platform

Production-ready, self-hosted **V**ulnerability **A**ssessment & **P**enetration **T**esting management platform.

Built to the spec in [`vapt-build-superprompt.md`](../vapt-build-superprompt.md):
vulnerability-centric dedup, MCP-driven AI report drafting, human-approval gate, traditional email+password+TOTP auth, full multi-tenant isolation, and Docker Compose deployment.

---

## Architecture

```
       ┌──────────────────────┐        ┌──────────────────────┐
       │   React + Vite +     │  HTTP  │   FastAPI backend    │
       │   shadcn-style UI    │ ◀────▶ │   (REST + ASGI)      │
       └──────────┬───────────┘        └────────┬─────────────┘
                  │                             │
                  │                             │ MCP (HTTP)
                  │                             ▼
                  │                    ┌──────────────────────┐
                  │                    │   MCP server         │
                  │                    │   (8 tools, audited) │
                  │                    └──────────┬───────────┘
                  │                               │
                  │                               │ tool calls
                  │                               ▼
                  │                    ┌──────────────────────┐
                  │                    │   Agent runtime      │
                  │                    │   (Anthropic / OAI)  │
                  │                    └──────────────────────┘
                  │
                  ▼
       ┌──────────────────────┐
       │   PostgreSQL 16 +    │
       │   pgvector + pg_trgm │
       └──────────────────────┘

       Redis (queue + cache)       MinIO (S3 evidence + reports)
```

### Key guarantees (per the spec)

- **Vulnerability-centric data model.** One row per unique vulnerability;
  assets are linked through the `findings` join table. The same vulnerability
  across many hosts is **one record with N findings**, not N records.
- **No scanner engine.** Ingestion is push (upload or webhook) or polled
  from a drop location. The platform only normalizes and dedups.
- **AI agent via MCP only.** The agent runtime is an MCP client. It never
  touches the database directly. Every tool call is audit-logged.
- **Human-approval gate.** A report can only reach `approved` via the
  `POST /reports/{id}/approve` endpoint, gated to `senior_analyst+`. The
  agent has no such tool — it terminates at `flag_for_human_review`.
- **No SSO/OIDC.** Email+password with Argon2id and mandatory TOTP for
  analyst and admin roles.
- **Multi-tenant.** Every query is workspace-scoped; cross-tenant access
  is denied and tested.
- **Local / on-prem deployment.** Docker Compose + Caddy; no cloud deps
  beyond the model API.

---

## Quick start

```bash
# 1) Copy env
cp .env.example .env
$EDITOR .env                 # set JWT_SECRET, LLM_API_KEY, passwords

# 2) Bring the stack up
docker compose up -d --build

# 3) Open
#    http://localhost:5173      → UI
#    http://localhost:8000/docs → FastAPI docs
#    http://localhost:8081      → MCP server
#    http://localhost:9001      → MinIO console (admin / changeme_minio_pw)

# 4) Seed a platform admin (one-off)
docker compose exec backend python -c "
import asyncio
from sqlalchemy.ext.asyncio import async_sessionmaker, create_asyncengine
" 2>/dev/null || true
# (Use the API once you have a way in; in dev the first user can be
# bootstrapped by an env-driven CLI in a future release.)
```

---

## Services

| Service        | Port (host)    | Notes                                      |
|----------------|----------------|--------------------------------------------|
| frontend       | `127.0.0.1:5173` | Vite dev (dev compose)                  |
| backend        | `127.0.0.1:8000` | FastAPI, Uvicorn                       |
| mcp            | `127.0.0.1:8081` | MCP HTTP server                          |
| postgres       | `127.0.0.1:5432` | pgvector enabled                        |
| redis          | internal        | queue + cache                            |
| minio          | `127.0.0.1:9000` | S3-compatible evidence + reports         |
| minio (admin)  | `127.0.0.1:9001` | MinIO console                           |

Production compose (`docker-compose.prod.yml`) replaces the per-service
host ports with Caddy on `:80/:443`.

---

## MCP tools (the agent's only API)

| Tool                          | Purpose                                                  |
|-------------------------------|----------------------------------------------------------|
| `list_findings`               | List findings in an engagement (filter by status/severity) |
| `get_vulnerability`           | Full vuln detail incl. linked assets                      |
| `get_asset_context`           | Asset metadata + prior findings count                    |
| `check_duplicate`             | pgvector cosine match for a (title, desc) pair            |
| `draft_finding_narrative`     | Persist AI impact/recommendation **as draft** (not approved) |
| `generate_exec_summary_stats` | Aggregate severity counts, top-risk assets                |
| `render_report`               | Render a docx draft into S3, status=`draft`              |
| `flag_for_human_review`       | Agent's terminal call — hands off to a human              |

The agent loop ends with `flag_for_human_review`. There is **no** `approve`
tool exposed to the agent. Approval is a server-side guard on the REST API.

---

## Environment variables

See `.env.example`. The non-obvious ones:

| Var                         | Purpose                                                 |
|-----------------------------|---------------------------------------------------------|
| `JWT_SECRET`                | ≥ 64 random chars. Used to sign access + refresh tokens |
| `LLM_API_KEY`               | Anthropic API key (or OpenAI-compatible base URL/key)   |
| `LLM_BASE_URL`              | Optional: swap to an OpenAI-compatible endpoint         |
| `LLM_PROVIDER`              | `anthropic` or `openai`                                 |
| `INGESTION_DROP_PATH`       | Local dir watched for new scan exports                   |
| `ARGON2_TIME_COST`          | Argon2id cost (default 3)                              |
| `LOGIN_MAX_ATTEMPTS`        | Failed logins before lockout (default 5)                |

---

## Backup & restore

```bash
# Nightly dump (run from the host, where ${INGESTION_DROP_PATH} mounts)
./deploy/backup.sh

# Restore
./deploy/restore.sh /var/backups/vapt/vapt-2025-01-15.sql.gz
```

The script:
1. `pg_dump` the database, gzipped.
2. `mc mirror` the MinIO evidence bucket to a local path.
3. Prune anything older than `BACKUP_RETENTION_DAYS`.

---

## Adding a new ingestion parser

1. Create `backend/app/services/ingestion/<format>.py` exporting
   `parse(blob: bytes) -> list[NormalizedItem]`.
2. Register the format in `backend/app/services/ingestion/service.py::detect_format`.
3. Add tests in `backend/tests/test_ingestion_<format>.py` covering at least:
   one item per `NormalizedItem` field, and a "same vuln, many hosts" dedup case.
4. Add a sample file under `backend/tests/fixtures/` (do **not** commit a real
   client scan without a scrubbing job).

---

## Testing

```bash
# Backend
cd backend
pytest -x -v

# Frontend
cd ../frontend
npm run test
```

The dedup test (`tests/test_dedup.py::test_same_vuln_many_hosts_one_record`)
is the canonical test for the spec's central guarantee. The MCP contract
tests (`tests/test_mcp.py`) lock in the agent↔server contract.

---

## Production checklist

- [ ] Set `APP_ENV=production`
- [ ] Generate strong `JWT_SECRET` (≥ 64 chars, random)
- [ ] Set all `*_PASSWORD` and `JWT_SECRET` via secrets, not committed env
- [ ] Caddy handles TLS for `CADDY_DOMAIN`
- [ ] `MINIO_BUCKET` private (the compose sets this)
- [ ] `BACKUP_PATH` mounted on a separate volume
- [ ] Reverse proxy exposes only 80/443
- [ ] Log shipping (Loki/ELK) hooked to the JSON stdout
- [ ] Synthetic Nessus load test passed at expected host count

---

## What this project deliberately does not do

- **No scanner.** This is the management plane. Bring your own Nessus/Qualys/Burp/ZAP/Nuclei.
- **No SSO/OIDC.** Argon2id + TOTP only. Per spec. (Optional LDAP sync is a user-provisioning
  channel, not SSO — see "LDAP" below.)
- **No local LLM inference in the default stack.** All model calls go to Anthropic
  or an OpenAI-compatible endpoint. The `local` LLM provider is opt-in (air-gapped).
- **No automatic publication.** A report that has been `flag_for_human_review`'d
  cannot be downloaded as final until a human with `senior_analyst+` role
  clicks **Approve & Lock**.

---

## v2 features (added on top of the spec's 7 phases)

| Area             | What                                                                                  |
|------------------|---------------------------------------------------------------------------------------|
| Threat Intel     | NVD / EPSS / CISA KEV enrichment per CVE, with 24h cache                               |
| Risk Score       | Composite (severity × criticality × EPSS × KEV × CVSS × recency), 0–100, recomputed nightly |
| Comments         | Threaded findings comments with `@email` mentions → in-app + email notifications      |
| Retests          | Schedule a follow-up engagement; auto-diff (regressed / remediated / new)             |
| Evidence         | Content-addressed (SHA-256) — same PoC image uploaded once, referenced N times        |
| API Tokens       | Long-lived, scoped, rotatable — for Nessus/Burp/Nuclei push integrations              |
| Webhooks         | HMAC-SHA256 signed, retried with backoff, per-event subscribed                          |
| Client Portal    | Tokenized, view-counted, time-bounded, watermarked docx download — no email         |
| Agent Live       | WebSocket feed of the in-progress agent run (tool calls + results as they happen)      |
| Agent Feedback   | Capture AI-vs-final diffs → few-shot corpus for next run; per-analyst approval stats |
| LDAP / AD        | Opt-in user provisioning. Password check delegates to LDAP bind as fallback          |
| SBOM             | CycloneDX (JSON) + SPDX (JSON) upload → components as assets                          |
| Local LLM        | Optional llama-cpp-python provider for air-gapped deployments                         |
| Real embeddings  | sentence-transformers sidecar; SHA placeholder is still the safe default              |
| DocX signing     | Report renderer embeds the signed payload in core properties so the file is verifiable on its own |
| CI               | ruff + mypy + pytest + dedup-guarantee gate + pip-audit + frontend tsc/vitest       |
| Pre-commit       | Runs the dedup test on every commit to `app/services/dedup/`                          |

### How to enable the embedder (real semantic dedup)

```bash
# In .env
EMBEDDING_BACKEND=remote
EMBEDDER_URL=http://embedder:9090
```

The `embedder` service is in the default compose stack and pre-downloads
`sentence-transformers/all-MiniLM-L6-v2` at build time.

### How to enable local LLM (air-gap)

```bash
# In .env
LLM_PROVIDER=local
LOCAL_LLM_PATH=/models/llama-3.1-8b-instruct.Q4_K_M.gguf
LOCAL_LLM_CTX=8192
```

The local provider is loaded lazily; if the file is missing the agent
falls back to a stub error so you see it explicitly.
