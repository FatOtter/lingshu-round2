"""Unit tests for T1: Immutable field protection."""

from unittest.mock import AsyncMock, patch

import pytest

from lingshu.infra.errors import AppError, ErrorCode
from lingshu.ontology.validators.immutable import (
    ENTITY_IMMUTABLE_FIELDS,
    IMMUTABLE_FIELDS,
    check_immutable_fields,
)
from lingshu.ontology.service import OntologyServiceImpl


class TestCheckImmutableFields:
    """Tests for the check_immutable_fields validator function."""

    def test_allows_mutable_fields(self) -> None:
        """Updating display_name and description should succeed."""
        check_immutable_fields(
            "ObjectType",
            {"display_name": "New Name", "description": "Updated desc"},
        )

    def test_rejects_rid_modification(self) -> None:
        """Attempting to change rid should raise ONTOLOGY_IMMUTABLE_FIELD."""
        with pytest.raises(AppError) as exc_info:
            check_immutable_fields("ObjectType", {"rid": "ri.obj.new"})
        assert exc_info.value.code == ErrorCode.ONTOLOGY_IMMUTABLE_FIELD
        assert "rid" in exc_info.value.message

    def test_rejects_api_name_modification(self) -> None:
        """Attempting to change api_name should raise ONTOLOGY_IMMUTABLE_FIELD."""
        with pytest.raises(AppError) as exc_info:
            check_immutable_fields("ObjectType", {"api_name": "new_name"})
        assert exc_info.value.code == ErrorCode.ONTOLOGY_IMMUTABLE_FIELD
        assert "api_name" in exc_info.value.message

    def test_rejects_tenant_id_modification(self) -> None:
        """Attempting to change tenant_id should raise ONTOLOGY_IMMUTABLE_FIELD."""
        with pytest.raises(AppError) as exc_info:
            check_immutable_fields("ObjectType", {"tenant_id": "t2"})
        assert exc_info.value.code == ErrorCode.ONTOLOGY_IMMUTABLE_FIELD

    def test_rejects_created_at_modification(self) -> None:
        """Attempting to change created_at should raise ONTOLOGY_IMMUTABLE_FIELD."""
        with pytest.raises(AppError) as exc_info:
            check_immutable_fields("ObjectType", {"created_at": "2026-01-01"})
        assert exc_info.value.code == ErrorCode.ONTOLOGY_IMMUTABLE_FIELD

    def test_rejects_entity_specific_immutable_link_type(self) -> None:
        """LinkType source_object_type_rid should be immutable."""
        with pytest.raises(AppError) as exc_info:
            check_immutable_fields(
                "LinkType", {"source_object_type_rid": "ri.obj.new"}
            )
        assert exc_info.value.code == ErrorCode.ONTOLOGY_IMMUTABLE_FIELD
        assert "source_object_type_rid" in exc_info.value.message

    def test_rejects_entity_specific_immutable_interface_category(self) -> None:
        """InterfaceType category should be immutable."""
        with pytest.raises(AppError) as exc_info:
            check_immutable_fields(
                "InterfaceType", {"category": "LINK_INTERFACE"}
            )
        assert exc_info.value.code == ErrorCode.ONTOLOGY_IMMUTABLE_FIELD

    def test_rejects_entity_specific_immutable_shared_data_type(self) -> None:
        """SharedPropertyType data_type should be immutable."""
        with pytest.raises(AppError) as exc_info:
            check_immutable_fields(
                "SharedPropertyType", {"data_type": "DT_INTEGER"}
            )
        assert exc_info.value.code == ErrorCode.ONTOLOGY_IMMUTABLE_FIELD

    def test_error_details_contain_field_list(self) -> None:
        """Error details should include the violated fields."""
        with pytest.raises(AppError) as exc_info:
            check_immutable_fields(
                "ObjectType",
                {"rid": "ri.obj.x", "api_name": "bad", "display_name": "ok"},
            )
        details = exc_info.value.details
        assert "fields" in details
        assert "api_name" in details["fields"]
        assert "rid" in details["fields"]
        assert "display_name" not in details["fields"]

    def test_empty_updates_allowed(self) -> None:
        """Empty update dict should not raise."""
        check_immutable_fields("ObjectType", {})

    def test_unknown_entity_type_uses_common_immutables_only(self) -> None:
        """Unknown entity type should only check common immutable fields."""
        # Should succeed — no entity-specific immutable fields for unknown
        check_immutable_fields("UnknownType", {"data_type": "DT_STRING"})
        # Should fail — common immutable
        with pytest.raises(AppError):
            check_immutable_fields("UnknownType", {"rid": "ri.x.1"})


class TestImmutableFieldIntegration:
    """Test immutable field check integration in OntologyServiceImpl._update_entity."""

    @pytest.fixture
    def mock_graph(self) -> AsyncMock:
        return AsyncMock()

    @pytest.fixture
    def mock_redis(self) -> AsyncMock:
        redis = AsyncMock()
        redis.get = AsyncMock(return_value=b"user1")
        return redis

    @pytest.fixture
    def service(self, mock_graph: AsyncMock, mock_redis: AsyncMock) -> OntologyServiceImpl:
        return OntologyServiceImpl(graph_repo=mock_graph, redis=mock_redis)

    @pytest.mark.asyncio
    async def test_update_entity_rejects_immutable_field(
        self, service: OntologyServiceImpl, mock_graph: AsyncMock,
    ) -> None:
        """_update_entity should reject immutable fields before touching Neo4j."""
        with (
            patch("lingshu.ontology.service.get_user_id", return_value="user1"),
            patch("lingshu.ontology.service.get_tenant_id", return_value="t1"),
        ):
            with pytest.raises(AppError) as exc_info:
                await service._update_entity(
                    "ObjectType", "ri.obj.1", {"api_name": "changed"}
                )
            assert exc_info.value.code == ErrorCode.ONTOLOGY_IMMUTABLE_FIELD
            # Should not have called get_draft_node (stopped before)
            mock_graph.get_draft_node.assert_not_called()
