"""Copilot module response DTOs."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SessionResponse(BaseModel):
    """Session details."""

    session_id: str
    mode: str
    title: str | None = None
    context: dict[str, Any] = Field(default_factory=dict)
    model_rid: str | None = None
    status: str = "active"
    created_at: datetime | None = None
    last_active_at: datetime | None = None


class ModelResponse(BaseModel):
    """Base model details."""

    rid: str
    api_name: str
    display_name: str
    provider: str
    connection: dict[str, Any] = Field(default_factory=dict)
    parameters: dict[str, Any] = Field(default_factory=dict)
    is_default: bool = False
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SkillResponse(BaseModel):
    """Copilot skill details."""

    rid: str
    api_name: str
    display_name: str
    description: str | None = None
    system_prompt: str
    tool_bindings: list[dict[str, Any]] = Field(default_factory=list)
    enabled: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None


class McpConnectionResponse(BaseModel):
    """MCP connection details."""

    rid: str
    api_name: str
    display_name: str
    description: str | None = None
    transport: dict[str, Any] = Field(default_factory=dict)
    auth: dict[str, Any] | None = None
    discovered_tools: list[dict[str, Any]] = Field(default_factory=list)
    status: str = "disconnected"
    enabled: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None


class SubAgentResponse(BaseModel):
    """Sub-agent details."""

    rid: str
    api_name: str
    display_name: str
    description: str | None = None
    model_rid: str | None = None
    system_prompt: str | None = None
    tool_bindings: list[dict[str, Any]] = Field(default_factory=list)
    safety_policy: dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    created_at: datetime | None = None
    updated_at: datetime | None = None


class CopilotOverviewResponse(BaseModel):
    """Copilot module overview."""

    sessions: dict[str, Any] = Field(default_factory=dict)
    models: dict[str, Any] = Field(default_factory=dict)
