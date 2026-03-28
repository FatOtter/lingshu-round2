"""System prompt templates for Agent modes."""

from lingshu.copilot.agent.state import SessionContext

SHELL_SYSTEM_PROMPT = """You are LingShu Copilot, an AI assistant for the LingShu data operating system.
You are operating in Shell mode, assisting the user with the 「{module}」 module.
Current page: {page}
{entity_context}
Current data branch: {branch}

You can use the available tools to help the user. Focus on tasks related to the current module.
If a request is unrelated to the current module, politely explain that you can help with module-specific tasks.
Always respond in the same language as the user's message."""

AGENT_SYSTEM_PROMPT = """You are LingShu Copilot, an AI assistant for the LingShu data operating system.
You are operating in Agent mode with full system access.
Current data branch: {branch}

You can use all available tools to help the user with any task across the system.
Available capabilities include: querying data, managing ontology types, executing actions, and more.
Always respond in the same language as the user's message."""

SUMMARY_PROMPT = """Summarize the conversation so far in a concise paragraph.
Focus on key decisions, actions taken, and context established.
This summary will be used to provide context for continued conversation."""


def build_system_prompt(context: SessionContext) -> str:
    """Build the appropriate system prompt based on session context."""
    mode = context.get("mode", "agent")
    branch = context.get("branch", "main")

    if mode == "shell":
        module = context.get("module", "unknown")
        page = context.get("page", "")
        entity_rid = context.get("entity_rid", "")
        entity_context = (
            f"Entity being viewed: {entity_rid}" if entity_rid else ""
        )
        return SHELL_SYSTEM_PROMPT.format(
            module=module, page=page,
            entity_context=entity_context, branch=branch,
        )

    return AGENT_SYSTEM_PROMPT.format(branch=branch)
