"""
AccountAgent — handles account lookups and build queries.
Uses mock data since the wiring is what's being evaluated.
"""

from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool
from app.config import settings


# ── Mock data ────────────────────────────────────────────────────────

_MOCK_BUILDS: dict[str, list[dict[str, str]]] = {
    "default": [
        {"build_id": "b-1001", "status": "passed", "branch": "main", "timestamp": "2026-05-01T10:00:00Z"},
        {"build_id": "b-1002", "status": "failed", "branch": "develop", "timestamp": "2026-05-01T11:30:00Z"},
        {"build_id": "b-1003", "status": "passed", "branch": "main", "timestamp": "2026-05-01T14:00:00Z"},
        {"build_id": "b-1004", "status": "failed", "branch": "feature/auth", "timestamp": "2026-05-02T09:15:00Z"},
        {"build_id": "b-1005", "status": "passed", "branch": "main", "timestamp": "2026-05-02T12:45:00Z"},
    ]
}

_MOCK_ACCOUNTS: dict[str, dict[str, str | int]] = {
    "default": {
        "user_id": "user_default",
        "email": "user@example.com",
        "plan_tier": "pro",
        "projects_count": 7,
        "build_minutes_used": 1250,
        "build_minutes_limit": 5000,
        "team_members": 8,
        "status": "active",
    }
}


# ── Tool functions ───────────────────────────────────────────────────

def get_recent_builds(user_id: str, limit: int = 5) -> str:
    """
    Get the most recent builds for a user.

    Args:
        user_id: The unique identifier of the user.
        limit: Maximum number of builds to return (default 5).

    Returns:
        A formatted string with recent build information.
    """
    builds = _MOCK_BUILDS.get(user_id, _MOCK_BUILDS["default"])[:limit]

    if not builds:
        return f"No builds found for user {user_id}."

    lines: list[str] = [f"Recent builds for user {user_id}:"]
    for b in builds:
        status_emoji = "✅" if b["status"] == "passed" else "❌"
        lines.append(
            f"  {status_emoji} {b['build_id']} | {b['status']} | "
            f"branch: {b['branch']} | {b['timestamp']}"
        )
    return "\n".join(lines)


def get_account_status(user_id: str) -> str:
    """
    Get the account status and usage information for a user.

    Args:
        user_id: The unique identifier of the user.

    Returns:
        A formatted string with account details and usage stats.
    """
    account = _MOCK_ACCOUNTS.get(user_id, _MOCK_ACCOUNTS["default"]).copy()
    # Override user_id to match the requested one
    account["user_id"] = user_id

    lines = [
        f"Account status for {user_id}:",
        f"  Plan: {account['plan_tier']}",
        f"  Status: {account['status']}",
        f"  Projects: {account['projects_count']}",
        f"  Build minutes: {account['build_minutes_used']}/{account['build_minutes_limit']}",
        f"  Team members: {account['team_members']}",
    ]
    return "\n".join(lines)


ACCOUNT_INSTRUCTION = """You are the Account Agent for Helix, a B2B SaaS dev-tools platform.

Your job is to look up user account information and build history using the available tools.

IMPORTANT RULES:
1. Use get_recent_builds to show build history when asked about builds, deployments, or CI/CD status.
2. Use get_account_status to show account details when asked about their plan, usage, or account info.
3. Present the information clearly and helpfully.
4. If asked about something outside account/build scope, say so.
"""

account_agent = LlmAgent(
    name="account_agent",
    model=settings.GEMINI_MODEL,
    instruction=ACCOUNT_INSTRUCTION,
    tools=[
        FunctionTool(get_recent_builds),
        FunctionTool(get_account_status),
    ],
    description="Looks up user account information, build history, and usage statistics. Use this agent when the user asks about their builds, account status, plan usage, billing, or any account-specific data.",
)
