"""Tests for PolicyPort protocol conformance."""

from resultarai.core.manifests import PolicyManifest
from resultarai.core.policy import ActionRequest, PolicyDecision
from resultarai.core.ports import PolicyPort


class FakePolicyAdapter:
    """Fake policy evaluator conforming to PolicyPort."""

    def evaluate(
        self,
        request: ActionRequest,
        active_policies: list[PolicyManifest],
    ) -> PolicyDecision:
        if not active_policies:
            return PolicyDecision(
                effect="deny",
                reason="No active policies",
                applied_policy="deny_by_default",
            )
        return PolicyDecision(
            effect="allow",
            reason="Passed fake check",
            applied_policy=active_policies[0].id,
        )


def test_policy_port_conformance() -> None:
    """Verify FakePolicyAdapter conforms to PolicyPort protocol."""
    policy_port: PolicyPort = FakePolicyAdapter()

    from resultarai.core.manifests.base import RiskLevel

    request = ActionRequest(
        user="user_1",
        tenant=None,
        agent="agent_1",
        skill="skill_1",
        tool="tool_1",
        operation_type="read",
        risk_level=RiskLevel.LOW,
        environment="production",
    )

    # Test with empty policies list
    decision_deny = policy_port.evaluate(request, [])
    assert decision_deny.effect == "deny"
    assert decision_deny.applied_policy == "deny_by_default"

    # Test with mock PolicyManifest
    # Since PolicyManifest is a Pydantic model, we can construct one using dummy values.
    # From policy.py:
    # class PolicyManifest(BaseManifest):
    #     applies_to: PolicyAppliesTo
    #     rules: list[PolicyRule]
    from resultarai.core.manifests import ManifestStatus
    from resultarai.core.manifests.policy import PolicyAppliesTo

    mock_policy = PolicyManifest(
        id="policy_1",
        status=ManifestStatus.ACTIVE,
        version="1.0.0",
        applies_to=PolicyAppliesTo(skills=["skill_1"]),
        rules=[],
    )

    decision_allow = policy_port.evaluate(request, [mock_policy])
    assert decision_allow.effect == "allow"
    assert decision_allow.applied_policy == "policy_1"
