"""Agent state definition for LangGraph."""

from typing import Any, TypedDict


class SessionContext(TypedDict, total=False):
    """Session context for Agent reasoning."""

    mode: str  # "shell" or "agent"
    module: str  # Current module (shell mode)
    page: str  # Current page path (shell mode)
    entity_rid: str  # Currently viewing entity RID
    active_skills: list[str]  # Active Skill RIDs
    model_rid: str  # Base model RID in use
    branch: str  # Data branch (default "main")


class CopilotState(TypedDict, total=False):
    """Agent state for LangGraph StateGraph.

    Extends the concept of MessagesState with context and summary.
    """

    messages: list[dict[str, Any]]  # Conversation history
    context: SessionContext  # Session context
    summary: str  # Long conversation summary
