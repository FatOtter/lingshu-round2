"""Unit tests for safety enforcer."""

import pytest

from lingshu.function.safety.enforcer import SafetyEnforcer


@pytest.fixture
def enforcer() -> SafetyEnforcer:
    return SafetyEnforcer()


class TestSafetyEnforcer:
    def test_read_only_direct_execute(self, enforcer: SafetyEnforcer) -> None:
        decision = enforcer.check("SAFETY_READ_ONLY", [], [])
        assert not decision.requires_confirmation

    def test_idempotent_write_direct_execute(self, enforcer: SafetyEnforcer) -> None:
        decision = enforcer.check("SAFETY_IDEMPOTENT_WRITE", [], [])
        assert not decision.requires_confirmation

    def test_non_idempotent_requires_confirmation(
        self, enforcer: SafetyEnforcer,
    ) -> None:
        outputs = [
            {"name": "update", "target_param": "robot", "operation": "update", "writeback": True},
        ]
        side_effects = [{"category": "DATA_MUTATION"}]
        decision = enforcer.check("SAFETY_NON_IDEMPOTENT", outputs, side_effects)
        assert decision.requires_confirmation
        assert len(decision.affected_outputs) == 1
        assert decision.side_effects == side_effects

    def test_critical_requires_confirmation(self, enforcer: SafetyEnforcer) -> None:
        decision = enforcer.check("SAFETY_CRITICAL", [], [])
        assert decision.requires_confirmation
        assert decision.message is not None

    def test_skip_confirmation_overrides(self, enforcer: SafetyEnforcer) -> None:
        decision = enforcer.check(
            "SAFETY_CRITICAL", [], [],
            skip_confirmation=True,
        )
        assert not decision.requires_confirmation

    def test_non_writeback_outputs_excluded(self, enforcer: SafetyEnforcer) -> None:
        outputs = [
            {"name": "read", "writeback": False},
            {"name": "write", "writeback": True, "target_param": "x", "operation": "update"},
        ]
        decision = enforcer.check("SAFETY_NON_IDEMPOTENT", outputs, [])
        assert len(decision.affected_outputs) == 1
        assert decision.affected_outputs[0]["name"] == "write"
