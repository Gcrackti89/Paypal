from __future__ import annotations
import asyncio
import uuid
from datetime import datetime, timezone, timedelta, date
from decimal import Decimal
from typing import AsyncGenerator
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import StaticPool

# Use SQLite in-memory for tests
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

import os
os.environ.setdefault("DATABASE_URL", TEST_DATABASE_URL)
os.environ.setdefault("APP_SECRET_KEY", "test-secret-key-32-bytes-long-enough")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-32-bytes-long")
os.environ.setdefault("PAYPAL_ENV", "sandbox")
os.environ.setdefault("PAYPAL_BASE_URL", "https://api-m.sandbox.paypal.com")
os.environ.setdefault("PAYPAL_CLIENT_ID", "test-client-id")
os.environ.setdefault("PAYPAL_CLIENT_SECRET", "test-client-secret")
os.environ.setdefault("PAYPAL_WEBHOOK_ID", "test-webhook-id")
os.environ.setdefault("OPENAI_API_KEY", "test-openai-key")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("CELERY_BROKER_URL", "redis://localhost:6379/1")
os.environ.setdefault("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")
os.environ.setdefault("CORS_ORIGINS", '["http://localhost:3000"]')

from backend.database import Base, get_db_session
from backend.main import app

# Test engine - SQLite async
test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestSessionLocal = async_sessionmaker(test_engine, expire_on_commit=False)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest_asyncio.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    # Create all tables fresh for each test
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with TestSessionLocal() as session:
        yield session

    # Drop tables after each test
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    async def override_db():
        yield db_session

    app.dependency_overrides[get_db_session] = override_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def registered_user(client: AsyncClient) -> dict:
    resp = await client.post("/api/v1/auth/register", json={
        "email": "test@example.com",
        "password": "TestPass123",
        "full_name": "Test User",
    })
    assert resp.status_code == 201
    return resp.json()


@pytest_asyncio.fixture
async def auth_headers(registered_user: dict) -> dict:
    return {"Authorization": f"Bearer {registered_user['access_token']}"}


@pytest_asyncio.fixture
async def second_user_headers(client: AsyncClient) -> dict:
    resp = await client.post("/api/v1/auth/register", json={
        "email": "other@example.com",
        "password": "OtherPass123",
        "full_name": "Other User",
    })
    assert resp.status_code == 201
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


async def create_test_invoice(client: AsyncClient, headers: dict, **overrides) -> dict:
    payload = {
        "customer_name": "Alice Smith",
        "customer_email": "alice@example.com",
        "currency": "USD",
        "line_items": [
            {"description": "Web design", "quantity": "2", "unit_price": "100.00"}
        ],
        "due_date": (date.today() + timedelta(days=7)).isoformat(),
    }
    payload.update(overrides)
    resp = await client.post("/api/v1/invoices/drafts", json=payload, headers=headers)
    assert resp.status_code == 201
    return resp.json()
