"""Unit tests for parameter resolver."""

from unittest.mock import AsyncMock, patch

import pytest

from lingshu.function.actions.param_resolver import ParamResolver
from lingshu.infra.errors import AppError, ErrorCode


@pytest.fixture
def mock_data_service() -> AsyncMock:
    data = AsyncMock()
    data.get_instance = AsyncMock(return_value={"name": "R2-D2", "status": "active"})
    return data


@pytest.fixture
def resolver(mock_data_service: AsyncMock) -> ParamResolver:
    return ParamResolver(mock_data_service)


class TestParamResolver:
    @pytest.mark.asyncio
    async def test_explicit_param(self, resolver: ParamResolver) -> None:
        with patch(
            "lingshu.function.actions.param_resolver.get_tenant_id",
            return_value="t1",
        ):
            result = await resolver.resolve(
                [{"api_name": "status", "definition_source": "explicit_type"}],
                {"status": "maintenance"},
            )
        assert result.values["status"] == "maintenance"
        assert result.instances == {}

    @pytest.mark.asyncio
    async def test_derived_from_object_type(
        self, resolver: ParamResolver, mock_data_service: AsyncMock,
    ) -> None:
        with patch(
            "lingshu.function.actions.param_resolver.get_tenant_id",
            return_value="t1",
        ):
            result = await resolver.resolve(
                [
                    {
                        "api_name": "robot",
                        "definition_source": "derived_from_object_type_rid",
                        "type_rid": "ri.obj.123",
                        "required": True,
                    },
                ],
                {"robot": {"primary_key": {"id": "R2-D2"}}},
            )
        assert "robot" in result.instances
        assert result.instances["robot"]["name"] == "R2-D2"
        mock_data_service.get_instance.assert_called_once()

    @pytest.mark.asyncio
    async def test_missing_required_param_raises(
        self, resolver: ParamResolver,
    ) -> None:
        with (
            patch(
                "lingshu.function.actions.param_resolver.get_tenant_id",
                return_value="t1",
            ),
            pytest.raises(AppError) as exc_info,
        ):
            await resolver.resolve(
                [{"api_name": "x", "required": True}],
                {},
            )
        assert exc_info.value.code == ErrorCode.FUNCTION_PARAM_INVALID

    @pytest.mark.asyncio
    async def test_optional_param_skipped(self, resolver: ParamResolver) -> None:
        with patch(
            "lingshu.function.actions.param_resolver.get_tenant_id",
            return_value="t1",
        ):
            result = await resolver.resolve(
                [{"api_name": "opt", "required": False}],
                {},
            )
        assert "opt" not in result.values

    @pytest.mark.asyncio
    async def test_instance_not_found_raises(
        self, resolver: ParamResolver, mock_data_service: AsyncMock,
    ) -> None:
        mock_data_service.get_instance = AsyncMock(return_value=None)
        with (
            patch(
                "lingshu.function.actions.param_resolver.get_tenant_id",
                return_value="t1",
            ),
            pytest.raises(AppError) as exc_info,
        ):
            await resolver.resolve(
                [
                    {
                        "api_name": "robot",
                        "definition_source": "derived_from_object_type_rid",
                        "type_rid": "ri.obj.123",
                    },
                ],
                {"robot": {"primary_key": {"id": "missing"}}},
            )
        assert exc_info.value.code == ErrorCode.FUNCTION_PARAM_INSTANCE_NOT_FOUND

    @pytest.mark.asyncio
    async def test_interface_param_requires_type_rid(
        self, resolver: ParamResolver,
    ) -> None:
        with (
            patch(
                "lingshu.function.actions.param_resolver.get_tenant_id",
                return_value="t1",
            ),
            pytest.raises(AppError) as exc_info,
        ):
            await resolver.resolve(
                [
                    {
                        "api_name": "item",
                        "definition_source": "derived_from_interface_type_rid",
                    },
                ],
                {"item": "plain_value"},
            )
        assert exc_info.value.code == ErrorCode.FUNCTION_PARAM_INVALID
