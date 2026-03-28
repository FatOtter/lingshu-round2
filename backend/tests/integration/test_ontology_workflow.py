"""Integration tests for ontology lifecycle workflows across service layers."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lingshu.infra.errors import AppError, ErrorCode
from lingshu.ontology.service import OntologyServiceImpl


# ── Helpers ───────────────────────────────────────────────────────


def _make_node(
    rid: str,
    label: str = "ObjectType",
    api_name: str = "robot",
    is_draft: bool = True,
    is_staging: bool = False,
    is_active: bool = True,
    **extra: Any,
) -> dict[str, Any]:
    now = datetime.utcnow().isoformat()
    return {
        "rid": rid,
        "tenant_id": "t1",
        "api_name": api_name,
        "display_name": api_name.replace("_", " ").title(),
        "description": f"A {api_name}",
        "lifecycle_status": "active",
        "is_draft": is_draft,
        "is_staging": is_staging,
        "is_active": is_active,
        "snapshot_id": None,
        "parent_snapshot_id": None,
        "draft_owner": "u1",
        "created_at": now,
        "updated_at": now,
        "_label": label,
        **extra,
    }


def _build_service() -> tuple[OntologyServiceImpl, AsyncMock, AsyncMock]:
    graph = AsyncMock()
    redis = AsyncMock()
    service = OntologyServiceImpl(graph_repo=graph, redis=redis)
    return service, graph, redis


# ── Tests ─────────────────────────────────────────────────────────


class TestCreateObjectTypeAddPropertiesSubmitActivate:
    """Create ObjectType -> add properties -> submit to staging -> commit."""

    async def test_full_lifecycle(self) -> None:
        service, graph, redis = _build_service()
        obj_node = _make_node("ri.obj.1", "ObjectType", "robot")
        prop_node = _make_node("ri.prop.1", "PropertyType", "name")
        staging_node = {**obj_node, "is_draft": False, "is_staging": True}

        graph.check_api_name_unique = AsyncMock(return_value=True)
        graph.create_node = AsyncMock(return_value=obj_node)
        graph.create_relationship = AsyncMock()

        with (
            patch("lingshu.ontology.service.get_tenant_id", return_value="t1"),
            patch("lingshu.ontology.service.get_user_id", return_value="u1"),
            patch("lingshu.ontology.service.generate_rid", side_effect=["ri.obj.1", "ri.prop.1"]),
        ):
            # Step 1: Create ObjectType
            result = await service.create_object_type({"api_name": "robot", "display_name": "Robot"})
            assert result.rid == "ri.obj.1"

            # Step 2: Add property (lock required)
            redis.get = AsyncMock(return_value=b"u1")
            graph.create_node = AsyncMock(return_value=prop_node)
            prop = await service.create_property_type(
                "ri.obj.1", "ObjectType",
                {"api_name": "name", "display_name": "Name", "base_type": "string"},
            )
            assert prop.rid == "ri.prop.1"
            graph.create_relationship.assert_awaited()

            # Step 3: Submit draft to staging
            graph.get_draft_node = AsyncMock(return_value=obj_node)
            graph.update_node = AsyncMock(return_value=staging_node)
            redis.delete = AsyncMock()
            staged = await service.submit_to_staging("ObjectType", "ri.obj.1")
            assert staged.version_status == "staging"


class TestCreateInterfaceImplementInObjectType:
    """Create InterfaceType -> create ObjectType implementing it."""

    async def test_interface_inheritance(self) -> None:
        service, graph, redis = _build_service()
        iface_node = _make_node("ri.iface.1", "InterfaceType", "trackable")
        obj_node = _make_node(
            "ri.obj.2", "ObjectType", "robot",
            implements_interface_type_rids=["ri.iface.1"],
        )

        graph.check_api_name_unique = AsyncMock(return_value=True)
        graph.create_node = AsyncMock(side_effect=[iface_node, obj_node])

        with (
            patch("lingshu.ontology.service.get_tenant_id", return_value="t1"),
            patch("lingshu.ontology.service.get_user_id", return_value="u1"),
            patch("lingshu.ontology.service.generate_rid", side_effect=["ri.iface.1", "ri.obj.2"]),
        ):
            iface = await service.create_interface_type({
                "api_name": "trackable", "display_name": "Trackable",
            })
            assert iface.rid == "ri.iface.1"

            obj = await service.create_object_type({
                "api_name": "robot",
                "display_name": "Robot",
                "implements_interface_type_rids": ["ri.iface.1"],
            })
            assert obj.rid == "ri.obj.2"


class TestCreateObjectTypeLinkTypeCascade:
    """Create ObjectType -> create LinkType between objects."""

    async def test_link_between_objects(self) -> None:
        service, graph, redis = _build_service()
        obj_a = _make_node("ri.obj.a", "ObjectType", "person")
        obj_b = _make_node("ri.obj.b", "ObjectType", "company")
        link = _make_node(
            "ri.link.1", "LinkType", "works_at",
            source_object_type_rid="ri.obj.a",
            target_object_type_rid="ri.obj.b",
        )

        graph.check_api_name_unique = AsyncMock(return_value=True)
        graph.create_node = AsyncMock(side_effect=[obj_a, obj_b, link])

        with (
            patch("lingshu.ontology.service.get_tenant_id", return_value="t1"),
            patch("lingshu.ontology.service.get_user_id", return_value="u1"),
            patch("lingshu.ontology.service.generate_rid", side_effect=["ri.obj.a", "ri.obj.b", "ri.link.1"]),
        ):
            a = await service.create_object_type({"api_name": "person", "display_name": "Person"})
            b = await service.create_object_type({"api_name": "company", "display_name": "Company"})
            lnk = await service.create_link_type({
                "api_name": "works_at",
                "display_name": "Works At",
                "source_object_type_rid": "ri.obj.a",
                "target_object_type_rid": "ri.obj.b",
            })
            assert a.rid == "ri.obj.a"
            assert b.rid == "ri.obj.b"
            assert lnk.rid == "ri.link.1"


class TestDeleteWithDependencyCheck:
    """Delete entity with existing dependencies should fail."""

    async def test_delete_dependency_error(self) -> None:
        service, graph, redis = _build_service()

        with (
            patch("lingshu.ontology.service.get_tenant_id", return_value="t1"),
            patch("lingshu.ontology.service.get_user_id", return_value="u1"),
            patch(
                "lingshu.ontology.service.check_delete_dependencies",
                side_effect=AppError(
                    code=ErrorCode.ONTOLOGY_DEPENDENCY_CONFLICT,
                    message="Entity has dependents",
                ),
            ),
        ):
            with pytest.raises(AppError) as exc_info:
                await service.delete_object_type("ri.obj.1")
            assert exc_info.value.code == ErrorCode.ONTOLOGY_DEPENDENCY_CONFLICT


class TestDuplicateApiName:
    """Creating entity with duplicate api_name should fail."""

    async def test_duplicate_api_name(self) -> None:
        service, graph, redis = _build_service()
        graph.check_api_name_unique = AsyncMock(return_value=False)

        with (
            patch("lingshu.ontology.service.get_tenant_id", return_value="t1"),
            patch("lingshu.ontology.service.get_user_id", return_value="u1"),
        ):
            with pytest.raises(AppError) as exc_info:
                await service.create_object_type({"api_name": "robot", "display_name": "Robot"})
            assert exc_info.value.code == ErrorCode.ONTOLOGY_DUPLICATE_API_NAME


class TestLockRequiredForUpdate:
    """Update without a lock should fail."""

    async def test_update_without_lock(self) -> None:
        service, graph, redis = _build_service()
        redis.get = AsyncMock(return_value=None)

        with (
            patch("lingshu.ontology.service.get_tenant_id", return_value="t1"),
            patch("lingshu.ontology.service.get_user_id", return_value="u1"),
        ):
            with pytest.raises(AppError) as exc_info:
                await service.update_object_type("ri.obj.1", {"display_name": "New"})
            assert exc_info.value.code == ErrorCode.ONTOLOGY_LOCK_REQUIRED


class TestSubmitDraftNotFound:
    """Submit non-existent draft should fail."""

    async def test_submit_missing_draft(self) -> None:
        service, graph, redis = _build_service()
        graph.get_draft_node = AsyncMock(return_value=None)

        with (
            patch("lingshu.ontology.service.get_tenant_id", return_value="t1"),
            patch("lingshu.ontology.service.get_user_id", return_value="u1"),
        ):
            with pytest.raises(AppError) as exc_info:
                await service.submit_to_staging("ObjectType", "ri.obj.missing")
            assert exc_info.value.code == ErrorCode.ONTOLOGY_DRAFT_NOT_FOUND


class TestCommitStagingEmpty:
    """Commit with empty staging should fail."""

    async def test_commit_empty_staging(self) -> None:
        service, graph, redis = _build_service()
        session = AsyncMock()

        redis.set = AsyncMock(return_value=True)
        redis.delete = AsyncMock()
        graph.get_staging_nodes = AsyncMock(return_value=[])

        with (
            patch("lingshu.ontology.service.get_tenant_id", return_value="t1"),
            patch("lingshu.ontology.service.get_user_id", return_value="u1"),
        ):
            with pytest.raises(AppError) as exc_info:
                await service.commit_staging("test commit", session)
            assert exc_info.value.code == ErrorCode.ONTOLOGY_STAGING_EMPTY
