"""BS-01: Smart City Traffic Management System Modeling.

Scenario: A data architect builds a complete traffic management ontology model.

Steps:
1. Create SharedPropertyType "geo_coordinate" and "status_code"
2. Create InterfaceType "locatable_device" with required properties
3. Create ObjectType "traffic_light" implementing the interface
4. Create ObjectType "camera" implementing the interface
5. Create LinkType "monitoring_range" connecting camera -> traffic_light
6. Create ActionType "restart_device" operating on traffic_light
7. Submit all to staging
8. Publish (commit_staging)
9. Verify all entities are Active
10. Verify dependency detection: deleting InterfaceType is blocked
11. Verify immutable fields: api_name cannot change after publish
"""

from __future__ import annotations

from datetime import datetime
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from lingshu.infra.errors import AppError, ErrorCode
from lingshu.ontology.service import OntologyServiceImpl

from .conftest import (
    make_action_type_node,
    make_active_node,
    make_interface_type_node,
    make_link_type_node,
    make_object_type_node,
    make_property_type_node,
    make_shared_property_type_node,
    make_staging_node,
    mock_session,
)


def _build_service() -> tuple[OntologyServiceImpl, AsyncMock, AsyncMock]:
    graph = AsyncMock()
    redis = AsyncMock()
    service = OntologyServiceImpl(graph_repo=graph, redis=redis)
    return service, graph, redis


class TestTrafficManagementModeling:
    """Complete traffic management system ontology modeling scenario."""

    @pytest.fixture
    def service_stack(self):
        return _build_service()

    @pytest.fixture
    def ctx_patches(self, tenant_id, admin_user_id):
        return {
            "tenant_id": patch(
                "lingshu.ontology.service.get_tenant_id",
                return_value=tenant_id,
            ),
            "user_id": patch(
                "lingshu.ontology.service.get_user_id",
                return_value=admin_user_id,
            ),
        }

    async def test_step1_create_shared_property_types(
        self, service_stack, ctx_patches, tenant_id,
    ) -> None:
        """Step 1: Create SharedPropertyType 'geo_coordinate' and 'status_code'."""
        service, graph, redis = service_stack

        geo_node = make_shared_property_type_node(
            "ri.shprop.geo", "geo_coordinate",
            display_name="Geo Coordinate",
            tenant_id=tenant_id,
        )
        status_node = make_shared_property_type_node(
            "ri.shprop.status", "status_code",
            display_name="Status Code",
            tenant_id=tenant_id,
        )

        graph.check_api_name_unique = AsyncMock(return_value=True)
        graph.create_node = AsyncMock(side_effect=[geo_node, status_node])

        with ctx_patches["tenant_id"], ctx_patches["user_id"]:
            with patch(
                "lingshu.ontology.service.generate_rid",
                side_effect=["ri.shprop.geo", "ri.shprop.status"],
            ):
                geo = await service.create_shared_property_type(
                    {"api_name": "geo_coordinate", "display_name": "Geo Coordinate"},
                )
                assert geo.rid == "ri.shprop.geo"
                assert geo.api_name == "geo_coordinate"

                status = await service.create_shared_property_type(
                    {"api_name": "status_code", "display_name": "Status Code"},
                )
                assert status.rid == "ri.shprop.status"

    async def test_step2_create_interface_type(
        self, service_stack, ctx_patches, tenant_id,
    ) -> None:
        """Step 2: Create InterfaceType 'locatable_device' with required properties."""
        service, graph, redis = service_stack

        iface_node = make_interface_type_node(
            "ri.iface.locatable", "locatable_device",
            display_name="Locatable Device",
            required_shared_property_type_rids=["ri.shprop.geo"],
            tenant_id=tenant_id,
        )
        graph.check_api_name_unique = AsyncMock(return_value=True)
        graph.create_node = AsyncMock(return_value=iface_node)

        with ctx_patches["tenant_id"], ctx_patches["user_id"]:
            with patch(
                "lingshu.ontology.service.generate_rid",
                return_value="ri.iface.locatable",
            ):
                iface = await service.create_interface_type({
                    "api_name": "locatable_device",
                    "display_name": "Locatable Device",
                    "required_shared_property_type_rids": ["ri.shprop.geo"],
                })
                assert iface.rid == "ri.iface.locatable"

    async def test_step3_create_traffic_light_with_interface(
        self, service_stack, ctx_patches, tenant_id,
    ) -> None:
        """Step 3: Create ObjectType 'traffic_light' implementing locatable_device."""
        service, graph, redis = service_stack

        obj_node = make_object_type_node(
            "ri.obj.traffic_light", "traffic_light",
            display_name="Traffic Light",
            implements_interface_type_rids=["ri.iface.locatable"],
            tenant_id=tenant_id,
        )
        graph.check_api_name_unique = AsyncMock(return_value=True)
        graph.create_node = AsyncMock(return_value=obj_node)

        with ctx_patches["tenant_id"], ctx_patches["user_id"]:
            with patch(
                "lingshu.ontology.service.generate_rid",
                return_value="ri.obj.traffic_light",
            ):
                obj = await service.create_object_type({
                    "api_name": "traffic_light",
                    "display_name": "Traffic Light",
                    "implements_interface_type_rids": ["ri.iface.locatable"],
                })
                assert obj.rid == "ri.obj.traffic_light"

    async def test_step4_create_camera_with_interface(
        self, service_stack, ctx_patches, tenant_id,
    ) -> None:
        """Step 4: Create ObjectType 'camera' implementing locatable_device."""
        service, graph, redis = service_stack

        obj_node = make_object_type_node(
            "ri.obj.camera", "camera",
            display_name="Camera",
            implements_interface_type_rids=["ri.iface.locatable"],
            tenant_id=tenant_id,
        )
        graph.check_api_name_unique = AsyncMock(return_value=True)
        graph.create_node = AsyncMock(return_value=obj_node)

        with ctx_patches["tenant_id"], ctx_patches["user_id"]:
            with patch(
                "lingshu.ontology.service.generate_rid",
                return_value="ri.obj.camera",
            ):
                obj = await service.create_object_type({
                    "api_name": "camera",
                    "display_name": "Camera",
                    "implements_interface_type_rids": ["ri.iface.locatable"],
                })
                assert obj.rid == "ri.obj.camera"

    async def test_step5_create_link_type(
        self, service_stack, ctx_patches, tenant_id,
    ) -> None:
        """Step 5: Create LinkType 'monitoring_range' from camera to traffic_light."""
        service, graph, redis = service_stack

        link_node = make_link_type_node(
            "ri.link.monitoring", "monitoring_range",
            display_name="Monitoring Range",
            source_object_type_rid="ri.obj.camera",
            target_object_type_rid="ri.obj.traffic_light",
            tenant_id=tenant_id,
        )
        graph.check_api_name_unique = AsyncMock(return_value=True)
        graph.create_node = AsyncMock(return_value=link_node)

        with ctx_patches["tenant_id"], ctx_patches["user_id"]:
            with patch(
                "lingshu.ontology.service.generate_rid",
                return_value="ri.link.monitoring",
            ):
                link = await service.create_link_type({
                    "api_name": "monitoring_range",
                    "display_name": "Monitoring Range",
                    "source_object_type_rid": "ri.obj.camera",
                    "target_object_type_rid": "ri.obj.traffic_light",
                })
                assert link.rid == "ri.link.monitoring"

    async def test_step6_create_action_type(
        self, service_stack, ctx_patches, tenant_id,
    ) -> None:
        """Step 6: Create ActionType 'restart_device' on traffic_light."""
        service, graph, redis = service_stack

        import json

        action_node = make_action_type_node(
            "ri.action.restart", "restart_device",
            display_name="Restart Device",
            safety_level="SAFETY_NON_IDEMPOTENT",
            parameters=json.dumps([
                {"api_name": "device_rid", "required": True},
                {"api_name": "reason", "required": True},
            ]),
            execution=json.dumps({"type": "native_crud"}),
            tenant_id=tenant_id,
        )
        graph.check_api_name_unique = AsyncMock(return_value=True)
        graph.create_node = AsyncMock(return_value=action_node)

        with ctx_patches["tenant_id"], ctx_patches["user_id"]:
            with patch(
                "lingshu.ontology.service.generate_rid",
                return_value="ri.action.restart",
            ):
                action = await service.create_action_type({
                    "api_name": "restart_device",
                    "display_name": "Restart Device",
                    "safety_level": "SAFETY_NON_IDEMPOTENT",
                    "parameters": [
                        {"api_name": "device_rid", "required": True},
                        {"api_name": "reason", "required": True},
                    ],
                })
                assert action.rid == "ri.action.restart"

    async def test_step7_submit_to_staging(
        self, service_stack, ctx_patches, tenant_id,
    ) -> None:
        """Step 7: Submit all entities to staging."""
        service, graph, redis = service_stack

        obj_draft = make_object_type_node(
            "ri.obj.traffic_light", "traffic_light", tenant_id=tenant_id,
        )
        obj_staging = make_staging_node(obj_draft)

        graph.get_draft_node = AsyncMock(return_value=obj_draft)
        graph.update_node = AsyncMock(return_value=obj_staging)
        redis.delete = AsyncMock()

        with ctx_patches["tenant_id"], ctx_patches["user_id"]:
            result = await service.submit_to_staging(
                "ObjectType", "ri.obj.traffic_light",
            )
            assert result.version_status == "staging"
            redis.delete.assert_awaited()

    async def test_step8_publish_commit_staging(
        self, service_stack, ctx_patches, tenant_id, admin_user_id,
    ) -> None:
        """Step 8: Publish all staging entities (commit_staging)."""
        service, graph, redis = service_stack
        session = mock_session()

        staging_nodes = [
            make_staging_node(
                make_object_type_node(
                    "ri.obj.traffic_light", "traffic_light", tenant_id=tenant_id,
                ),
            ),
            make_staging_node(
                make_object_type_node(
                    "ri.obj.camera", "camera", tenant_id=tenant_id,
                ),
            ),
        ]

        redis.set = AsyncMock(return_value=True)
        redis.delete = AsyncMock()
        redis.scan = AsyncMock(return_value=(0, []))
        redis.publish = AsyncMock()
        graph.get_staging_nodes = AsyncMock(return_value=staging_nodes)
        graph.get_active_node = AsyncMock(return_value=None)
        graph.promote_staging_to_active = AsyncMock()

        with ctx_patches["tenant_id"], ctx_patches["user_id"]:
            with patch(
                "lingshu.ontology.service.generate_rid",
                return_value="ri.snap.v1",
            ):
                with patch(
                    "lingshu.ontology.service.SnapshotRepository",
                ) as MockSnapRepo:
                    MockSnapRepo.return_value.get_active_pointer = AsyncMock(
                        return_value=None,
                    )
                    MockSnapRepo.return_value.create = AsyncMock()
                    MockSnapRepo.return_value.set_active_pointer = AsyncMock()

                    snap = await service.commit_staging("Initial publish", session)
                    assert snap.snapshot_id == "ri.snap.v1"
                    assert "ri.obj.traffic_light" in snap.entity_changes
                    assert snap.entity_changes["ri.obj.traffic_light"] == "create"
                    session.commit.assert_awaited()

    async def test_step9_verify_active_entities(
        self, service_stack, ctx_patches, tenant_id,
    ) -> None:
        """Step 9: Verify all entities are queryable in Active state."""
        service, graph, redis = service_stack

        active_node = make_active_node(
            make_object_type_node(
                "ri.obj.traffic_light", "traffic_light", tenant_id=tenant_id,
            ),
        )
        graph.get_active_node = AsyncMock(return_value=active_node)
        graph.get_related_nodes = AsyncMock(return_value=[])

        with ctx_patches["tenant_id"], ctx_patches["user_id"]:
            result = await service._get_entity("ObjectType", "ri.obj.traffic_light")
            assert result.rid == "ri.obj.traffic_light"
            assert result.version_status == "active"

    async def test_step10_dependency_blocks_delete(
        self, service_stack, ctx_patches,
    ) -> None:
        """Step 10: Deleting InterfaceType is blocked when ObjectTypes implement it."""
        service, graph, redis = service_stack

        with ctx_patches["tenant_id"], ctx_patches["user_id"]:
            with patch(
                "lingshu.ontology.service.check_delete_dependencies",
                side_effect=AppError(
                    code=ErrorCode.ONTOLOGY_DEPENDENCY_CONFLICT,
                    message="InterfaceType has implementing ObjectTypes",
                ),
            ):
                with pytest.raises(AppError) as exc_info:
                    await service.delete_interface_type("ri.iface.locatable")
                assert exc_info.value.code == ErrorCode.ONTOLOGY_DEPENDENCY_CONFLICT

    async def test_step11_immutable_field_after_publish(
        self, service_stack, ctx_patches, tenant_id, admin_user_id,
    ) -> None:
        """Step 11: After publish, api_name cannot be changed."""
        service, graph, redis = service_stack

        redis.get = AsyncMock(return_value=admin_user_id.encode())

        with ctx_patches["tenant_id"], ctx_patches["user_id"]:
            with patch(
                "lingshu.ontology.service.check_immutable_fields",
                side_effect=AppError(
                    code=ErrorCode.ONTOLOGY_IMMUTABLE_FIELD,
                    message="Field 'api_name' is immutable after publish",
                ),
            ):
                with pytest.raises(AppError) as exc_info:
                    await service.update_object_type(
                        "ri.obj.traffic_light",
                        {"api_name": "new_name"},
                    )
                assert exc_info.value.code == ErrorCode.ONTOLOGY_IMMUTABLE_FIELD

    async def test_duplicate_api_name_rejected(
        self, service_stack, ctx_patches,
    ) -> None:
        """Creating entity with duplicate api_name is rejected."""
        service, graph, redis = service_stack
        graph.check_api_name_unique = AsyncMock(return_value=False)

        with ctx_patches["tenant_id"], ctx_patches["user_id"]:
            with pytest.raises(AppError) as exc_info:
                await service.create_object_type(
                    {"api_name": "traffic_light", "display_name": "Traffic Light"},
                )
            assert exc_info.value.code == ErrorCode.ONTOLOGY_DUPLICATE_API_NAME

    async def test_add_property_type_to_object(
        self, service_stack, ctx_patches, tenant_id, admin_user_id,
    ) -> None:
        """Add PropertyType to ObjectType (requires lock)."""
        service, graph, redis = service_stack

        prop_node = make_property_type_node(
            "ri.prop.signal_status", "signal_status",
            base_type="integer",
            tenant_id=tenant_id,
        )

        redis.get = AsyncMock(return_value=admin_user_id.encode())
        graph.get_related_nodes = AsyncMock(return_value=[])
        graph.create_node = AsyncMock(return_value=prop_node)
        graph.create_relationship = AsyncMock()

        with ctx_patches["tenant_id"], ctx_patches["user_id"]:
            with patch(
                "lingshu.ontology.service.generate_rid",
                return_value="ri.prop.signal_status",
            ):
                prop = await service.create_property_type(
                    "ri.obj.traffic_light",
                    "ObjectType",
                    {
                        "api_name": "signal_status",
                        "display_name": "Signal Status",
                        "base_type": "integer",
                    },
                )
                assert prop.rid == "ri.prop.signal_status"
                graph.create_relationship.assert_awaited()
