"""Tests for risk level mapping, HITL features, and user-tenant isolation."""

from __future__ import annotations

import yaml

from resultarai.core.manifests.base import RiskLevel
from resultarai.core.manifests.policy import PolicyManifest
from resultarai.core.policy import ActionRequest, policy_gate


def test_risk_low_mapping(
    low_risk_read_request: ActionRequest,
    erp_read_only_policy: PolicyManifest,
) -> None:
    """Verify low risk maps to allow when permitted by policy."""
    decision = policy_gate(low_risk_read_request, [erp_read_only_policy])
    assert decision.effect == "allow"
    assert decision.limits is None
    assert decision.requires_approver_comment is False
    assert decision.requires_second_approval is False


def test_risk_medium_mapping(
    medium_risk_read_request: ActionRequest,
    erp_read_only_policy: PolicyManifest,
) -> None:
    """Verify medium risk maps to allow with limits when permitted by policy."""
    decision = policy_gate(medium_risk_read_request, [erp_read_only_policy])
    assert decision.effect == "allow"
    assert decision.limits == {"max_rows": 20, "pagination": True, "summarize": True}
    assert decision.requires_approver_comment is False
    assert decision.requires_second_approval is False


def test_risk_high_mapping(
    high_risk_write_request: ActionRequest,
    erp_read_only_policy: PolicyManifest,
) -> None:
    """Verify high risk maps to escalate_hitl."""
    decision = policy_gate(high_risk_write_request, [erp_read_only_policy])
    assert decision.effect == "escalate_hitl"
    assert decision.requires_approver_comment is False
    assert decision.requires_second_approval is False


def test_risk_critical_mapping(
    critical_risk_write_request: ActionRequest,
    erp_read_only_policy: PolicyManifest,
) -> None:
    """Verify critical risk maps to escalate_hitl with requires_approver_comment."""
    decision = policy_gate(critical_risk_write_request, [erp_read_only_policy])
    assert decision.effect == "escalate_hitl"
    assert decision.requires_approver_comment is True
    assert decision.requires_second_approval is False


def test_risk_critical_irreversible_request_mapping(
    critical_irreversible_request: ActionRequest,
    erp_read_only_policy: PolicyManifest,
) -> None:
    """Verify critical risk with irreversible request maps to escalate_hitl with second approval."""
    decision = policy_gate(critical_irreversible_request, [erp_read_only_policy])
    assert decision.effect == "escalate_hitl"
    assert decision.requires_approver_comment is True
    assert decision.requires_second_approval is True


def test_risk_critical_irreversible_rule_mapping(
    critical_risk_write_request: ActionRequest,
    user_tenant_policy: PolicyManifest,
) -> None:
    """Verify critical risk with rule of irreversible: True.

    Should map to escalate_hitl with second approval.
    """
    # Let's create an active policy with a rule containing irreversible: True in when
    yaml_policy = """
id: critical_irreversible_policy
status: active
version: 1.0.0
applies_to:
  skills:
    - erp_skill
rules:
  - effect: allow
    when:
      operation_type: write
      irreversible: true
"""
    policy = PolicyManifest.model_validate(yaml.safe_load(yaml_policy))

    # Request is irreversible=True, matching the rule
    req = ActionRequest(
        user="Alice",
        tenant="totalpec",
        agent="agent_1",
        skill="erp_skill",
        tool="erp_write_invoices",
        operation_type="write",
        risk_level=RiskLevel.CRITICAL,
        environment="production",
        irreversible=True,
    )
    decision = policy_gate(req, [policy])
    assert decision.effect == "escalate_hitl"
    assert decision.requires_approver_comment is True
    assert decision.requires_second_approval is True


def test_user_tenant_isolation_blocked(
    cross_tenant_request: ActionRequest,
    active_policies: list[PolicyManifest],
) -> None:
    """Verify that user-tenant cross requests are blocked."""
    decision = policy_gate(cross_tenant_request, active_policies)
    assert decision.effect == "deny"
    assert decision.applied_policy == "deny_by_default"
    assert decision.reason == "Falta de autorización usuario↔tenant: cruce entre tenants bloqueado"


def test_user_tenant_isolation_allowed(
    low_risk_read_request: ActionRequest,
    active_policies: list[PolicyManifest],
) -> None:
    """Verify that requests matching the authorized user-tenant association are allowed."""
    decision = policy_gate(low_risk_read_request, active_policies)
    assert decision.effect == "allow"
