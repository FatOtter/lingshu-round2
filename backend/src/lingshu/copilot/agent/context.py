"""Context management for Agent sessions."""

from typing import Any

from lingshu.copilot.agent.state import SessionContext


def build_context(
    mode: str,
    raw_context: dict[str, Any],
) -> SessionContext:
    """Build a SessionContext from raw request context."""
    ctx = SessionContext(
        mode=mode,
        branch=raw_context.get("branch", "main"),
    )
    if mode == "shell":
        ctx["module"] = raw_context.get("module", "")
        ctx["page"] = raw_context.get("page", "")
        if "entity_rid" in raw_context:
            ctx["entity_rid"] = raw_context["entity_rid"]

    if "model_rid" in raw_context:
        ctx["model_rid"] = raw_context["model_rid"]
    if "active_skills" in raw_context:
        ctx["active_skills"] = raw_context["active_skills"]

    return ctx


def get_branch_from_context(context: SessionContext) -> str | None:
    """Extract branch from session context."""
    return context.get("branch", "main")
