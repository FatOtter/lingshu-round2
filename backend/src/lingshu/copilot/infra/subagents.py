"""Sub-Agent management: CRUD for sub_agents table + tool conversion.

Configuration example (via API POST /copilot/v1/sub-agents):
    {
        "api_name": "data_analyst",
        "display_name": "Data Analyst",
        "description": "Analyzes data and produces reports",
        "model_rid": "ri.model.gemini-flash",
        "system_prompt": "You are a data analyst. Analyze data carefully.",
        "tool_bindings": [
            {"tool": "query_data", "params": {"source": "main"}},
            {"tool": "chart_builder"}
        ],
        "safety_policy": {
            "max_iterations": 10,
            "allow_write": false
        },
        "enabled": true
    }

When ``model_rid`` is None, the sub-agent operates in stub mode — tool
invocation returns a placeholder response. Configure a model via the
Models API first, then reference its RID to enable full LLM-backed execution.
"""

from typing import Any

from sqlalchemy import func as sa_func
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from lingshu.copilot.models import SubAgent
from lingshu.infra.context import get_tenant_id
from lingshu.infra.errors import AppError, ErrorCode
from lingshu.infra.rid import generate_rid


class SubAgentManager:
    """CRUD manager for Sub-Agents."""

    async def register(
        self,
        session: AsyncSession,
        *,
        api_name: str,
        display_name: str,
        description: str | None = None,
        model_rid: str | None = None,
        system_prompt: str | None = None,
        tool_bindings: list[dict[str, Any]] | None = None,
        safety_policy: dict[str, Any] | None = None,
        enabled: bool = True,
    ) -> SubAgent:
        """Register a new sub-agent."""
        tenant_id = get_tenant_id()

        agent = SubAgent(
            rid=generate_rid("subagent"),
            tenant_id=tenant_id,
            api_name=api_name,
            display_name=display_name,
            description=description,
            model_rid=model_rid,
            system_prompt=system_prompt,
            tool_bindings=tool_bindings or [],
            safety_policy=safety_policy or {},
            enabled=enabled,
        )
        session.add(agent)
        await session.flush()
        await session.commit()
        return agent

    async def get(
        self, rid: str, session: AsyncSession,
    ) -> SubAgent:
        tenant_id = get_tenant_id()
        result = await session.execute(
            select(SubAgent).where(
                SubAgent.rid == rid,
                SubAgent.tenant_id == tenant_id,
            )
        )
        agent = result.scalar_one_or_none()
        if not agent:
            raise AppError(
                code=ErrorCode.COMMON_NOT_FOUND,
                message=f"Sub-agent {rid} not found",
            )
        return agent

    async def update(
        self,
        rid: str,
        updates: dict[str, Any],
        session: AsyncSession,
    ) -> SubAgent:
        tenant_id = get_tenant_id()

        await session.execute(
            update(SubAgent)
            .where(
                SubAgent.rid == rid,
                SubAgent.tenant_id == tenant_id,
            )
            .values(**updates)
        )
        await session.flush()
        await session.commit()
        return await self.get(rid, session)

    async def delete(
        self, rid: str, session: AsyncSession,
    ) -> None:
        tenant_id = get_tenant_id()
        result = await session.execute(
            select(SubAgent).where(
                SubAgent.rid == rid,
                SubAgent.tenant_id == tenant_id,
            )
        )
        agent = result.scalar_one_or_none()
        if not agent:
            raise AppError(
                code=ErrorCode.COMMON_NOT_FOUND,
                message=f"Sub-agent {rid} not found",
            )
        await session.delete(agent)
        await session.commit()

    async def query(
        self,
        session: AsyncSession,
        *,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[SubAgent], int]:
        tenant_id = get_tenant_id()
        base = select(SubAgent).where(
            SubAgent.tenant_id == tenant_id,
        )
        count_result = await session.execute(
            select(sa_func.count()).select_from(base.subquery())
        )
        total = count_result.scalar_one()

        result = await session.execute(
            base.order_by(SubAgent.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return list(result.scalars().all()), total

    async def set_enabled(
        self,
        rid: str,
        enabled: bool,
        session: AsyncSession,
    ) -> SubAgent:
        return await self.update(rid, {"enabled": enabled}, session)


def load_as_tool(subagent: SubAgent) -> dict[str, Any]:
    """Convert a sub-agent definition into a callable tool schema for the main agent.

    Returns a tool schema dict that describes the sub-agent as an invocable tool.
    The main agent can call this tool, which will delegate to a nested agent run
    with the sub-agent's system_prompt and tool_bindings.
    """
    return {
        "name": f"subagent_{subagent.api_name}",
        "description": (
            subagent.description
            or f"Delegate to sub-agent: {subagent.display_name}"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "input": {
                    "type": "string",
                    "description": "The task or question to delegate to this sub-agent.",
                },
            },
            "required": ["input"],
        },
        "metadata": {
            "type": "subagent",
            "rid": subagent.rid,
            "model_rid": subagent.model_rid,
            "system_prompt": subagent.system_prompt,
            "tool_bindings": subagent.tool_bindings,
            "safety_policy": subagent.safety_policy,
        },
    }
