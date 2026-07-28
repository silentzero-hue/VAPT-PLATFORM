# Expand ingestion parser coverage

## Why

The platform only understood Nessus and Nmap. Real engagements need Burp, ZAP, Nuclei, OpenVAS, Trivy, Snyk, Prowler, testssl, WPScan, Nikto, Metasploit, AWS Inspector, kube-bench, SARIF, plus SBOM (CycloneDX/SPDX) and the legacy SQLite DB. The seed script also pre-populated a fake client and demo engagement, which we no longer want.

## What changes

### Backend
- `app/cli/seed_demo.py` → **deleted**
- `app/cli/bootstrap.py` → **new** minimal idempotent bootstrap (admin + empty workspace)
- `app/models/ingestion.py` → extend `IngestionFormat` enum with 13 new values
- `alembic/versions/0003_ingestion_formats.py` → enum expansion
- `app/services/ingestion/formats.py` → **new** unified `detect_format` covering all formats
- `app/services/ingestion/service.py` → dispatch to all parsers (incl. SBOM → info-severity items)
- `app/services/ingestion/{burp,zap,sarif,nuclei,openvas,trivy,snyk,prowler,testssl,wpscan,nikto,metasploit,aws_inspector,kube_bench,qualys}.py` → **14 new parsers**
- `app/api/v1/ingestion.py` → add `POST /ingestion/parse` preview endpoint, increase sniff window
- `tests/test_parsers.py` → **new** 19 tests, one per parser + detector edge cases

### Frontend
- `pages/engagements/EngagementDetailPage.tsx` → permissive `accept` attribute, supported-formats pill list with tooltips

## Compatibility

- Existing Nessus / Nmap upload flow is unchanged.
- `NormalizedItem` shape is unchanged.
- Dedup pipeline (`find_or_create`) is unchanged.
- All new parsers output through the same pipeline.
- The legacy `bootstrap_admin.py`, `enroll_totp.py`, `reset_credentials.py` are untouched.

## Validation

- `find backend -name "*.py" -exec python3 -m py_compile {} \;` passes.
- `pytest tests/test_parsers.py` → 19/19 pass.
- `tsc --noEmit` on the frontend → clean.
- Pre-existing failures in `test_legacy_parity.py` and DB-dependent tests are unrelated to this change.
