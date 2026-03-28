"""Response DTOs for Data module APIs."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_serializer

_SENSITIVE_KEYS = frozenset({
    "password", "secret", "token", "api_key", "private_key",
    "secret_key", "access_key", "s3_secret_key",
})


class ConnectionResponse(BaseModel):
    rid: str
    display_name: str
    type: str
    config: dict[str, Any] = Field(default_factory=dict)
    status: str = "disconnected"
    status_message: str | None = None
    last_tested_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @field_serializer("config")
    def scrub_config(self, config: dict[str, Any]) -> dict[str, Any]:
        """Remove sensitive values from config before returning to clients."""
        return {
            k: "***" if k.lower() in _SENSITIVE_KEYS else v
            for k, v in config.items()
        }


class ConnectionTestResponse(BaseModel):
    success: bool
    latency_ms: float = 0
    server_version: str | None = None
    error: str | None = None


class InstanceQueryResponse(BaseModel):
    rows: list[dict[str, Any]]
    total: int
    columns: list[str] = Field(default_factory=list)
    schema_info: dict[str, Any] | None = None


class BranchResponse(BaseModel):
    name: str
    hash: str
    metadata: dict[str, Any] | None = None


class DataOverviewResponse(BaseModel):
    connections: dict[str, Any]
