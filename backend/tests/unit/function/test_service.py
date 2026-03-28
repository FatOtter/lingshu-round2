"""Unit tests for FunctionServiceImpl."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lingshu.function.schemas.responses import GlobalFunctionResponse
from lingshu.function.service import FunctionServiceImpl
from lingshu.infra.errors import AppError, ErrorCode


@pytest.fixture
def mock_ontology() -> AsyncMock:
    ontology = AsyncMock()
    ontology.get_object_type = AsyncMock(return_value={
        "api_name": "update_robot",
        "display_name": "Update Robot",
        "parameters": [
            {"api_name": "new_status", "definition_source": "explicit_type", "required": True},
        ],
        "execution": {
            "type": "native_crud",
            "native_crud_json": {
                "outputs": [
                    {
                        "name": "status_update",
                        "field_mappings": [
                            {"target_field": "status", "source": "new_status"},
                        ],
                    },
                ],
            },
        },
        "safety_level": "SAFETY_IDEMPOTENT_WRITE",
        "side_effects": [],
    })
    ontology.query_action_types = AsyncMock(return_value=([], 0))
    return ontology


@pytest.fixture
def mock_data() -> AsyncMock:
    data = AsyncMock()
    data.get_instance = AsyncMock(return_value={"name": "R2-D2"})
    data.query_instances = AsyncMock(return_value={"rows": [], "total": 0, "columns": []})
    return data


@pytest.fixture
def service(mock_ontology: AsyncMock, mock_data: AsyncMock) -> FunctionServiceImpl:
    return FunctionServiceImpl(
        ontology_service=mock_ontology,
        data_service=mock_data,
    )


@pytest.fixture
def mock_session() -> AsyncMock:
    session = AsyncMock()
    session.commit = AsyncMock()
    session.flush = AsyncMock()
    session.add = MagicMock()
    # Make execute return something for flush/commit
    session.execute = AsyncMock(return_value=MagicMock(scalar_one_or_none=MagicMock(return_value=None)))
    return session


class TestExecuteAction:
    @pytest.mark.asyncio
    async def test_direct_execution_idempotent(
        self, service: FunctionServiceImpl, mock_session: AsyncMock,
    ) -> None:
        with (
            patch("lingshu.function.service.get_tenant_id", return_value="t1"),
            patch("lingshu.function.service.get_user_id", return_value="u1"),
            patch("lingshu.function.actions.loader.get_tenant_id", return_value="t1"),
            patch("lingshu.function.actions.param_resolver.get_tenant_id", return_value="t1"),
        ):
            result = await service.execute_action(
                "ri.action.1",
                {"new_status": "maintenance"},
                mock_session,
            )
        assert result.status == "success"
        assert result.execution_id.startswith("exec_")

    @pytest.mark.asyncio
    async def test_pending_confirmation_non_idempotent(
        self, service: FunctionServiceImpl, mock_session: AsyncMock,
        mock_ontology: AsyncMock,
    ) -> None:
        mock_ontology.get_object_type = AsyncMock(return_value={
            "api_name": "delete_robot",
            "display_name": "Delete Robot",
            "parameters": [],
            "execution": {"type": "native_crud", "native_crud_json": {"outputs": []}},
            "safety_level": "SAFETY_NON_IDEMPOTENT",
            "side_effects": [{"category": "DATA_MUTATION"}],
        })
        with (
            patch("lingshu.function.service.get_tenant_id", return_value="t1"),
            patch("lingshu.function.service.get_user_id", return_value="u1"),
            patch("lingshu.function.actions.loader.get_tenant_id", return_value="t1"),
            patch("lingshu.function.actions.param_resolver.get_tenant_id", return_value="t1"),
        ):
            result = await service.execute_action(
                "ri.action.1", {}, mock_session,
            )
        assert result.status == "pending_confirmation"
        assert result.confirmation is not None
        assert "confirm_url" in result.confirmation

    @pytest.mark.asyncio
    async def test_skip_confirmation(
        self, service: FunctionServiceImpl, mock_session: AsyncMock,
        mock_ontology: AsyncMock,
    ) -> None:
        mock_ontology.get_object_type = AsyncMock(return_value={
            "api_name": "critical_op",
            "display_name": "Critical Op",
            "parameters": [],
            "execution": {"type": "native_crud", "native_crud_json": {"outputs": []}},
            "safety_level": "SAFETY_CRITICAL",
            "side_effects": [],
        })
        with (
            patch("lingshu.function.service.get_tenant_id", return_value="t1"),
            patch("lingshu.function.service.get_user_id", return_value="u1"),
            patch("lingshu.function.actions.loader.get_tenant_id", return_value="t1"),
            patch("lingshu.function.actions.param_resolver.get_tenant_id", return_value="t1"),
        ):
            result = await service.execute_action(
                "ri.action.1", {}, mock_session,
                skip_confirmation=True,
            )
        assert result.status == "success"


class TestCancelExecution:
    @pytest.mark.asyncio
    async def test_cancel_not_found(
        self, service: FunctionServiceImpl, mock_session: AsyncMock,
    ) -> None:
        with (
            patch("lingshu.function.service.get_tenant_id", return_value="t1"),
            pytest.raises(AppError) as exc_info,
        ):
            await service.cancel_execution("exec_missing", mock_session)
        assert exc_info.value.code == ErrorCode.FUNCTION_NOT_FOUND


class TestGlobalFunctions:
    @pytest.mark.asyncio
    async def test_create_function(
        self, service: FunctionServiceImpl, mock_session: AsyncMock,
    ) -> None:
        with patch(
            "lingshu.function.globals.registry.get_tenant_id",
            return_value="t1",
        ):
            func = await service.create_function(
                api_name="test_func",
                display_name="Test Function",
                description="A test function",
                parameters=[],
                implementation={"type": "builtin", "handler": "query_instances"},
                session=mock_session,
            )
        assert isinstance(func, GlobalFunctionResponse)
        assert func.api_name == "test_func"

    @pytest.mark.asyncio
    async def test_get_function_not_found(
        self, service: FunctionServiceImpl, mock_session: AsyncMock,
    ) -> None:
        with (
            patch(
                "lingshu.function.globals.registry.get_tenant_id",
                return_value="t1",
            ),
            pytest.raises(AppError) as exc_info,
        ):
            await service.get_function("ri.func.missing", mock_session)
        assert exc_info.value.code == ErrorCode.FUNCTION_NOT_FOUND


class TestOverview:
    @pytest.mark.asyncio
    async def test_overview_returns_counts(
        self, service: FunctionServiceImpl, mock_session: AsyncMock,
    ) -> None:
        # Mock the count queries
        mock_result = MagicMock()
        mock_result.scalar_one = MagicMock(return_value=0)
        mock_result.all = MagicMock(return_value=[])
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("lingshu.function.service.get_tenant_id", return_value="t1"):
            overview = await service.get_overview(mock_session)
        assert "functions" in overview.capabilities
        assert "actions" in overview.capabilities
        assert "workflows" in overview.capabilities

    @pytest.mark.asyncio
    async def test_overview_real_action_count(
        self, service: FunctionServiceImpl, mock_session: AsyncMock,
        mock_ontology: AsyncMock,
    ) -> None:
        """Overview returns real action count from ontology service."""
        mock_ontology.query_action_types = AsyncMock(return_value=(
            [{"rid": "ri.action.1"}, {"rid": "ri.action.2"}], 2
        ))
        mock_result = MagicMock()
        mock_result.scalar_one = MagicMock(return_value=3)
        mock_result.all = MagicMock(return_value=[])
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("lingshu.function.service.get_tenant_id", return_value="t1"):
            overview = await service.get_overview(mock_session)
        assert overview.capabilities["actions"] == 2

    @pytest.mark.asyncio
    async def test_overview_action_count_fallback_on_error(
        self, service: FunctionServiceImpl, mock_session: AsyncMock,
        mock_ontology: AsyncMock,
    ) -> None:
        """Overview falls back to 0 if ontology query fails."""
        mock_ontology.query_action_types = AsyncMock(side_effect=Exception("Neo4j down"))
        mock_result = MagicMock()
        mock_result.scalar_one = MagicMock(return_value=0)
        mock_result.all = MagicMock(return_value=[])
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("lingshu.function.service.get_tenant_id", return_value="t1"):
            overview = await service.get_overview(mock_session)
        assert overview.capabilities["actions"] == 0


class TestListCapabilities:
    @pytest.mark.asyncio
    async def test_list_capabilities_functions_only(
        self, service: FunctionServiceImpl, mock_session: AsyncMock,
    ) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one = MagicMock(return_value=0)
        mock_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("lingshu.function.service.get_tenant_id", return_value="t1"):
            caps = await service.list_capabilities(mock_session, capability_type="function")
        # Should not include actions or workflows when filtered
        for c in caps:
            assert c.type == "function"

    @pytest.mark.asyncio
    async def test_list_capabilities_includes_actions(
        self, service: FunctionServiceImpl, mock_session: AsyncMock,
        mock_ontology: AsyncMock,
    ) -> None:
        """Capability catalog includes actions from ontology."""
        mock_ontology.query_action_types = AsyncMock(return_value=([
            {
                "rid": "ri.action.abc",
                "api_name": "create_order",
                "display_name": "Create Order",
                "description": "Creates an order",
                "safety_level": "SAFETY_IDEMPOTENT_WRITE",
                "parameters": [{"api_name": "item_id", "required": True}],
                "execution": {"type": "native_crud"},
            },
        ], 1))
        mock_result = MagicMock()
        mock_result.scalar_one = MagicMock(return_value=0)
        mock_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("lingshu.function.service.get_tenant_id", return_value="t1"):
            caps = await service.list_capabilities(mock_session, capability_type="action")
        assert len(caps) == 1
        assert caps[0].type == "action"
        assert caps[0].rid == "ri.action.abc"
        assert caps[0].api_name == "create_order"
        assert caps[0].safety_level == "SAFETY_IDEMPOTENT_WRITE"

    @pytest.mark.asyncio
    async def test_list_capabilities_includes_workflows(
        self, service: FunctionServiceImpl, mock_session: AsyncMock,
    ) -> None:
        """Capability catalog includes workflows."""
        mock_wf = MagicMock()
        mock_wf.rid = "ri.workflow.xyz"
        mock_wf.api_name = "order_pipeline"
        mock_wf.display_name = "Order Pipeline"
        mock_wf.description = "End-to-end order pipeline"
        mock_wf.parameters = [{"api_name": "order_id"}]
        mock_wf.safety_level = "SAFETY_IDEMPOTENT_WRITE"
        mock_wf.side_effects = []

        mock_result = MagicMock()
        mock_result.scalar_one = MagicMock(return_value=1)
        mock_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[mock_wf])))
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("lingshu.function.service.get_tenant_id", return_value="t1"):
            caps = await service.list_capabilities(mock_session, capability_type="workflow")
        assert len(caps) == 1
        assert caps[0].type == "workflow"
        assert caps[0].rid == "ri.workflow.xyz"
        assert caps[0].api_name == "order_pipeline"

    @pytest.mark.asyncio
    async def test_list_capabilities_all_types(
        self, service: FunctionServiceImpl, mock_session: AsyncMock,
        mock_ontology: AsyncMock,
    ) -> None:
        """Capability catalog returns all types when no filter."""
        mock_ontology.query_action_types = AsyncMock(return_value=([
            {
                "rid": "ri.action.1",
                "api_name": "act1",
                "display_name": "Act 1",
                "safety_level": "SAFETY_READ_ONLY",
            },
        ], 1))

        mock_result = MagicMock()
        mock_result.scalar_one = MagicMock(return_value=0)
        mock_result.scalars = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch("lingshu.function.service.get_tenant_id", return_value="t1"):
            caps = await service.list_capabilities(mock_session)
        types = {c.type for c in caps}
        assert "action" in types
