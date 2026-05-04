"""
SQLAlchemy ORM models for SROP.
Tables: sessions, messages, agent_traces.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import JSON, DateTime, Float, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""
    pass


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_uuid() -> str:
    return uuid.uuid4().hex


class Session(Base):
    """Tracks a user conversation session with persisted state."""

    __tablename__ = "sessions"

    session_id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=_new_uuid
    )
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    plan_tier: Mapped[str] = mapped_column(String(32), nullable=False, default="free")
    last_agent: Mapped[str | None] = mapped_column(String(64), nullable=True)
    turn_count: Mapped[int] = mapped_column(Integer, default=0)
    state_json: Mapped[str] = mapped_column(Text, default="{}")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow, onupdate=_utcnow
    )


class Message(Base):
    """Individual chat messages within a session."""

    __tablename__ = "messages"

    message_id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=_new_uuid
    )
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False)  # user | assistant
    content: Mapped[str] = mapped_column(Text, nullable=False)
    turn_index: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )


class AgentTrace(Base):
    """One trace row per turn — captures routing, tools, RAG chunks, latency."""

    __tablename__ = "agent_traces"

    trace_id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=_new_uuid
    )
    session_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    routed_to: Mapped[str | None] = mapped_column(String(64), nullable=True)
    tool_calls: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    retrieved_chunk_ids: Mapped[list | None] = mapped_column(JSON, nullable=True)
    latency_ms: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )


class SupportTicket(Base):
    """Support tickets created by the Escalation Agent."""

    __tablename__ = "support_tickets"

    ticket_id: Mapped[str] = mapped_column(
        String(64), primary_key=True, default=_new_uuid
    )
    user_id: Mapped[str] = mapped_column(String(128), nullable=False)
    summary: Mapped[str] = mapped_column(String(256), nullable=False)
    priority: Mapped[str] = mapped_column(String(16), nullable=False, default="normal")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=_utcnow
    )
