"""Parameter resolver: resolve action parameters from definitions."""

from typing import Any

from lingshu.data.interface import DataService
from lingshu.infra.context import get_tenant_id
from lingshu.infra.errors import AppError, ErrorCode


class ResolvedParams:
    """Container for resolved parameters."""

    def __init__(
        self,
        values: dict[str, Any],
        instances: dict[str, dict[str, Any]],
    ) -> None:
        self.values = values
        self.instances = instances


class ParamResolver:
    """Resolve action parameters based on their definition_source."""

    def __init__(self, data_service: DataService) -> None:
        self._data = data_service

    async def resolve(
        self,
        param_defs: list[dict[str, Any]],
        raw_params: dict[str, Any],
    ) -> ResolvedParams:
        """Resolve all parameters and return resolved values + fetched instances."""
        tenant_id = get_tenant_id()
        values: dict[str, Any] = {}
        instances: dict[str, dict[str, Any]] = {}

        for param_def in param_defs:
            api_name = param_def["api_name"]
            required = param_def.get("required", False)
            raw_value = raw_params.get(api_name)

            if raw_value is None:
                if required:
                    raise AppError(
                        code=ErrorCode.FUNCTION_PARAM_INVALID,
                        message=f"Required parameter '{api_name}' is missing",
                    )
                continue

            source = param_def.get("definition_source", "explicit_type")

            if source in (
                "derived_from_object_type_rid",
                "derived_from_link_type_rid",
            ):
                type_rid = param_def.get("type_rid", "")
                instance = await self._resolve_instance(
                    type_rid, raw_value, tenant_id, api_name,
                )
                values[api_name] = raw_value
                instances[api_name] = instance

            elif source == "derived_from_interface_type_rid":
                if not isinstance(raw_value, dict) or "type_rid" not in raw_value:
                    raise AppError(
                        code=ErrorCode.FUNCTION_PARAM_INVALID,
                        message=(
                            f"Parameter '{api_name}' with interface source "
                            "requires {{type_rid, primary_key}}"
                        ),
                    )
                type_rid = raw_value["type_rid"]
                instance = await self._resolve_instance(
                    type_rid, raw_value, tenant_id, api_name,
                )
                values[api_name] = raw_value
                instances[api_name] = instance

            else:
                # explicit_type: direct value
                values[api_name] = raw_value

        return ResolvedParams(values=values, instances=instances)

    async def _resolve_instance(
        self,
        type_rid: str,
        raw_value: Any,
        tenant_id: str,
        param_name: str,
    ) -> dict[str, Any]:
        """Fetch instance from DataService by primary key."""
        if isinstance(raw_value, dict):
            primary_key = raw_value.get("primary_key", raw_value)
        else:
            raise AppError(
                code=ErrorCode.FUNCTION_PARAM_INVALID,
                message=f"Parameter '{param_name}' expects {{primary_key: ...}}",
            )

        instance = await self._data.get_instance(type_rid, tenant_id, primary_key)
        if instance is None:
            raise AppError(
                code=ErrorCode.FUNCTION_PARAM_INSTANCE_NOT_FOUND,
                message=f"Instance not found for parameter '{param_name}'",
            )
        return instance
