"""Data masking pipeline: apply compliance rules to query results."""

from typing import Any


def mask_value(value: Any, strategy: str) -> Any:
    """Apply a masking strategy to a single value."""
    if value is None:
        return None

    if strategy == "MASK_NONE":
        return value
    if strategy == "MASK_NULLIFY":
        return None
    if strategy == "MASK_REDACT_FULL":
        return "***"
    if strategy == "SHOW_LAST_4":
        s = str(value)
        if len(s) <= 4:
            return "***"
        return "***" + s[-4:]
    if strategy == "MASK_PHONE_MIDDLE":
        s = str(value)
        if len(s) >= 7:
            return s[:3] + "****" + s[-4:]
        return "***"
    # Default: full redact
    return "***"


def apply_masking(
    rows: list[dict[str, Any]],
    masking_rules: dict[str, str],
) -> list[dict[str, Any]]:
    """Apply masking rules to all rows.

    Args:
        rows: List of row dicts
        masking_rules: Mapping of field_name → masking_strategy
    """
    if not masking_rules:
        return rows

    result = []
    for row in rows:
        masked = dict(row)
        for field, strategy in masking_rules.items():
            if field in masked:
                masked[field] = mask_value(masked[field], strategy)
        result.append(masked)
    return result


def build_masking_rules(
    property_types: list[dict[str, Any]],
) -> dict[str, str]:
    """Extract masking rules from property type compliance configs."""
    rules: dict[str, str] = {}
    for pt in property_types:
        api_name = pt.get("api_name", "")
        compliance = pt.get("compliance")
        if not compliance:
            continue
        sensitivity = compliance.get("sensitivity", "PUBLIC")
        strategy = compliance.get("masking_strategy", "MASK_NONE")
        if sensitivity != "PUBLIC" and strategy != "MASK_NONE":
            rules[api_name] = strategy
    return rules
