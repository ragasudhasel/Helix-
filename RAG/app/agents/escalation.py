"""
EscalationAgent — handles ticket creation when user requests a human or complex support.
"""

from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool
from app.config import settings
from app.database import async_session_factory as async_session_maker
from app.models import SupportTicket


async def create_support_ticket(user_id: str, summary: str, priority: str = "normal") -> str:
    """
    Creates a formal support ticket in the database.
    Use this when the user is frustrated, asks for a human, or has an issue that cannot be resolved automatically.
    
    Args:
        user_id: The ID of the user requesting help.
        summary: A clear summary of the issue.
        priority: 'low', 'normal', or 'high'.
    """
    async with async_session_maker() as session:
        ticket = SupportTicket(
            user_id=user_id,
            summary=summary,
            priority=priority
        )
        session.add(ticket)
        await session.commit()
        return f"Support ticket created successfully! Ticket ID: {ticket.ticket_id}. A human agent will review this shortly."


ESCALATION_INSTRUCTION = """
You are the Helix Escalation Specialist. Your job is to help users when our automated systems aren't enough.

If a user is frustrated, directly asks for a human, or has a complex billing/security issue, use the 'create_support_ticket' tool.
Always confirm the ticket ID back to the user once created.
Be professional, empathetic, and reassuring.
"""

escalation_agent = LlmAgent(
    name="escalation_agent",
    model=settings.GEMINI_MODEL,
    instruction=ESCALATION_INSTRUCTION,
    tools=[FunctionTool(create_support_ticket)],
    description="Specialized agent for creating support tickets and handling human escalation. Use this when the user is frustrated or specifically asks for a human representative.",
)
