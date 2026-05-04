"""
KnowledgeAgent — answers product questions using RAG search.
Citations reference chunk IDs so answers are traceable.
"""

from google.adk.agents import LlmAgent
from google.adk.tools import FunctionTool
from app.config import settings

from app.rag.search import search_docs as _search_docs


def search_docs_tool(query: str, k: int = 3) -> str:
    """
    Search the Helix product documentation for relevant information.

    Args:
        query: The search query describing what information to find.
        k: Number of top results to return (default 3).

    Returns:
        A formatted string with chunk IDs and their content for citation.
    """
    results = _search_docs(query, k=k)
    if not results:
        return "No relevant documentation found for this query."

    formatted_parts: list[str] = []
    for r in results:
        source = r.metadata.get("source_file", "unknown")
        title = r.metadata.get("title", "")
        header = f"[{r.chunk_id}] (source: {source}"
        if title:
            header += f", title: {title}"
        header += f", score: {r.score})"
        formatted_parts.append(f"{header}\n{r.content}")

    return "\n\n---\n\n".join(formatted_parts)


KNOWLEDGE_INSTRUCTION = """You are the Knowledge Agent for Helix, a B2B SaaS dev-tools platform.

Your job is to answer product questions by searching the Helix documentation using the search_docs_tool.

IMPORTANT RULES:
1. ALWAYS use the search_docs_tool to find relevant information before answering.
2. ALWAYS cite chunk IDs in your answers using the format: "According to [chunk_id]..."
3. If multiple chunks are relevant, cite all of them.
4. If no relevant documentation is found, say so clearly.
5. Do NOT make up information that isn't in the documentation.
6. Be concise but thorough.
"""

knowledge_agent = LlmAgent(
    name="knowledge_agent",
    model=settings.GEMINI_MODEL,
    instruction=KNOWLEDGE_INSTRUCTION,
    tools=[FunctionTool(search_docs_tool)],
    description="Answers product and documentation questions about Helix using RAG search. Use this agent when the user asks about how to use features, configuration, setup, troubleshooting, or any product-related question.",
)
