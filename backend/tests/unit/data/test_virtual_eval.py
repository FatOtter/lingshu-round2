"""Unit tests for virtual expression evaluator."""

import pytest

from lingshu.data.pipeline.virtual_eval import apply_virtual_fields, evaluate_expression


class TestEvaluateExpression:
    def test_simple_addition(self) -> None:
        result = evaluate_expression("a + b", {"a": 10, "b": 5})
        assert result == 15

    def test_multiplication(self) -> None:
        result = evaluate_expression("price * quantity", {"price": 9.99, "quantity": 3})
        assert result == pytest.approx(29.97)

    def test_division(self) -> None:
        result = evaluate_expression("total / count", {"total": 100, "count": 4})
        assert result == 25.0

    def test_constant(self) -> None:
        result = evaluate_expression("42", {})
        assert result == 42

    def test_missing_field_returns_none(self) -> None:
        result = evaluate_expression("a + b", {"a": 10})
        assert result is None

    def test_complex_expression(self) -> None:
        result = evaluate_expression("a * b + c", {"a": 2, "b": 3, "c": 4})
        assert result == 10

    def test_negative_value(self) -> None:
        result = evaluate_expression("-a", {"a": 5})
        assert result == -5

    def test_invalid_expression_returns_none(self) -> None:
        result = evaluate_expression("!!!invalid", {})
        assert result is None


class TestBuiltinFunctions:
    def test_concat(self) -> None:
        result = evaluate_expression("CONCAT(first, last)", {"first": "John", "last": "Doe"})
        assert result == "JohnDoe"

    def test_abs(self) -> None:
        result = evaluate_expression("ABS(value)", {"value": -42})
        assert result == 42

    def test_round(self) -> None:
        result = evaluate_expression("ROUND(value, 2)", {"value": 3.14159})
        assert result == 3.14


class TestApplyVirtualFields:
    def test_adds_virtual_field(self) -> None:
        rows = [{"a": 10, "b": 5}]
        result = apply_virtual_fields(rows, {"total": "a + b"})
        assert result[0]["total"] == 15

    def test_empty_virtual_fields(self) -> None:
        rows = [{"a": 1}]
        result = apply_virtual_fields(rows, {})
        assert result == rows

    def test_multiple_rows(self) -> None:
        rows = [{"x": 1}, {"x": 2}, {"x": 3}]
        result = apply_virtual_fields(rows, {"doubled": "x * 2"})
        assert [r["doubled"] for r in result] == [2, 4, 6]
