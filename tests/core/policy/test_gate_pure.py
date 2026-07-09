"""Pure gate tests for Policy Gate (allow with permissive policy, deny-by-default, determinism)."""

from __future__ import annotations

from resultarai.core.manifests.base import RiskLevel
from resultarai.core.manifests.policy import PolicyManifest
from resultarai.core.policy import ActionRequest, policy_gate


def test_allow_with_permissive_policy(
    low_risk_read_request: ActionRequest,
    erp_read_only_policy: PolicyManifest,
) -> None:
    """Verify that an ActionRequest matching an allow rule in an active policy resolves to allow."""
    decision = policy_gate(low_risk_read_request, [erp_read_only_policy])
    assert decision.effect == "allow"
    assert decision.applied_policy == "erp_read_only_policy"
    assert "permitida" in decision.reason.lower()


def test_deny_by_default_no_matching_policy(low_risk_read_request: ActionRequest) -> None:
    """Verify that an ActionRequest that matches no policy/rule gets denied by default."""
    # No active policies at all
    decision = policy_gate(low_risk_read_request, [])
    assert decision.effect == "deny"
    assert decision.applied_policy == "deny_by_default"
    assert "bloqueada por defecto" in decision.reason.lower()


def test_deny_by_default_no_matching_rule(
    low_risk_read_request: ActionRequest,
    erp_read_only_policy: PolicyManifest,
) -> None:
    """Verify that if a policy applies to the skill but no rule matches, it denies by default."""
    # Create request with a write operation which doesn't match erp_read_only_policy's allow rules
    write_request = ActionRequest(
        user="Alice",
        tenant="totalpec",
        agent="agent_1",
        skill="erp_skill",
        tool="erp_write_invoices",
        operation_type="write",
        risk_level=RiskLevel.LOW,
        environment="production",
    )
    decision = policy_gate(write_request, [erp_read_only_policy])
    assert decision.effect == "deny"
    assert decision.applied_policy == "deny_by_default"


def test_policy_gate_determinism(
    low_risk_read_request: ActionRequest,
    erp_read_only_policy: PolicyManifest,
) -> None:
    """Verify that evaluating the same ActionRequest twice returns identical PolicyDecision."""
    decision1 = policy_gate(low_risk_read_request, [erp_read_only_policy])
    decision2 = policy_gate(low_risk_read_request, [erp_read_only_policy])
    assert decision1 == decision2
    assert decision1.model_dump() == decision2.model_dump()
