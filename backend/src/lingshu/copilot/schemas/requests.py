"""Copilot module request DTOs."""

from typing import Any

from pydantic import BaseModel, Field

from lingshu.infra.models import QueryRequest


class CreateSessionRequest(BaseModel):
    """Request to create a new copilot session."""

    mode: str = Field(default="agent", pattern="^(shell|agent)$")
    context: dict[str, Any] = Field(default_factory=dict)


class SendMessageRequest(BaseModel):
    """Request to send a message to the agent."""

    content: str = Field(min_length=1, max_length=10000)


class ResumeRequest(BaseModel):
    """Request to resume an interrupted agent."""

    approved: bool


class UpdateContextRequest(BaseModel):
    """Request to update session context."""

    context: dict[str, Any]


class QuerySessionsRequest(QueryRequest):
    """Query sessions."""

    pass


class RegisterModelRequest(BaseModel):
    """Request to register a base model."""

    api_name: str = Field(min_length=1, max_length=100)
    display_name: str = Field(min_length=1, max_length=200)
    provider: str = Field(min_length=1)
    connection: dict[str, Any] = Field(default_factory=dict)
    parameters: dict[str, Any] = Field(default_factory=dict)
    is_default: bool = False


class UpdateModelRequest(BaseModel):
    """Request to update a base model."""

    display_name: str | None = None
    provider: str | None = None
    connection: dict[str, Any] | None = None
    parameters: dict[str, Any] | None = None
    is_default: bool | None = None


# ── Skill Requests ────────────────────────────────────────────────


class CreateSkillRequest(BaseModel):
    """Request to register a new copilot skill."""

    api_name: str = Field(min_length=1, max_length=100)
    display_name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    system_prompt: str = Field(min_length=1)
    tool_bindings: list[dict[str, Any]] = Field(default_factory=list)


class UpdateSkillRequest(BaseModel):
    """Request to update a copilot skill."""

    display_name: str | None = None
    description: str | None = None
    system_prompt: str | None = None
    tool_bindings: list[dict[str, Any]] | None = None
    enabled: bool | None = None


class QuerySkillsRequest(QueryRequest):
    """Query skills."""

    pass


# ── MCP Requests ──────────────────────────────────────────────────


class ConnectMcpRequest(BaseModel):
    """Request to register a new MCP connection."""

    api_name: str = Field(min_length=1, max_length=100)
    display_name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    transport: dict[str, Any]
    auth: dict[str, Any] | None = None


class UpdateMcpRequest(BaseModel):
    """Request to update an MCP connection."""

    display_name: str | None = None
    description: str | None = None
    transport: dict[str, Any] | None = None
    auth: dict[str, Any] | None = None
    enabled: bool | None = None


class QueryMcpRequest(QueryRequest):
    """Query MCP connections."""

    pass


# ── Sub-Agent Requests ───────────────────────────────────────────


class CreateSubAgentRequest(BaseModel):
    """Request to create a new sub-agent."""

    api_name: str = Field(min_length=1, max_length=100)
    display_name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    model_rid: str | None = None
    system_prompt: str | None = None
    tool_bindings: list[dict[str, Any]] = Field(default_factory=list)
    safety_policy: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class UpdateSubAgentRequest(BaseModel):
    """Request to update a sub-agent."""

    display_name: str | None = None
    description: str | None = None
    model_rid: str | None = None
    system_prompt: str | None = None
    tool_bindings: list[dict[str, Any]] | None = None
    safety_policy: dict[str, Any] | None = None
    enabled: bool | None = None


class QuerySubAgentsRequest(QueryRequest):
    """Query sub-agents."""

    pass
