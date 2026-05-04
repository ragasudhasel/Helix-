"""
SROP Pipeline — the core orchestration logic.

Flow per turn:
  1. Load session state from SQLite
  2. Build conversation history for ADK
  3. Run ADK root agent with asyncio.wait_for timeout
  4. Parse ADK events to extract routing + tool calls + chunk IDs
  5. Save updated state back to SQLite
  6. Write agent_trace row

State is ALWAYS persisted to SQLite — never held in memory only.
This ensures state survives uvicorn restart.
"""

import asyncio
import json
import logging
import time
import uuid

from google.adk.agents import LlmAgent
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types as genai_types

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import AgentTrace, Message, Session

logger = logging.getLogger(__name__)


class UpstreamTimeoutError(Exception):
    """Raised when the LLM does not respond within the configured timeout."""
    pass


class SessionNotFoundError(Exception):
    """Raised when the requested session does not exist in the database."""
    pass


async def _load_session(db: AsyncSession, session_id: str) -> Session:
    """Load session from SQLite. Raises SessionNotFoundError if missing."""
    result = await db.execute(
        select(Session).where(Session.session_id == session_id)
    )
    session = result.scalar_one_or_none()
    if session is None:
        raise SessionNotFoundError(f"Session {session_id} not found")
    return session


async def _load_messages(db: AsyncSession, session_id: str) -> list[Message]:
    """Load all messages for a session, ordered by turn index."""
    result = await db.execute(
        select(Message)
        .where(Message.session_id == session_id)
        .order_by(Message.turn_index.asc(), Message.created_at.asc())
    )
    return list(result.scalars().all())


async def _save_message(
    db: AsyncSession,
    session_id: str,
    role: str,
    content: str,
    turn_index: int,
) -> Message:
    """Save a single message to the database."""
    msg = Message(
        session_id=session_id,
        role=role,
        content=content,
        turn_index=turn_index,
    )
    db.add(msg)
    return msg


async def _save_trace(
    db: AsyncSession,
    session_id: str,
    routed_to: str | None,
    tool_calls: list[dict],
    chunk_ids: list[str],
    latency_ms: float,
) -> AgentTrace:
    """Write one agent_trace row for this turn."""
    trace = AgentTrace(
        trace_id=uuid.uuid4().hex[:16],
        session_id=session_id,
        routed_to=routed_to,
        tool_calls=tool_calls,
        retrieved_chunk_ids=chunk_ids,
        latency_ms=round(latency_ms, 2),
    )
    db.add(trace)
    return trace


def _build_adk_history(
    messages: list[Message],
) -> list[genai_types.Content]:
    """Convert DB messages into ADK-compatible Content objects."""
    history: list[genai_types.Content] = []
    for msg in messages:
        role = "user" if msg.role == "user" else "model"
        history.append(
            genai_types.Content(
                role=role,
                parts=[genai_types.Part(text=msg.content)],
            )
        )
    return history


async def _run_adk_agent(
    agent: LlmAgent,
    user_message: str,
    history: list[genai_types.Content],
    session_state: dict,
    user_id: str,
) -> tuple[str, str | None, list[dict], list[str]]:
    """
    Run the ADK agent with timeout protection.

    Returns:
        (reply_text, routed_to, tool_calls_list, chunk_ids_list)
    """
    # ADK uses its own session management; we create a fresh InMemorySession
    # per request but inject our persisted history and state.
    session_service = InMemorySessionService()

    # Create ADK session with persisted state
    adk_session = await session_service.create_session(
        app_name=agent.name,
        user_id=user_id,
        state=session_state,
    )

    runner = Runner(
        agent=agent,
        app_name=agent.name,
        session_service=session_service,
    )

    # Build the user content for this turn
    user_content = genai_types.Content(
        role="user",
        parts=[genai_types.Part(text=user_message)],
    )

    reply_parts: list[str] = []
    routed_to: str | None = None
    tool_calls: list[dict] = []
    chunk_ids: list[str] = []

    async def _execute() -> None:
        nonlocal routed_to

        async for event in runner.run_async(
            user_id=user_id,
            session_id=adk_session.id,
            new_message=user_content,
        ):
            # Extract agent routing info from events
            if hasattr(event, "author") and event.author:
                author = event.author
                if author in ("knowledge_agent", "account_agent"):
                    routed_to = author

            # Collect text content from the event
            if hasattr(event, "content") and event.content:
                content = event.content
                if hasattr(content, "parts") and content.parts:
                    for part in content.parts:
                        if hasattr(part, "text") and part.text:
                            # Only collect text from the final author (root or routed agent)
                            reply_parts.append(part.text)

                        # Track tool calls for tracing
                        if hasattr(part, "function_call") and part.function_call:
                            fc = part.function_call
                            call_record = {
                                "tool_name": fc.name if hasattr(fc, "name") else str(fc),
                                "args": dict(fc.args) if hasattr(fc, "args") and fc.args else {},
                            }
                            tool_calls.append(call_record)

                            # Track chunk IDs from search_docs calls
                            if hasattr(fc, "name") and fc.name == "search_docs_tool":
                                # chunk IDs will be in the results
                                pass

                        # Track function responses (tool results)
                        if hasattr(part, "function_response") and part.function_response:
                            fr = part.function_response
                            if hasattr(fr, "response") and fr.response:
                                result_str = str(fr.response)
                                # Extract chunk IDs from search results
                                # Chunk IDs are 12-char hex strings in brackets like [abc123def456]
                                import re
                                found_ids = re.findall(r"\[([a-f0-9]{12})\]", result_str)
                                chunk_ids.extend(found_ids)

                                # Add result to the last tool call
                                if tool_calls:
                                    tool_calls[-1]["result"] = result_str[:500]  # truncate

    try:
        await asyncio.wait_for(
            _execute(),
            timeout=settings.LLM_TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError as exc:
        raise UpstreamTimeoutError(
            f"LLM did not respond within {settings.LLM_TIMEOUT_SECONDS}s"
        ) from exc

    reply_text = reply_parts[-1] if reply_parts else "I wasn't able to generate a response."
    return reply_text, routed_to, tool_calls, chunk_ids


async def run_pipeline(
    db: AsyncSession,
    session_id: str,
    user_message: str,
    agent: LlmAgent,
) -> tuple[str, str | None, str]:
    """
    Full pipeline: load state → run ADK → save state → write trace.

    Args:
        db: Async SQLAlchemy session
        session_id: The conversation session ID
        user_message: The user's message for this turn
        agent: The root LlmAgent to run

    Returns:
        (reply_text, routed_to, trace_id)
    """
    start_time = time.monotonic()

    # 1. Load session state from SQLite
    session = await _load_session(db, session_id)
    messages = await _load_messages(db, session_id)

    # Parse persisted state
    try:
        state_dict = json.loads(session.state_json) if session.state_json else {}
    except json.JSONDecodeError:
        logger.warning(f"Corrupt state_json for session {session_id}, resetting")
        state_dict = {}

    # Inject session metadata into state for ADK context
    state_dict["user_id"] = session.user_id
    state_dict["plan_tier"] = session.plan_tier
    state_dict["turn_count"] = session.turn_count
    if session.last_agent:
        state_dict["last_agent"] = session.last_agent

    # 2. Build conversation context
    # Include recent history as context prefix in the message
    context_parts: list[str] = []
    if messages:
        context_parts.append("=== Conversation History ===")
        for msg in messages[-10:]:  # Last 10 messages for context window
            role_label = "User" if msg.role == "user" else "Assistant"
            context_parts.append(f"{role_label}: {msg.content}")
        context_parts.append("=== End History ===\n")

    # Add session context
    context_prefix = (
        f"[Session Context: user_id={session.user_id}, "
        f"plan_tier={session.plan_tier}, "
        f"turn_count={session.turn_count}"
    )
    if session.last_agent:
        context_prefix += f", last_agent={session.last_agent}"
    context_prefix += "]\n"

    # Build the full message with context
    full_message = context_prefix
    if context_parts:
        full_message += "\n".join(context_parts) + "\n"
    full_message += f"User: {user_message}"

    # Build ADK history from past messages
    history = _build_adk_history(messages)

    # 3. Run ADK agent
    reply_text, routed_to, tool_calls, chunk_ids = await _run_adk_agent(
        agent=agent,
        user_message=full_message,
        history=history,
        session_state=state_dict,
        user_id=session.user_id,
    )

    latency_ms = (time.monotonic() - start_time) * 1000

    # 4. Save user message
    new_turn = session.turn_count + 1
    await _save_message(db, session_id, "user", user_message, new_turn)

    # 5. Save assistant reply
    await _save_message(db, session_id, "assistant", reply_text, new_turn)

    # 6. Update session state
    state_dict["turn_count"] = new_turn
    if routed_to:
        state_dict["last_agent"] = routed_to

    session.turn_count = new_turn
    session.last_agent = routed_to or session.last_agent
    session.state_json = json.dumps(state_dict)

    # 7. Write trace
    trace = await _save_trace(
        db=db,
        session_id=session_id,
        routed_to=routed_to,
        tool_calls=tool_calls,
        chunk_ids=chunk_ids,
        latency_ms=latency_ms,
    )

    # 8. Commit all changes atomically
    await db.commit()

    return reply_text, routed_to, trace.trace_id
