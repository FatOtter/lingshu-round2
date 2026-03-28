"""BS-18: Chart Data Pipeline scenario tests.

Tests A2UI chart event building, multiple series, chart type variants,
and empty series graceful handling.
"""

from __future__ import annotations

import pytest

from lingshu.copilot.a2ui.components import chart_component
from lingshu.copilot.a2ui.protocol import A2UIEvent, component


class TestBS18ChartData:
    """Chart Data Pipeline: build chart events, verify structure."""

    async def test_step1_a2ui_chart_event_format(self) -> None:
        """Build A2UIChart event, verify structure."""
        chart = chart_component(
            chart_type="bar",
            title="Sales by Region",
            x_axis={"label": "Region", "type": "category"},
            y_axis={"label": "Revenue ($)", "type": "value"},
            series=[
                {
                    "name": "Q1 2026",
                    "data_points": [
                        {"x": "North", "y": 120000},
                        {"x": "South", "y": 95000},
                        {"x": "East", "y": 110000},
                    ],
                },
            ],
        )

        assert chart["type"] == "chart"
        assert chart["chart_type"] == "bar"
        assert chart["title"] == "Sales by Region"
        assert chart["x_axis"]["label"] == "Region"
        assert chart["y_axis"]["label"] == "Revenue ($)"
        assert len(chart["series"]) == 1
        assert chart["series"][0]["name"] == "Q1 2026"
        assert len(chart["series"][0]["data_points"]) == 3

    async def test_step2_chart_with_multiple_series(self) -> None:
        """Multiple series with data_points."""
        chart = chart_component(
            chart_type="line",
            title="Monthly Trend",
            x_axis={"label": "Month", "type": "category"},
            y_axis={"label": "Count", "type": "value"},
            series=[
                {
                    "name": "2025",
                    "data_points": [
                        {"x": "Jan", "y": 100},
                        {"x": "Feb", "y": 120},
                        {"x": "Mar", "y": 110},
                    ],
                },
                {
                    "name": "2026",
                    "data_points": [
                        {"x": "Jan", "y": 130},
                        {"x": "Feb", "y": 140},
                        {"x": "Mar", "y": 150},
                    ],
                },
            ],
        )

        assert len(chart["series"]) == 2
        assert chart["series"][0]["name"] == "2025"
        assert chart["series"][1]["name"] == "2026"
        assert chart["series"][1]["data_points"][2]["y"] == 150

    async def test_step3_chart_type_variants(self) -> None:
        """Verify bar, line, pie, area chart types all produce valid structures."""
        for chart_type in ("bar", "line", "pie", "area"):
            chart = chart_component(
                chart_type=chart_type,
                title=f"{chart_type.capitalize()} Chart",
                x_axis={"label": "X"},
                y_axis={"label": "Y"},
                series=[{"name": "s1", "data_points": [{"x": "a", "y": 1}]}],
            )

            assert chart["type"] == "chart"
            assert chart["chart_type"] == chart_type
            assert chart["title"] == f"{chart_type.capitalize()} Chart"
            assert len(chart["series"]) == 1

    async def test_step4_empty_series(self) -> None:
        """Empty series array — verify graceful handling."""
        chart = chart_component(
            chart_type="bar",
            title="Empty Chart",
            x_axis={"label": "X"},
            y_axis={"label": "Y"},
            series=[],
        )

        assert chart["type"] == "chart"
        assert chart["series"] == []
        assert chart["title"] == "Empty Chart"

        # Wrap in A2UI event
        event = component(chart)
        assert event.event_type == "component"
        assert event.data["component"]["type"] == "chart"
        assert event.data["component"]["series"] == []

        # Verify SSE serialization works
        sse_str = event.to_sse()
        assert "event: a2ui" in sse_str
        assert '"type": "chart"' in sse_str
