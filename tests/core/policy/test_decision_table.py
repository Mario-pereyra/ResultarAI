"""Tests the Policy Gate decision table matrix and runtime step independence."""

from __future__ import annotations

import pytest

from resultarai.core.manifests.base import RiskLevel
from resultarai.core.manifests.policy import PolicyManifest
from resultarai.core.policy import ActionRequest, policy_gate


@pytest.mark.parametrize(
    (
        "operation_type",
        "risk_level",
        "request_skill",
        "request_tenant",
        "request_user",
        "expected_effect",
        "expected_policy",
    ),
    [
        # 1. Matches read-only policy for erp_skill: low risk, authorized tenant -> allow
        (
            "read",
            RiskLevel.LOW,
            "erp_skill",
            "totalpec",
            "Alice",
            "allow",
            "erp_read_only_policy",
        ),
        # 2. Matches read-only policy: medium risk, authorized tenant -> allow (with limits)
        (
            "read",
            RiskLevel.MEDIUM,
            "erp_skill",
            "totalpec",
            "Alice",
            "allow",
            "erp_read_only_policy",
        ),
        # 3. Matches read-only policy: high risk, authorized tenant -> escalate_hitl
        (
            "read",
            RiskLevel.HIGH,
            "erp_skill",
            "totalpec",
            "Alice",
            "escalate_hitl",
            "erp_read_only_policy",
        ),
        # 4. Matches read-only policy: critical risk, authorized tenant -> escalate_hitl
        (
            "read",
            RiskLevel.CRITICAL,
            "erp_skill",
            "totalpec",
            "Alice",
            "escalate_hitl",
            "erp_read_only_policy",
        ),
        # 5. Write operation on erp_read_only_policy (doesn't match rules) -> deny
        # Matches user_tenant_policy
        (
            "write",
            RiskLevel.LOW,
            "erp_skill",
            "totalpec",
            "Alice",
            "allow",
            "user_tenant_policy",
        ),
        # 6. Cruce de tenants: Alice is associated with totalpec/union.
        # Request to "other" -> deny (user-tenant isolation)
        (
            "read",
            RiskLevel.LOW,
            "erp_skill",
            "other",
            "Alice",
            "deny",
            "deny_by_default",
        ),
        # 7. Bob is associated with totalpec.
        # Request to union -> deny (user-tenant isolation)
        (
            "read",
            RiskLevel.LOW,
            "erp_skill",
            "union",
            "Bob",
            "deny",
            "deny_by_default",
        ),
        # 8. Request for unmapped skill (no policy applies) -> deny
        (
            "read",
            RiskLevel.LOW,
            "unmapped_skill",
            "totalpec",
            "Alice",
            "deny",
            "deny_by_default",
        ),
    ],
)
def test_decision_table(
    active_policies: list[PolicyManifest],
    operation_type: str,
    risk_level: RiskLevel,
    request_skill: str,
    request_tenant: str,
    request_user: str,
    expected_effect: str,
    expected_policy: str,
) -> None:
    """Evaluates various combinations from the decision table matrix."""
    request = ActionRequest(
        user=request_user,
        tenant=request_tenant,
        agent="agent_1",
        skill=request_skill,
        tool="erp_tool",
        operation_type=operation_type,  # type: ignore
        risk_level=risk_level,
        environment="production",
        irreversible=False,
    )
    decision = policy_gate(request, active_policies)
    assert decision.effect == expected_effect
    assert decision.applied_policy == expected_policy


def test_runtime_authorization_per_step_independence(
    active_policies: list[PolicyManifest],
) -> None:
    """Verify that consecutive calls to policy gate are independent.

    Uses Runtime Authorization per Step.
    """
    # Step 1: Low risk request -> should be allowed
    req_step_1 = ActionRequest(
        user="Alice",
        tenant="totalpec",
        agent="agent_1",
        skill="erp_skill",
        tool="erp_read",
        operation_type="read",
        risk_level=RiskLevel.LOW,
        environment="production",
    )
    decision_1 = policy_gate(req_step_1, active_policies)
    assert decision_1.effect == "allow"

    # Step 2: High risk request on same context -> should be escalated to HITL.
    # Unaffected by prior allow.
    req_step_2 = ActionRequest(
        user="Alice",
        tenant="totalpec",
        agent="agent_1",
        skill="erp_skill",
        tool="erp_write",
        operation_type="write",
        risk_level=RiskLevel.HIGH,
        environment="production",
    )
    decision_2 = policy_gate(req_step_2, active_policies)
    assert decision_2.effect == "escalate_hitl"

    # Step 3: Cruce de tenants request -> should be denied
    req_step_3 = ActionRequest(
        user="Alice",
        tenant="unauthorized",
        agent="agent_1",
        skill="erp_skill",
        tool="erp_read",
        operation_type="read",
        risk_level=RiskLevel.LOW,
        environment="production",
    )
    decision_3 = policy_gate(req_step_3, active_policies)
    assert decision_3.effect == "deny"
