"""Unit tests for WorkflowService and WorkflowRepository."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lingshu.function.models import Workflow
from lingshu.function.workflows.repository import WorkflowRepository, recompute_safety_level
from lingshu.function.workflows.service import WorkflowService
from lingshu.infra.errors import AppError


def _make_session() -> AsyncMock:
    session = AsyncMock()
    session.add = MagicMock()
    session.flush = AsyncMock()
    session.commit = AsyncMock()
    session.delete = AsyncMock()
    return session


def _make_workflow(**overrides) -> Workflow:
    defaults = dict(
        rid="ri.workflow.abc123",
        tenant_id="t1",
        api_name="test_workflow",
        display_name="Test Workflow",
        description="A test workflow",
        parameters=[],
        definition={"nodes": [], "edges": []},
        safety_level="SAFETY_READ_ONLY",
        side_effects=[],
        version=1,
        is_active=True,
        created_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
        updated_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
    )
    defaults.update(overrides)
    return Workflow(**defaults)


def _mock_scalar(session: AsyncMock, value):
    result = MagicMock()
    result.scalar_one_or_none.return_value = value
    session.execute = AsyncMock(return_value=result)


# ══════════════════════════════════════════════════════════════════
# WorkflowRepository
# ══════════════════════════════════════════════════════════════════


class TestWorkflowRepository:
    @pytest.mark.asyncio
    async def test_create(self):
        session = _make_session()
        repo = WorkflowRepository(session)
        wf = _make_workflow()
        result = await repo.create(wf)
        session.add.assert_called_once_with(wf)
        assert result is wf

    @pytest.mark.asyncio
    async def test_get_by_rid_found(self):
        session = _make_session()
        repo = WorkflowRepository(session)
        wf = _make_workflow()
        _mock_scalar(session, wf)
        result = await repo.get_by_rid("ri.workflow.abc123", "t1")
        assert result is wf

    @pytest.mark.asyncio
    async def test_get_by_rid_not_found(self):
        session = _make_session()
        repo = WorkflowRepository(session)
        _mock_scalar(session, None)
        assert await repo.get_by_rid("ri.workflow.missing", "t1") is None

    @pytest.mark.asyncio
    async def test_update_fields(self):
        session = _make_session()
        repo = WorkflowRepository(session)
        updated = _make_workflow(display_name="Updated")
        exec_result = AsyncMock()
        get_result = MagicMock()
        get_result.scalar_one_or_none.return_value = updated
        session.execute = AsyncMock(side_effect=[exec_result, get_result])

        result = await repo.update_fields("ri.workflow.abc123", "t1", display_name="Updated")
        assert result is updated

    @pytest.mark.asyncio
    async def test_delete_found(self):
        session = _make_session()
        repo = WorkflowRepository(session)
        wf = _make_workflow()
        _mock_scalar(session, wf)
        result = await repo.delete("ri.workflow.abc123", "t1")
        assert result is True
        session.delete.assert_awaited_once_with(wf)

    @pytest.mark.asyncio
    async def test_delete_not_found(self):
        session = _make_session()
        repo = WorkflowRepository(session)
        _mock_scalar(session, None)
        result = await repo.delete("ri.workflow.missing", "t1")
        assert result is False

    @pytest.mark.asyncio
    async def test_list_by_tenant(self):
        session = _make_session()
        repo = WorkflowRepository(session)
        wfs = [_make_workflow(rid=f"ri.workflow.{i}") for i in range(2)]
        count_result = MagicMock()
        count_result.scalar_one.return_value = 2
        data_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = wfs
        data_result.scalars.return_value = scalars_mock
        session.execute = AsyncMock(side_effect=[count_result, data_result])

        result, total = await repo.list_by_tenant("t1")
        assert total == 2
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_by_tenant_with_is_active(self):
        session = _make_session()
        repo = WorkflowRepository(session)
        count_result = MagicMock()
        count_result.scalar_one.return_value = 0
        data_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = []
        data_result.scalars.return_value = scalars_mock
        session.execute = AsyncMock(side_effect=[count_result, data_result])

        result, total = await repo.list_by_tenant("t1", is_active=True)
        assert total == 0
        assert result == []

    @pytest.mark.asyncio
    async def test_count_by_tenant(self):
        session = _make_session()
        repo = WorkflowRepository(session)
        result_mock = MagicMock()
        result_mock.scalar_one.return_value = 5
        session.execute = AsyncMock(return_value=result_mock)

        count = await repo.count_by_tenant("t1")
        assert count == 5


class TestRecomputeSafetyLevel:
    def test_default_read_only(self):
        result = recompute_safety_level({"nodes": [], "edges": []})
        assert result == "SAFETY_READ_ONLY"

    def test_with_safety_in_input_mappings(self):
        definition = {
            "nodes": [
                {
                    "node_id": "n1",
                    "type": "action",
                    "input_mappings": {"safety_level": "SAFETY_NON_IDEMPOTENT"},
                },
            ],
            "edges": [],
        }
        result = recompute_safety_level(definition)
        assert result == "SAFETY_NON_IDEMPOTENT"

    def test_highest_wins(self):
        definition = {
            "nodes": [
                {"node_id": "n1", "type": "action", "input_mappings": {"safety_level": "SAFETY_READ_ONLY"}},
                {"node_id": "n2", "type": "action", "input_mappings": {"safety_level": "SAFETY_CRITICAL"}},
            ],
            "edges": [],
        }
        result = recompute_safety_level(definition)
        assert result == "SAFETY_CRITICAL"


# ══════════════════════════════════════════════════════════════════
# WorkflowService
# ══════════════════════════════════════════════════════════════════


class TestWorkflowService:
    @pytest.fixture
    def service(self) -> WorkflowService:
        return WorkflowService()

    @pytest.mark.asyncio
    @patch("lingshu.function.workflows.service.get_tenant_id", return_value="t1")
    async def test_create_workflow(self, mock_tid, service: WorkflowService):
        session = _make_session()

        # Patch the Workflow constructor so server_default fields are set
        original_add = session.add

        def add_side_effect(obj):
            if hasattr(obj, "version") and obj.version is None:
                obj.version = 1
            if hasattr(obj, "is_active") and obj.is_active is None:
                obj.is_active = True
            if hasattr(obj, "created_at") and obj.created_at is None:
                obj.created_at = datetime(2025, 1, 1, tzinfo=timezone.utc)
            if hasattr(obj, "updated_at") and obj.updated_at is None:
                obj.updated_at = datetime(2025, 1, 1, tzinfo=timezone.utc)

        session.add = MagicMock(side_effect=add_side_effect)

        resp = await service.create_workflow(
            api_name="wf_test",
            display_name="WF Test",
            description="desc",
            nodes=[],
            edges=[],
            status="draft",
            session=session,
        )
        assert resp.api_name == "wf_test"
        assert resp.display_name == "WF Test"
        session.commit.assert_awaited_once()

    @pytest.mark.asyncio
    @patch("lingshu.function.workflows.service.get_tenant_id", return_value="t1")
    async def test_get_workflow_found(self, mock_tid, service: WorkflowService):
        session = _make_session()
        wf = _make_workflow()
        _mock_scalar(session, wf)
        resp = await service.get_workflow("ri.workflow.abc123", session)
        assert resp.rid == "ri.workflow.abc123"

    @pytest.mark.asyncio
    @patch("lingshu.function.workflows.service.get_tenant_id", return_value="t1")
    async def test_get_workflow_not_found(self, mock_tid, service: WorkflowService):
        session = _make_session()
        _mock_scalar(session, None)
        with pytest.raises(AppError):
            await service.get_workflow("ri.workflow.missing", session)

    @pytest.mark.asyncio
    @patch("lingshu.function.workflows.service.get_tenant_id", return_value="t1")
    async def test_update_workflow_display_name(self, mock_tid, service: WorkflowService):
        session = _make_session()
        wf = _make_workflow()
        updated = _make_workflow(display_name="New Name")
        # get_by_rid, then update_fields (execute + get_by_rid again)
        get_result = MagicMock()
        get_result.scalar_one_or_none.return_value = wf
        exec_result = AsyncMock()
        updated_result = MagicMock()
        updated_result.scalar_one_or_none.return_value = updated
        session.execute = AsyncMock(side_effect=[get_result, exec_result, updated_result])

        resp = await service.update_workflow("ri.workflow.abc123", {"display_name": "New Name"}, session)
        assert resp.display_name == "New Name"

    @pytest.mark.asyncio
    @patch("lingshu.function.workflows.service.get_tenant_id", return_value="t1")
    async def test_update_workflow_not_found(self, mock_tid, service: WorkflowService):
        session = _make_session()
        _mock_scalar(session, None)
        with pytest.raises(AppError):
            await service.update_workflow("ri.workflow.missing", {"display_name": "X"}, session)

    @pytest.mark.asyncio
    @patch("lingshu.function.workflows.service.get_tenant_id", return_value="t1")
    async def test_update_workflow_with_nodes_edges(self, mock_tid, service: WorkflowService):
        session = _make_session()
        wf = _make_workflow()
        updated = _make_workflow(definition={"nodes": [{"node_id": "n1", "type": "action"}], "edges": []})
        get_result = MagicMock()
        get_result.scalar_one_or_none.return_value = wf
        exec_result = AsyncMock()
        updated_result = MagicMock()
        updated_result.scalar_one_or_none.return_value = updated
        session.execute = AsyncMock(side_effect=[get_result, exec_result, updated_result])

        resp = await service.update_workflow(
            "ri.workflow.abc123",
            {"nodes": [{"node_id": "n1", "type": "action"}]},
            session,
        )
        assert resp is not None

    @pytest.mark.asyncio
    @patch("lingshu.function.workflows.service.get_tenant_id", return_value="t1")
    async def test_delete_workflow_found(self, mock_tid, service: WorkflowService):
        session = _make_session()
        wf = _make_workflow()
        _mock_scalar(session, wf)
        await service.delete_workflow("ri.workflow.abc123", session)
        session.commit.assert_awaited()

    @pytest.mark.asyncio
    @patch("lingshu.function.workflows.service.get_tenant_id", return_value="t1")
    async def test_delete_workflow_not_found(self, mock_tid, service: WorkflowService):
        session = _make_session()
        _mock_scalar(session, None)
        with pytest.raises(AppError):
            await service.delete_workflow("ri.workflow.missing", session)

    @pytest.mark.asyncio
    @patch("lingshu.function.workflows.service.get_tenant_id", return_value="t1")
    async def test_query_workflows(self, mock_tid, service: WorkflowService):
        session = _make_session()
        wfs = [_make_workflow(rid=f"ri.workflow.{i}") for i in range(2)]
        count_result = MagicMock()
        count_result.scalar_one.return_value = 2
        data_result = MagicMock()
        scalars_mock = MagicMock()
        scalars_mock.all.return_value = wfs
        data_result.scalars.return_value = scalars_mock
        session.execute = AsyncMock(side_effect=[count_result, data_result])

        results, total = await service.query_workflows(session)
        assert total == 2
        assert len(results) == 2

    @pytest.mark.asyncio
    @patch("lingshu.function.workflows.service.get_tenant_id", return_value="t1")
    async def test_execute_workflow(self, mock_tid, service: WorkflowService):
        session = _make_session()
        wf = _make_workflow(definition={"nodes": [], "edges": []})
        _mock_scalar(session, wf)

        resp = await service.execute_workflow("ri.workflow.abc123", {"x": 1}, session)
        assert resp.workflow_rid == "ri.workflow.abc123"
        assert resp.status == "success"

    @pytest.mark.asyncio
    @patch("lingshu.function.workflows.service.get_tenant_id", return_value="t1")
    async def test_execute_workflow_not_found(self, mock_tid, service: WorkflowService):
        session = _make_session()
        _mock_scalar(session, None)
        with pytest.raises(AppError):
            await service.execute_workflow("ri.workflow.missing", {}, session)

    def test_to_response_active(self, service: WorkflowService):
        wf = _make_workflow(is_active=True)
        resp = service._to_response(wf)
        assert resp.status == "active"

    def test_to_response_draft(self, service: WorkflowService):
        wf = _make_workflow(is_active=False)
        resp = service._to_response(wf)
        assert resp.status == "draft"

    def test_to_response_with_dict_nodes(self, service: WorkflowService):
        wf = _make_workflow(
            definition={
                "nodes": [{"node_id": "n1", "type": "action", "source_node_id": "n1", "target_node_id": "n2"}],
                "edges": [{"source_node_id": "n1", "target_node_id": "n2"}],
            }
        )
        resp = service._to_response(wf)
        assert len(resp.nodes) == 1
        assert len(resp.edges) == 1

    @pytest.mark.asyncio
    @patch("lingshu.function.workflows.service.get_tenant_id", return_value="t1")
    async def test_update_workflow_status(self, mock_tid, service: WorkflowService):
        session = _make_session()
        wf = _make_workflow()
        updated = _make_workflow(is_active=False)
        get_result = MagicMock()
        get_result.scalar_one_or_none.return_value = wf
        exec_result = AsyncMock()
        updated_result = MagicMock()
        updated_result.scalar_one_or_none.return_value = updated
        session.execute = AsyncMock(side_effect=[get_result, exec_result, updated_result])

        resp = await service.update_workflow(
            "ri.workflow.abc123", {"status": "draft"}, session,
        )
        assert resp.status == "draft"
