"""Shared test fixtures."""

from __future__ import annotations

import asyncio
import os
import uuid
from pathlib import Path
from typing import AsyncIterator

import pytest
import pytest_asyncio
from dotenv import load_dotenv
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

# Load .env from the project root (where docker-compose expects it). The
# `pydantic_settings` BaseSettings auto-loads from cwd-relative .env; in tests
# we run from `backend/`, so we have to point it at the right file. This MUST
# run before any `app.*` import.
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
load_dotenv(_PROJECT_ROOT / ".env", override=False)

from app.core.config import settings  # noqa: E402  (env must be loaded first)
from app.core.db import Base, get_session  # noqa: E402
from app.main import app  # noqa: E402


# Use a dedicated test database if present; otherwise an in-memory SQLite
# (we disable pgvector-only ops in tests that don't need them).
TEST_DB_URL = os.environ.get(
    "TEST_DATABASE_URL",
    "postgresql+asyncpg://vapt:vapt@localhost:5432/vapt_test",
)


@pytest_asyncio.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="session")
async def engine():
    eng = create_async_engine(TEST_DB_URL, echo=False, future=True)
    async with eng.begin() as conn:
        # full reset for a clean test
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield eng
    await eng.dispose()


@pytest_asyncio.fixture
async def db(engine) -> AsyncIterator:
    SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)
    async with SessionLocal() as s:
        yield s
        await s.rollback()


@pytest_asyncio.fixture
async def client(engine) -> AsyncIterator[AsyncClient]:
    SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)

    async def _override():
        async with SessionLocal() as s:
            yield s

    app.dependency_overrides[get_session] = _override
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()
