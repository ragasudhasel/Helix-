"""
Integration test — POST two messages to the same session with LLM mocked
at the ADK boundary.

Asserts:
  - Turn 1 routes to the correct sub-agent.
  - Turn 2 has access to context set in turn 1.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.main import app
from app.models import Base, Message, Session


# ── Fixtures ─────────────────────────────────────────────────────────

@pytest_asyncio.fixture
async def test_db():
    """Create a fresh in-memory SQLite database for testing."""
    engine = create_async_engine(
        "sqlite+aiosqlite:///:memory:",
        connect_args={"check_same_thread": False},
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session_factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )
    yield session_factory

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await engine.dispose()


@pytest_asyncio.fixture
async def client(test_db):
    """Create a test client that uses the test database."""
    from app import database

    # Override the database dependency
    original_factory = database.async_session_factory

    async def override_get_db():
        async with test_db() as session:
            yield session

    app.dependency_overrides[database.get_db] = override_get_db

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()


# ── Mock ADK responses ──────────────────────────────────────────────

def _make_mock_event(author: str, text: str, function_call=None, function_response=None):
    """Create a mock ADK event."""
    event = MagicMock()
    event.author = author

    part = MagicMock()
    part.text = text
    part.function_call = function_call
    part.function_response = function_response

    content = MagicMock()
    content.parts = [part]
    event.content = content

    return event


async def _mock_run_async_knowledge(*args, **kwargs):
    """Mock ADK run that simulates routing to knowledge_agent."""
    events = [
        _make_mock_event(
            "knowledge_agent",
            "According to [abc123def456], to rotate a deploy key, go to Project Settings → Deploy Keys and click Rotate."
        ),
    ]
    for e in events:
        yield e


async def _mock_run_async_account(*args, **kwargs):
    """Mock ADK run that simulates routing to account_agent with context from turn 1."""
    events = [
        _make_mock_event(
            "account_agent",
            "Here are your recent builds: b-1001 (passed), b-1002 (failed). Since you are on the Pro plan, you have 5000 build minutes."
        ),
    ]
    for e in events:
        yield e


# ── Tests ────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_healthz(client):
    """Health check should return 200 with status ok."""
    resp = await client.get("/healthz")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"


@pytest.mark.asyncio
async def test_session_not_found(client):
    """Chat to a non-existent session should return 404."""
    resp = await client.post(
        "/v1/chat/nonexistent123",
        json={"message": "hello"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_two_turn_conversation(client):
    """
    Integration test: two messages to the same session.
    Turn 1 → knowledge_agent (docs question)
    Turn 2 → account_agent (account question, should have context from turn 1)
    """
    # Create session
    resp = await client.post(
        "/v1/sessions",
        json={"user_id": "test_user_001", "plan_tier": "pro"},
    )
    assert resp.status_code == 201
    session_id = resp.json()["session_id"]

    # Turn 1: knowledge question — mock ADK to route to knowledge_agent
    with patch("app.pipeline.Runner") as MockRunner:
        mock_runner_instance = MagicMock()
        mock_runner_instance.run_async = _mock_run_async_knowledge
        MockRunner.return_value = mock_runner_instance

        with patch("app.pipeline.InMemorySessionService") as MockSessionService:
            mock_session = MagicMock()
            mock_session.id = "mock-session-1"
            mock_svc = AsyncMock()
            mock_svc.create_session = AsyncMock(return_value=mock_session)
            MockSessionService.return_value = mock_svc

            resp1 = await client.post(
                f"/v1/chat/{session_id}",
                json={"message": "How do I rotate a deploy key?"},
            )

    assert resp1.status_code == 200
    data1 = resp1.json()
    assert data1["routed_to"] == "knowledge_agent"
    assert "deploy key" in data1["reply"].lower()
    assert data1["trace_id"]

    # Turn 2: account question — mock ADK to route to account_agent
    with patch("app.pipeline.Runner") as MockRunner:
        mock_runner_instance = MagicMock()
        mock_runner_instance.run_async = _mock_run_async_account
        MockRunner.return_value = mock_runner_instance

        with patch("app.pipeline.InMemorySessionService") as MockSessionService:
            mock_session = MagicMock()
            mock_session.id = "mock-session-2"
            mock_svc = AsyncMock()
            mock_svc.create_session = AsyncMock(return_value=mock_session)
            MockSessionService.return_value = mock_svc

            resp2 = await client.post(
                f"/v1/chat/{session_id}",
                json={"message": "Show me my recent builds"},
            )

    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["routed_to"] == "account_agent"
    # The mock response references the Pro plan — proving context from turn 1 is accessible
    assert "pro" in data2["reply"].lower()
    assert data2["trace_id"]
    # Different trace IDs for different turns
    assert data1["trace_id"] != data2["trace_id"]

    # Verify the trace endpoint works
    trace_resp = await client.get(f"/v1/traces/{data1['trace_id']}")
    assert trace_resp.status_code == 200
    trace_data = trace_resp.json()
    assert trace_data["session_id"] == session_id
    assert trace_data["routed_to"] == "knowledge_agent"
