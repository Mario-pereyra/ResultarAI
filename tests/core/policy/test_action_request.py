"""Tests for ActionRequest validation and construction."""

import pytest
from pydantic import ValidationError

from resultarai.core.manifests.base import RiskLevel
from resultarai.core.policy import ActionRequest


def test_action_request_valid_non_erp() -> None:
    """Verify that a non-ERP tool request can be built without a tenant."""
    req = ActionRequest(
        user="user_1",
        tenant=None,
        agent="agent_1",
        skill="skill_1",
        tool="some_normal_tool",
        operation_type="read",
        risk_level=RiskLevel.LOW,
        environment="production",
    )
    assert req.user == "user_1"
    assert req.tenant is None
    assert req.tool == "some_normal_tool"


def test_action_request_valid_erp_with_tenant() -> None:
    """Verify that an ERP tool request can be built when a valid tenant is supplied."""
    # Tool starts with "erp_"
    req1 = ActionRequest(
        user="user_1",
        tenant="totalpec",
        agent="agent_1",
        skill="skill_1",
        tool="erp_read_invoices",
        operation_type="read",
        risk_level=RiskLevel.LOW,
        environment="production",
    )
    assert req1.tenant == "totalpec"

    # Tool contains "erp"
    req2 = ActionRequest(
        user="user_1",
        tenant="union",
        agent="agent_1",
        skill="skill_1",
        tool="get_erp_client_data",
        operation_type="read",
        risk_level=RiskLevel.LOW,
        environment="production",
    )
    assert req2.tenant == "union"


def test_action_request_invalid_erp_missing_tenant() -> None:
    """Verify that ERP tool requests fail if tenant is missing, None, or empty."""
    # Starts with "erp_" and tenant is None
    with pytest.raises(ValidationError) as exc_info:
        ActionRequest(
            user="user_1",
            tenant=None,
            agent="agent_1",
            skill="skill_1",
            tool="erp_read_invoices",
            operation_type="read",
            risk_level=RiskLevel.LOW,
            environment="production",
        )
    assert "tenant is required for ERP tools" in str(exc_info.value)

    # Contains "erp" and tenant is empty
    with pytest.raises(ValidationError) as exc_info:
        ActionRequest(
            user="user_1",
            tenant="  ",
            agent="agent_1",
            skill="skill_1",
            tool="get_erp_client_data",
            operation_type="read",
            risk_level=RiskLevel.LOW,
            environment="production",
        )
    assert "tenant is required for ERP tools" in str(exc_info.value)


def test_action_request_extra_fields_forbidden() -> None:
    """Verify that extra fields are forbidden during ActionRequest construction."""
    with pytest.raises(ValidationError):
        ActionRequest(
            user="user_1",
            tenant=None,
            agent="agent_1",
            skill="skill_1",
            tool="some_tool",
            operation_type="read",
            risk_level=RiskLevel.LOW,
            environment="production",
            extra_field="not_allowed",  # type: ignore
        )
