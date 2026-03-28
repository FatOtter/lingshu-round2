"""Unit tests for data masking pipeline."""

from lingshu.data.pipeline.masking import apply_masking, build_masking_rules, mask_value


class TestMaskValue:
    def test_none_input(self) -> None:
        assert mask_value(None, "MASK_REDACT_FULL") is None

    def test_mask_none(self) -> None:
        assert mask_value("secret", "MASK_NONE") == "secret"

    def test_mask_nullify(self) -> None:
        assert mask_value("secret", "MASK_NULLIFY") is None

    def test_mask_redact_full(self) -> None:
        assert mask_value("secret", "MASK_REDACT_FULL") == "***"

    def test_show_last_4(self) -> None:
        assert mask_value("1234567890", "SHOW_LAST_4") == "***7890"

    def test_show_last_4_short(self) -> None:
        assert mask_value("12", "SHOW_LAST_4") == "***"

    def test_mask_phone_middle(self) -> None:
        assert mask_value("13812345678", "MASK_PHONE_MIDDLE") == "138****5678"

    def test_mask_phone_short(self) -> None:
        assert mask_value("123", "MASK_PHONE_MIDDLE") == "***"


class TestApplyMasking:
    def test_masks_specified_fields(self) -> None:
        rows = [{"name": "Alice", "ssn": "123-45-6789"}]
        rules = {"ssn": "MASK_REDACT_FULL"}
        result = apply_masking(rows, rules)
        assert result[0]["name"] == "Alice"
        assert result[0]["ssn"] == "***"

    def test_empty_rules(self) -> None:
        rows = [{"name": "Alice"}]
        result = apply_masking(rows, {})
        assert result == rows

    def test_multiple_rows(self) -> None:
        rows = [{"phone": "13812345678"}, {"phone": "13900001111"}]
        rules = {"phone": "MASK_PHONE_MIDDLE"}
        result = apply_masking(rows, rules)
        assert result[0]["phone"] == "138****5678"
        assert result[1]["phone"] == "139****1111"


class TestBuildMaskingRules:
    def test_builds_rules_from_compliance(self) -> None:
        props = [
            {
                "api_name": "ssn",
                "compliance": {
                    "sensitivity": "CONFIDENTIAL",
                    "masking_strategy": "MASK_REDACT_FULL",
                },
            },
            {
                "api_name": "name",
                "compliance": {
                    "sensitivity": "PUBLIC",
                    "masking_strategy": "MASK_NONE",
                },
            },
        ]
        rules = build_masking_rules(props)
        assert rules == {"ssn": "MASK_REDACT_FULL"}
        assert "name" not in rules

    def test_no_compliance(self) -> None:
        props = [{"api_name": "field1"}]
        rules = build_masking_rules(props)
        assert rules == {}
