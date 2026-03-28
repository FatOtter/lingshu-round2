"""Action loader: fetch ActionType from OntologyService and parse execution config."""

from typing import Any

from lingshu.infra.context import get_tenant_id
from lingshu.infra.errors import AppError, ErrorCode
from lingshu.ontology.interface import OntologyService


class ActionDefinition:
    """Parsed ActionType definition ready for execution."""

    def __init__(
        self,
        rid: str,
        api_name: str,
        display_name: str,
        parameters: list[dict[str, Any]],
        execution: dict[str, Any],
        outputs: list[dict[str, Any]],
        safety_level: str,
        side_effects: list[dict[str, Any]],
    ) -> None:
        self.rid = rid
        self.api_name = api_name
        self.display_name = display_name
        self.parameters = parameters
        self.execution = execution
        self.outputs = outputs
        self.safety_level = safety_level
        self.side_effects = side_effects


class ActionLoader:
    """Load and parse ActionType definitions from OntologyService."""

    def __init__(self, ontology: OntologyService) -> None:
        self._ontology = ontology

    async def load(self, action_type_rid: str) -> ActionDefinition:
        """Load an ActionType by RID and return parsed definition."""
        tenant_id = get_tenant_id()
        node = await self._ontology.get_object_type(action_type_rid, tenant_id)
        if not node:
            raise AppError(
                code=ErrorCode.FUNCTION_NOT_FOUND,
                message=f"ActionType {action_type_rid} not found",
            )

        # Parse execution config
        execution = node.get("execution", {})
        outputs = self._extract_outputs(execution)
        safety_level = node.get("safety_level", "SAFETY_READ_ONLY")
        side_effects = node.get("side_effects", [])
        parameters = node.get("parameters", [])

        return ActionDefinition(
            rid=action_type_rid,
            api_name=node.get("api_name", ""),
            display_name=node.get("display_name", ""),
            parameters=parameters,
            execution=execution,
            outputs=outputs,
            safety_level=safety_level,
            side_effects=side_effects,
        )

    def _extract_outputs(self, execution: dict[str, Any]) -> list[dict[str, Any]]:
        """Extract outputs from execution config based on engine type."""
        exec_type = execution.get("type", "")
        config_key_map: dict[str, str] = {
            "native_crud": "native_crud_json",
            "python_venv": "python_script",
            "sql_runner": "sql_template",
            "webhook": "webhook_config_json",
        }
        config_key = config_key_map.get(exec_type)
        if config_key is not None:
            sub_config: dict[str, Any] = execution.get(config_key, {})
            outputs: list[dict[str, Any]] = sub_config.get("outputs", [])
            return outputs
        return []
