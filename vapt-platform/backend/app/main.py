"""FastAPI app entrypoint."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.v1 import (
    agent as agent_router,
    assets as assets_router,
    auth as auth_router,
    comments as comments_router,
    engagements as engagements_router,
    evidence as evidence_router,
    features as features_router,
    findings as findings_router,
    ingestion as ingestion_router,
    missing as missing_router,
    multiscan as multiscan_router,
    nessus as nessus_router,
    portal as portal_router,
    reports as reports_router,
    retests as retests_router,
    threat_intel as threat_intel_router,
    vulnerabilities as vulnerabilities_router,
    webhooks as webhooks_router,
    workspaces as workspaces_router,
)
from app.core.config import settings
from app.core.db import Base, engine
from app.core.limiter import limiter
from app.core.logging import configure_logging, get_logger
from app.schemas.common import HealthOut


log = get_logger(__name__)

# rate limiter (slowapi) — instance lives in app.core.limiter so all routers
# can import and share the same per-IP key_func and default limit.


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        resp = await call_next(request)
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "DENY")
        resp.headers.setdefault("Referrer-Policy", "no-referrer")
        resp.headers.setdefault(
            "Content-Security-Policy", "default-src 'none'; frame-ancestors 'none'"
        )
        if settings.app_env in ("staging", "production"):
            resp.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )
        return resp


@asynccontextmanager
async def lifespan(_app: FastAPI):
    configure_logging()
    log.info("startup", env=settings.app_env)
    # ensure S3 bucket exists on boot
    try:
        from app.services import storage
        await storage.ensure_bucket()
    except Exception:  # noqa: BLE001
        log.warning("minio_not_ready")
    yield
    log.info("shutdown")
    await engine.dispose()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs" if settings.app_env != "production" else None,
    redoc_url=None,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-VAPT-Workspace"],
)


@app.exception_handler(Exception)
async def _unhandled(request: Request, exc: Exception):  # noqa: ARG001
    log.exception("unhandled", path=str(request.url))
    return JSONResponse(
        status_code=500,
        content={"detail": "internal error", "code": "internal"},
    )


@app.get("/api/v1/health", response_model=HealthOut, tags=["health"])
async def health():
    from app.core.db import SessionLocal
    from app.services import storage
    db_ok = True
    try:
        async with SessionLocal() as s:
            await s.execute(__import__("sqlalchemy").text("SELECT 1"))
    except Exception:
        db_ok = False
    s3_ok = True
    try:
        await storage.ensure_bucket()
    except Exception:
        s3_ok = False
    return HealthOut(db=db_ok, s3=s3_ok, redis=True, status="ok")


api_v1 = "/api/v1"
app.include_router(auth_router.router, prefix=api_v1)
app.include_router(workspaces_router.router, prefix=api_v1)
app.include_router(engagements_router.router, prefix=api_v1)
app.include_router(assets_router.router, prefix=api_v1)
app.include_router(vulnerabilities_router.router, prefix=api_v1)
app.include_router(findings_router.router, prefix=api_v1)
app.include_router(reports_router.router, prefix=api_v1)
app.include_router(ingestion_router.router, prefix=api_v1)
app.include_router(agent_router.router, prefix=api_v1)
# v2 feature routers
app.include_router(comments_router.router, prefix=api_v1)
app.include_router(retests_router.router, prefix=api_v1)
app.include_router(evidence_router.router, prefix=api_v1)
app.include_router(evidence_router.tokens_router, prefix=api_v1)
app.include_router(webhooks_router.router, prefix=api_v1)
app.include_router(portal_router.router, prefix=api_v1)
# threat_feed_router MUST be registered before threat_intel_router so that
# `/threat-intel/feed` matches before the catch-all `/threat-intel/{cve_id}`.
app.include_router(missing_router.threat_feed_router, prefix=api_v1)
app.include_router(threat_intel_router.router, prefix=api_v1)
app.include_router(features_router.sbom_router, prefix=api_v1)
app.include_router(features_router.ldap_router, prefix=api_v1)
app.include_router(features_router.agent_router, prefix=api_v1)

# Legacy / Nessus live / multi-scan / table view
app.include_router(nessus_router.router, prefix=api_v1)
app.include_router(multiscan_router.router, prefix=api_v1)
app.include_router(multiscan_router.table_router, prefix=api_v1)
app.include_router(multiscan_router.legacy_router, prefix=api_v1)

# Missing endpoints (settings, sbom list, scan-jobs, multiscan/summary)
app.include_router(missing_router.settings_router, prefix=api_v1)
app.include_router(missing_router.sbom_list_router, prefix=api_v1)
app.include_router(missing_router.scan_jobs_router, prefix=api_v1)
app.include_router(missing_router.multiscan_summary_router, prefix=api_v1)

# WebSocket for live agent feed
from app.services.agent.ws_bridge import router as agent_ws_router
app.include_router(agent_ws_router, prefix=api_v1)


@app.get("/")
async def root():
    return {
        "name": settings.app_name,
        "version": "0.1.0",
        "docs": "/api/docs",
        "health": "/api/v1/health",
    }
