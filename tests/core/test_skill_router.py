"""Tests for SkillRouter decision logic."""

from resultarai.core.manifests.base import ManifestStatus
from resultarai.core.manifests.routing import RoutingAction, RoutingManifest, RoutingRule
from resultarai.core.routing import decide


class DummyTurn:
    """Mock class representing a Turn object."""

    def __init__(self, intent: str | None) -> None:
        self.intent = intent


def _build_manifest() -> RoutingManifest:
    """Helper to build a routing manifest with active rules."""
    rules = [
        RoutingRule(
            intent="check_balance",
            action=RoutingAction.ACTIVATE_SKILL,
            target="erp_balance_skill",
        ),
        RoutingRule(
            intent="greet",
            action=RoutingAction.ANSWER_DIRECTLY,
            target=None,
        ),
    ]
    return RoutingManifest(
        id="test_routing_manifest",
        status=ManifestStatus.ACTIVE,
        version="1.0.0",
        rules=rules,
    )


def test_decide_matched_intent_object() -> None:
    """Verify that a known intent in an object turn matches the routing rules."""
    manifest = _build_manifest()
    turn = DummyTurn(intent="check_balance")

    decision = decide(turn, manifest)

    assert decision.action == RoutingAction.ACTIVATE_SKILL
    assert decision.target == "erp_balance_skill"
    assert "test_routing_manifest" in decision.reason
    assert "check_balance" in decision.reason


def test_decide_matched_intent_dict() -> None:
    """Verify that a known intent in a dict turn matches the routing rules."""
    manifest = _build_manifest()
    turn = {"intent": "greet"}

    decision = decide(turn, manifest)

    assert decision.action == RoutingAction.ANSWER_DIRECTLY
    assert decision.target is None
    assert "test_routing_manifest" in decision.reason
    assert "greet" in decision.reason


def test_decide_fallback_unmatched_intent() -> None:
    """Verify fallback to answer_directly when intent is not found in manifest."""
    manifest = _build_manifest()
    turn = DummyTurn(intent="ask_for_help")

    decision = decide(turn, manifest)

    assert decision.action == RoutingAction.ANSWER_DIRECTLY
    assert decision.target is None
    assert "No matching rule found" in decision.reason
    assert "ask_for_help" in decision.reason


def test_decide_fallback_missing_intent() -> None:
    """Verify fallback when intent is None or missing from the turn context."""
    manifest = _build_manifest()
    turn = DummyTurn(intent=None)

    decision = decide(turn, manifest)

    assert decision.action == RoutingAction.ANSWER_DIRECTLY
    assert decision.target is None
    assert "No matching rule found" in decision.reason
