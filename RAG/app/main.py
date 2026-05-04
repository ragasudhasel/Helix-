"""
SROP — Stateful RAG Orchestration Pipeline
FastAPI application with lifespan, three core endpoints, and /healthz.
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import Depends, FastAPI, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.root import root_agent
from app.config import settings
from app.database import async_session_factory, create_all, get_db
from app.models import AgentTrace, Session
from app.pipeline import SessionNotFoundError, UpstreamTimeoutError, run_pipeline
from app.schemas import (
    ChatRequest,
    ChatResponse,
    CreateSessionRequest,
    CreateSessionResponse,
    ErrorResponse,
    HealthResponse,
    ToolCallRecord,
    TraceResponse,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan ─────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Startup: create tables. Shutdown: clean up."""
    logger.info("SROP starting up — creating database tables...")
    await create_all()
    logger.info("Database tables ready.")

    # Validate that API key is set
    if not settings.GEMINI_API_KEY:
        logger.warning(
            "GEMINI_API_KEY is not set! LLM calls will fail. "
            "Set it in .env or environment."
        )

    yield

    logger.info("SROP shutting down.")


# ── App ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="SROP — Stateful RAG Orchestration Pipeline",
    description="AI Support Concierge for Helix with knowledge search and account lookups.",
    version="1.0.0",
    lifespan=lifespan,
)


# ── Health ───────────────────────────────────────────────────────────

@app.get("/healthz", response_model=HealthResponse, tags=["health"])
async def healthz() -> HealthResponse:
    """Health check endpoint."""
    return HealthResponse(status="ok", version="1.0.0")


# ── POST /v1/sessions ───────────────────────────────────────────────

@app.post(
    "/v1/sessions",
    response_model=CreateSessionResponse,
    status_code=201,
    tags=["sessions"],
    responses={400: {"model": ErrorResponse}},
)
async def create_session(
    body: CreateSessionRequest,
    db: AsyncSession = Depends(get_db),
) -> CreateSessionResponse:
    """Create a new conversation session."""
    session = Session(
        user_id=body.user_id,
        plan_tier=body.plan_tier,
    )
    db.add(session)
    await db.commit()
    await db.refresh(session)

    logger.info(f"Created session {session.session_id} for user {body.user_id}")
    return CreateSessionResponse(session_id=session.session_id)


# ── POST /v1/chat/{session_id} ──────────────────────────────────────

@app.post(
    "/v1/chat/{session_id}",
    response_model=ChatResponse,
    tags=["chat"],
    responses={
        404: {"model": ErrorResponse, "description": "Session not found"},
        504: {"model": ErrorResponse, "description": "LLM timeout"},
    },
)
async def chat(
    session_id: str,
    body: ChatRequest,
    db: AsyncSession = Depends(get_db),
) -> ChatResponse:
    """Send a message in an existing session. Returns AI reply with routing info."""
    import re
    # Simple PII redaction for logs
    redacted_message = re.sub(r'[\w\.-]+@[\w\.-]+', '[EMAIL REDACTED]', body.message)
    redacted_message = re.sub(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', '[PHONE REDACTED]', redacted_message)
    logger.info(f"Session {session_id} received message: {redacted_message}")
    
    try:
        reply, routed_to, trace_id = await run_pipeline(
            db=db,
            session_id=session_id,
            user_message=body.message,
            agent=root_agent,
        )
    except SessionNotFoundError:
        raise HTTPException(
            status_code=404,
            detail={"error": "SESSION_NOT_FOUND", "detail": f"Session {session_id} does not exist"},
        )
    except UpstreamTimeoutError:
        raise HTTPException(
            status_code=504,
            detail={"error": "UPSTREAM_TIMEOUT", "detail": "LLM did not respond in time"},
        )
    except Exception as exc:
        logger.exception(f"Pipeline error for session {session_id}")
        raise HTTPException(
            status_code=500,
            detail={"error": "INTERNAL_ERROR", "detail": str(exc)},
        ) from exc

    return ChatResponse(
        reply=reply,
        routed_to=routed_to,
        trace_id=trace_id,
    )


# ── GET /v1/traces/{trace_id} ───────────────────────────────────────

@app.get(
    "/v1/traces/{trace_id}",
    response_model=TraceResponse,
    tags=["traces"],
    responses={404: {"model": ErrorResponse}},
)
async def get_trace(
    trace_id: str,
    db: AsyncSession = Depends(get_db),
) -> TraceResponse:
    """Retrieve the full structured trace for a single turn."""
    result = await db.execute(
        select(AgentTrace).where(AgentTrace.trace_id == trace_id)
    )
    trace = result.scalar_one_or_none()

    if trace is None:
        raise HTTPException(
            status_code=404,
            detail={"error": "TRACE_NOT_FOUND", "detail": f"Trace {trace_id} does not exist"},
        )

    # Parse tool_calls from JSON to structured records
    tool_call_records: list[ToolCallRecord] = []
    if trace.tool_calls:
        for tc in trace.tool_calls:
            tool_call_records.append(
                ToolCallRecord(
                    tool_name=tc.get("tool_name", "unknown"),
                    args=tc.get("args", {}),
                    result=tc.get("result"),
                )
            )

    return TraceResponse(
        trace_id=trace.trace_id,
        session_id=trace.session_id,
        routed_to=trace.routed_to,
        tool_calls=tool_call_records,
        retrieved_chunk_ids=trace.retrieved_chunk_ids or [],
        latency_ms=trace.latency_ms,
        created_at=trace.created_at,
    )
