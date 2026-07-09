"""Tests for PolicyDecision validation and defaults."""

import pytest
from pydantic import ValidationError

from resultarai.core.policy import PolicyDecision


def test_policy_decision_defaults() -> None:
    """Verify default values and flags for a valid PolicyDecision."""
    decision = PolicyDecision(
        effect="allow",
        reason="User is authorized",
        applied_policy="policy_1",
    )
    assert decision.effect == "allow"
    assert decision.reason == "User is authorized"
    assert decision.applied_policy == "policy_1"
    assert decision.limits is None
    assert decision.requires_approver_comment is False
    assert decision.requires_second_approval is False


def test_policy_decision_invalid_effect() -> None:
    """Verify that an effect outside the allowed Literal causes a ValidationError."""
    with pytest.raises(ValidationError):
        PolicyDecision(
            effect="something_else",  # type: ignore
            reason="Invalid effect type",
            applied_policy="policy_1",
        )
