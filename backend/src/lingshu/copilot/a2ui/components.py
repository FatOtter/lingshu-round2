"""A2UI component builders for structured UI output."""

from typing import Any


def table_component(
    title: str,
    columns: list[dict[str, str]],
    rows: list[dict[str, Any]],
    *,
    object_type_rid: str | None = None,
    actions: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Build a Table component."""
    comp: dict[str, Any] = {
        "type": "table",
        "title": title,
        "columns": columns,
        "rows": rows,
    }
    if object_type_rid:
        comp["object_type_rid"] = object_type_rid
    if actions:
        comp["actions"] = actions
    return comp


def metric_card_component(
    metrics: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a MetricCard component."""
    return {
        "type": "metric_card",
        "metrics": metrics,
    }


def confirmation_card_component(
    action: str,
    description: str,
    safety_level: str,
    message: str,
    affected_outputs: list[dict[str, Any]],
    side_effects: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a ConfirmationCard component."""
    return {
        "type": "confirmation_card",
        "action": action,
        "description": description,
        "safety_level": safety_level,
        "message": message,
        "affected_outputs": affected_outputs,
        "side_effects": side_effects,
    }


def entity_card_component(
    entity_type: str,
    rid: str,
    display_name: str,
    properties: list[dict[str, Any]],
    *,
    link: str | None = None,
) -> dict[str, Any]:
    """Build an EntityCard component."""
    comp: dict[str, Any] = {
        "type": "entity_card",
        "entity_type": entity_type,
        "rid": rid,
        "display_name": display_name,
        "properties": properties,
    }
    if link:
        comp["link"] = link
    return comp


def chart_component(
    chart_type: str,
    title: str,
    x_axis: dict[str, Any],
    y_axis: dict[str, Any],
    series: list[dict[str, Any]],
) -> dict[str, Any]:
    """Build a Chart component."""
    return {
        "type": "chart",
        "chart_type": chart_type,
        "title": title,
        "x_axis": x_axis,
        "y_axis": y_axis,
        "series": series,
    }
