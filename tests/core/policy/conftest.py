"""Fixtures and configuration for policy core tests."""

from __future__ import annotations

import pytest
import yaml

from resultarai.core.manifests.base import RiskLevel
from resultarai.core.manifests.policy import PolicyManifest
from resultarai.core.policy import ActionRequest

ERP_READ_ONLY_POLICY_YAML = """
id: erp_read_only_policy
status: active
version: 1.0.0
applies_to:
  skills:
    - erp_skill
rules:
  - effect: allow
    when:
      operation_type: read
  - effect: escalate_hitl
    when:
      risk_level: high
  - effect: escalate_hitl
    when:
      risk_level: critical
"""

USER_TENANT_POLICY_YAML = """
id: user_tenant_policy
status: active
version: 1.0.0
applies_to:
  skills:
    - erp_skill
rules:
  - effect: allow
    when:
      user: Alice
      tenant: totalpec
  - effect: allow
    when:
      user: Alice
      tenant: union
  - effect: escalate_hitl
    when:
      user: Bob
      tenant: totalpec
      risk_level: high
"""


@pytest.fixture
def erp_read_only_policy() -> PolicyManifest:
    """Fixture that returns a validated erp_read_only_policy manifest."""
    data = yaml.safe_load(ERP_READ_ONLY_POLICY_YAML)
    return PolicyManifest.model_validate(data)


@pytest.fixture
def user_tenant_policy() -> PolicyManifest:
    """Fixture that returns a validated user_tenant_policy manifest."""
    data = yaml.safe_load(USER_TENANT_POLICY_YAML)
    return PolicyManifest.model_validate(data)


@pytest.fixture
def active_policies(
    erp_read_only_policy: PolicyManifest,
    user_tenant_policy: PolicyManifest,
) -> list[PolicyManifest]:
    """Fixture that returns a list of active policy manifests."""
    return [erp_read_only_policy, user_tenant_policy]


@pytest.fixture
def low_risk_read_request() -> ActionRequest:
    """Fixture that returns a low-risk read ActionRequest."""
    return ActionRequest(
        user="Alice",
        tenant="totalpec",
        agent="agent_1",
        skill="erp_skill",
        tool="erp_read_invoices",
        operation_type="read",
        risk_level=RiskLevel.LOW,
        environment="production",
        irreversible=False,
    )


@pytest.fixture
def medium_risk_read_request() -> ActionRequest:
    """Fixture that returns a medium-risk read ActionRequest."""
    return ActionRequest(
        user="Alice",
        tenant="totalpec",
        agent="agent_1",
        skill="erp_skill",
        tool="erp_read_invoices",
        operation_type="read",
        risk_level=RiskLevel.MEDIUM,
        environment="production",
        irreversible=False,
    )


@pytest.fixture
def high_risk_write_request() -> ActionRequest:
    """Fixture that returns a high-risk write ActionRequest."""
    return ActionRequest(
        user="Alice",
        tenant="totalpec",
        agent="agent_1",
        skill="erp_skill",
        tool="erp_write_invoices",
        operation_type="write",
        risk_level=RiskLevel.HIGH,
        environment="production",
        irreversible=False,
    )


@pytest.fixture
def critical_risk_write_request() -> ActionRequest:
    """Fixture that returns a critical-risk write ActionRequest."""
    return ActionRequest(
        user="Alice",
        tenant="totalpec",
        agent="agent_1",
        skill="erp_skill",
        tool="erp_write_invoices",
        operation_type="write",
        risk_level=RiskLevel.CRITICAL,
        environment="production",
        irreversible=False,
    )


@pytest.fixture
def critical_irreversible_request() -> ActionRequest:
    """Fixture that returns a critical-risk irreversible write ActionRequest."""
    return ActionRequest(
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


@pytest.fixture
def cross_tenant_request() -> ActionRequest:
    """Fixture that returns a request for a different tenant than authorized."""
    return ActionRequest(
        user="Alice",
        tenant="unauthorized_tenant",
        agent="agent_1",
        skill="erp_skill",
        tool="erp_read_invoices",
        operation_type="read",
        risk_level=RiskLevel.LOW,
        environment="production",
        irreversible=False,
    )
