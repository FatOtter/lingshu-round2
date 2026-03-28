"""Safety enforcer: determine execution strategy based on safety_level."""

from typing import Any

# Safety levels that allow direct execution without confirmation
DIRECT_EXECUTE_LEVELS = frozenset({"SAFETY_READ_ONLY", "SAFETY_IDEMPOTENT_WRITE"})

# Safety levels that require confirmation
CONFIRMATION_LEVELS = frozenset({"SAFETY_NON_IDEMPOTENT", "SAFETY_CRITICAL"})


class SafetyDecision:
    """Result of safety check."""

    def __init__(
        self,
        requires_confirmation: bool,
        message: str | None = None,
        affected_outputs: list[dict[str, Any]] | None = None,
        side_effects: list[dict[str, Any]] | None = None,
    ) -> None:
        self.requires_confirmation = requires_confirmation
        self.message = message
        self.affected_outputs = affected_outputs or []
        self.side_effects = side_effects or []


class SafetyEnforcer:
    """Evaluate safety level and determine execution strategy."""

    def check(
        self,
        safety_level: str,
        outputs: list[dict[str, Any]],
        side_effects: list[dict[str, Any]],
        *,
        skip_confirmation: bool = False,
    ) -> SafetyDecision:
        """Check if execution requires confirmation.

        Args:
            safety_level: One of SAFETY_* levels.
            outputs: Action output declarations.
            side_effects: Side effect declarations.
            skip_confirmation: If True, skip confirmation (used by Copilot).

        Returns:
            SafetyDecision indicating whether confirmation is needed.
        """
        if skip_confirmation:
            return SafetyDecision(requires_confirmation=False)

        if safety_level in DIRECT_EXECUTE_LEVELS:
            return SafetyDecision(requires_confirmation=False)

        # Build affected outputs summary for confirmation dialog
        affected = [
            {
                "name": o.get("name", ""),
                "target_param": o.get("target_param", ""),
                "operation": o.get("operation", ""),
                "writeback": o.get("writeback", False),
            }
            for o in outputs
            if o.get("writeback", False)
        ]

        message = None
        if safety_level == "SAFETY_CRITICAL":
            message = "This is a critical operation that cannot be undone"
        elif safety_level == "SAFETY_NON_IDEMPOTENT":
            message = "This operation may have irreversible effects"

        return SafetyDecision(
            requires_confirmation=True,
            message=message,
            affected_outputs=affected,
            side_effects=side_effects,
        )
