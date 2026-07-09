"""Tests for RoutingDecision schema constraints."""

import pytest
from pydantic import ValidationError

from resultarai.core.manifests.routing import RoutingAction
from resultarai.core.routing import RoutingDecision


def test_routing_decision_valid() -> None:
    """Verify that a valid RoutingDecision can be constructed."""
    decision = RoutingDecision(
        action=RoutingAction.ACTIVATE_SKILL,
        target="some_skill",
        reason="Matched intent exactly",
    )
    assert decision.action == RoutingAction.ACTIVATE_SKILL
    assert decision.target == "some_skill"
    assert decision.reason == "Matched intent exactly"


def test_routing_decision_valid_string_action() -> None:
    """Verify that Literal action strings are allowed."""
    decision = RoutingDecision(
        action="answer_directly",
        target=None,
        reason="Answer directly requested",
    )
    assert decision.action == RoutingAction.ANSWER_DIRECTLY
    assert decision.target is None


def test_routing_decision_strict_type_checking() -> None:
    """Verify strict type checking rejects incorrect types under strict=True."""
    # Invalid target type (int instead of str)
    with pytest.raises(ValidationError):
        RoutingDecision(
            action=RoutingAction.ANSWER_DIRECTLY,
            target=123,  # type: ignore
            reason="Invalid target type",
        )

    # Invalid action type
    with pytest.raises(ValidationError):
        RoutingDecision(
            action="invalid_action",  # type: ignore
            target=None,
            reason="Invalid action",
        )


def test_routing_decision_extra_fields_forbidden() -> None:
    """Verify that extra fields are forbidden."""
    with pytest.raises(ValidationError):
        RoutingDecision(
            action=RoutingAction.ANSWER_DIRECTLY,
            target=None,
            reason="No extra fields",
            unexpected_field="not allowed",  # type: ignore
        )


def test_routing_decision_frozen() -> None:
    """Verify that RoutingDecision is frozen (immutable)."""
    decision = RoutingDecision(
        action=RoutingAction.ANSWER_DIRECTLY,
        target=None,
        reason="Read-only test",
    )
    with pytest.raises(ValidationError):
        decision.target = "new_target"  # type: ignore
