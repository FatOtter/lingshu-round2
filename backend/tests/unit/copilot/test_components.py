"""Unit tests for A2UI components."""


from lingshu.copilot.a2ui.components import (
    chart_component,
    confirmation_card_component,
    entity_card_component,
    metric_card_component,
    table_component,
)


class TestTableComponent:
    def test_basic_table(self) -> None:
        comp = table_component(
            "Test Table",
            [{"key": "name", "label": "Name"}],
            [{"name": "Alice"}],
        )
        assert comp["type"] == "table"
        assert comp["title"] == "Test Table"
        assert len(comp["rows"]) == 1

    def test_table_with_object_type_rid(self) -> None:
        comp = table_component(
            "Robots",
            [{"key": "id", "label": "ID"}],
            [{"id": "R2-D2"}],
            object_type_rid="ri.obj.1",
        )
        assert comp["object_type_rid"] == "ri.obj.1"

    def test_table_with_actions(self) -> None:
        comp = table_component(
            "Items",
            [{"key": "id", "label": "ID"}],
            [],
            actions=[{"label": "Delete", "action_rid": "ri.action.1"}],
        )
        assert len(comp["actions"]) == 1


class TestMetricCard:
    def test_basic_metrics(self) -> None:
        comp = metric_card_component([
            {"label": "Total", "value": 42},
            {"label": "Active", "value": 35, "color": "green"},
        ])
        assert comp["type"] == "metric_card"
        assert len(comp["metrics"]) == 2


class TestConfirmationCard:
    def test_confirmation(self) -> None:
        comp = confirmation_card_component(
            "update_status",
            "Update robot status",
            "SAFETY_NON_IDEMPOTENT",
            "This will update 2 robots",
            [{"name": "update", "operation": "update"}],
            [{"category": "DATA_MUTATION"}],
        )
        assert comp["type"] == "confirmation_card"
        assert comp["safety_level"] == "SAFETY_NON_IDEMPOTENT"


class TestEntityCard:
    def test_entity_card(self) -> None:
        comp = entity_card_component(
            "ObjectType", "ri.obj.1", "Robot",
            [{"label": "Status", "value": "ACTIVE"}],
            link="/ontology/object-types/ri.obj.1",
        )
        assert comp["type"] == "entity_card"
        assert comp["link"] == "/ontology/object-types/ri.obj.1"


class TestChart:
    def test_chart(self) -> None:
        comp = chart_component(
            "bar", "Distribution",
            {"label": "Range", "values": ["0-20", "20-50"]},
            {"label": "Count"},
            [{"name": "Count", "values": [5, 12]}],
        )
        assert comp["type"] == "chart"
        assert comp["chart_type"] == "bar"
