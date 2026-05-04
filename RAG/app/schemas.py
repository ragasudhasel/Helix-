"""
Pydantic v2 request/response models for the SROP API.
"""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


# ── Session ──────────────────────────────────────────────────────────

class CreateSessionRequest(BaseModel):
    """Body for POST /v1/sessions."""
    user_id: str = Field(..., min_length=1, description="Unique user identifier")
    plan_tier: str = Field(
        default="free",
        description="User's plan tier (free, pro, enterprise)",
    )


class CreateSessionResponse(BaseModel):
    """Response from POST /v1/sessions."""
    session_id: str


# ── Chat ─────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    """Body for POST /v1/chat/{session_id}."""
    message: str = Field(..., min_length=1, description="User message")


class ChatResponse(BaseModel):
    """Response from POST /v1/chat/{session_id}."""
    reply: str
    routed_to: str | None = None
    trace_id: str


# ── Trace ────────────────────────────────────────────────────────────

class ToolCallRecord(BaseModel):
    """Individual tool invocation record."""
    tool_name: str
    args: dict[str, Any] = Field(default_factory=dict)
    result: Any = None


class TraceResponse(BaseModel):
    """Response from GET /v1/traces/{trace_id}."""
    trace_id: str
    session_id: str
    routed_to: str | None = None
    tool_calls: list[ToolCallRecord] = Field(default_factory=list)
    retrieved_chunk_ids: list[str] = Field(default_factory=list)
    latency_ms: float
    created_at: datetime


# ── Errors ───────────────────────────────────────────────────────────

class ErrorResponse(BaseModel):
    """Standard error envelope."""
    error: str
    detail: str | None = None


# ── Health ───────────────────────────────────────────────────────────

class HealthResponse(BaseModel):
    """Response from GET /healthz."""
    status: str = "ok"
    version: str = "1.0.0"
