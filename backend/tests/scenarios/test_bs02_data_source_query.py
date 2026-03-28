"""BS-02: Data Source Connection and Instance Query.

Scenario: A data engineer connects a PostgreSQL data source,
configures asset mapping on an ObjectType, and queries instances
with filters, sorting, pagination, and data masking.

Steps:
1. Create connection (PostgreSQL type)
2. Test connection (mock connector)
3. Configure AssetMapping on ObjectType
4. Query instances with filter/sort/pagination
5. Verify masking applied to sensitive fields
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lingshu.data.models import Connection
from lingshu.data.service import DataServiceImpl
from lingshu.infra.errors import AppError, ErrorCode

from .conftest import mock_session


def _make_connection(
    rid: str = "ri.conn.pg1",
    tenant_id: str = "ri.tenant.test-tenant",
    conn_type: str = "postgresql",
    status: str = "disconnected",
) -> Connection:
    c = Connection(
        rid=rid,
        tenant_id=tenant_id,
        display_name="Traffic DB",
        type=conn_type,
        config={"host": "localhost", "port": 5432, "database": "traffic"},
        credentials="secret_password",
        status=status,
    )
    c.created_at = datetime.now(UTC)
    c.updated_at = datetime.now(UTC)
    return c


def _build_service() -> DataServiceImpl:
    ontology = AsyncMock()
    return DataServiceImpl(ontology_service=ontology)


class TestDataSourceQuery:
    """Complete data source connection and instance query scenario."""

    async def test_step1_create_connection(self, tenant_id) -> None:
        """Step 1: Create a PostgreSQL connection."""
        service = _build_service()
        session = mock_session()

        conn = _make_connection(tenant_id=tenant_id)

        with (
            patch("lingshu.data.service.get_tenant_id", return_value=tenant_id),
            patch("lingshu.data.service.generate_rid", return_value="ri.conn.pg1"),
            patch("lingshu.data.service.ConnectionRepository") as MockRepo,
        ):
            MockRepo.return_value.create = AsyncMock(return_value=conn)

            result = await service.create_connection(
                display_name="Traffic DB",
                conn_type="postgresql",
                config={"host": "localhost", "port": 5432, "database": "traffic"},
                credentials="secret_password",
                session=session,
            )
            assert result.rid == "ri.conn.pg1"
            assert result.type == "postgresql"
            assert result.display_name == "Traffic DB"
            session.commit.assert_awaited()

    async def test_step2_test_connection(self, tenant_id) -> None:
        """Step 2: Test connection succeeds."""
        service = _build_service()
        session = mock_session()

        conn = _make_connection(tenant_id=tenant_id)

        mock_connector = AsyncMock()
        test_result = MagicMock()
        test_result.success = True
        test_result.latency_ms = 15
        test_result.server_version = "15.2"
        test_result.error = None
        mock_connector.test_connection = AsyncMock(return_value=test_result)

        with (
            patch("lingshu.data.service.get_tenant_id", return_value=tenant_id),
            patch("lingshu.data.service.ConnectionRepository") as MockRepo,
        ):
            MockRepo.return_value.get_by_rid = AsyncMock(return_value=conn)
            MockRepo.return_value.update_fields = AsyncMock(return_value=conn)

            # Inject mock connector
            service._connectors["ri.conn.pg1"] = mock_connector

            result = await service.test_connection("ri.conn.pg1", session)
            assert result.success is True
            assert result.latency_ms == 15
            assert result.server_version == "15.2"

    async def test_step2_test_connection_failure(self, tenant_id) -> None:
        """Step 2 error path: Connection test fails."""
        service = _build_service()
        session = mock_session()

        conn = _make_connection(tenant_id=tenant_id)

        mock_connector = AsyncMock()
        test_result = MagicMock()
        test_result.success = False
        test_result.latency_ms = 0
        test_result.server_version = None
        test_result.error = "Connection refused"
        mock_connector.test_connection = AsyncMock(return_value=test_result)

        with (
            patch("lingshu.data.service.get_tenant_id", return_value=tenant_id),
            patch("lingshu.data.service.ConnectionRepository") as MockRepo,
        ):
            MockRepo.return_value.get_by_rid = AsyncMock(return_value=conn)
            MockRepo.return_value.update_fields = AsyncMock(return_value=conn)
            service._connectors["ri.conn.pg1"] = mock_connector

            result = await service.test_connection("ri.conn.pg1", session)
            assert result.success is False
            assert result.error == "Connection refused"

    async def test_step3_query_instances_no_mapping(self, tenant_id) -> None:
        """Step 3 error path: Query instances without AssetMapping raises error."""
        service = _build_service()

        schema = MagicMock()
        schema.asset_mapping = None
        service._schema_loader.get_schema = AsyncMock(return_value=schema)

        with pytest.raises(AppError) as exc_info:
            await service.query_instances(
                "ri.obj.traffic_light", tenant_id, [], [],
            )
        assert exc_info.value.code == ErrorCode.DATA_ASSET_NOT_MAPPED

    async def test_step4_query_instances_with_mapping(self, tenant_id) -> None:
        """Step 4: Query instances with full pipeline."""
        service = _build_service()

        schema = MagicMock()
        schema.asset_mapping = {
            "read_connection_id": "ri.conn.pg1",
            "read_asset_path": "public.traffic_lights",
        }
        schema.virtual_fields = []
        schema.property_types = []
        service._schema_loader.get_schema = AsyncMock(return_value=schema)

        mock_connector = AsyncMock()
        query_result = MagicMock()
        query_result.rows = [
            {"id": 1, "intersection": "Main St & 1st Ave", "status": 1},
            {"id": 2, "intersection": "Oak Rd & 2nd Ave", "status": 0},
        ]
        query_result.total = 2
        query_result.columns = ["id", "intersection", "status"]
        mock_connector.query = AsyncMock(return_value=query_result)

        service._connectors["ri.conn.pg1"] = mock_connector

        with patch(
            "lingshu.data.service.QueryEngine",
        ) as MockEngine:
            engine_instance = MockEngine.return_value
            engine_instance.query_instances = AsyncMock(return_value=query_result)

            result = await service.query_instances(
                "ri.obj.traffic_light", tenant_id, [], [],
                offset=0, limit=20,
            )
            assert result["total"] == 2
            assert len(result["rows"]) == 2
            assert result["rows"][0]["intersection"] == "Main St & 1st Ave"

    async def test_step5_masking_applied(self, tenant_id) -> None:
        """Step 5: Verify masking is applied to sensitive fields."""
        service = _build_service()

        schema = MagicMock()
        schema.asset_mapping = {
            "read_connection_id": "ri.conn.pg1",
            "read_asset_path": "public.traffic_lights",
        }
        schema.virtual_fields = []
        # Mark phone_number as sensitive
        schema.property_types = [
            {
                "api_name": "phone_number",
                "compliance": {"sensitivity": "high", "masking_strategy": "full"},
            },
        ]
        service._schema_loader.get_schema = AsyncMock(return_value=schema)

        mock_connector = AsyncMock()
        query_result = MagicMock()
        query_result.rows = [
            {"id": 1, "phone_number": "1234567890"},
        ]
        query_result.total = 1
        query_result.columns = ["id", "phone_number"]

        service._connectors["ri.conn.pg1"] = mock_connector

        with patch("lingshu.data.service.QueryEngine") as MockEngine:
            MockEngine.return_value.query_instances = AsyncMock(
                return_value=query_result,
            )
            with patch(
                "lingshu.data.service.build_masking_rules",
                return_value={"phone_number": "full"},
            ):
                with patch(
                    "lingshu.data.service.apply_masking",
                    return_value=[{"id": 1, "phone_number": "***"}],
                ):
                    result = await service.query_instances(
                        "ri.obj.traffic_light", tenant_id, [], [],
                    )
                    assert result["rows"][0]["phone_number"] == "***"

    async def test_connection_not_found(self, tenant_id) -> None:
        """Error path: Get non-existent connection."""
        service = _build_service()
        session = mock_session()

        with (
            patch("lingshu.data.service.get_tenant_id", return_value=tenant_id),
            patch("lingshu.data.service.ConnectionRepository") as MockRepo,
        ):
            MockRepo.return_value.get_by_rid = AsyncMock(return_value=None)

            with pytest.raises(AppError) as exc_info:
                await service.get_connection("ri.conn.missing", session)
            assert exc_info.value.code == ErrorCode.DATA_SOURCE_NOT_FOUND

    async def test_delete_connection(self, tenant_id) -> None:
        """Delete connection succeeds."""
        service = _build_service()
        session = mock_session()

        with (
            patch("lingshu.data.service.get_tenant_id", return_value=tenant_id),
            patch("lingshu.data.service.ConnectionRepository") as MockRepo,
        ):
            MockRepo.return_value.delete = AsyncMock(return_value=True)

            await service.delete_connection("ri.conn.pg1", session)
            session.commit.assert_awaited()
