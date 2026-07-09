"""Tests for audit coverage, parameter enmasking, and event corrections."""

from __future__ import annotations

from typing import Any

import pytest

from resultarai.core.audit import create_audit_event
from resultarai.core.manifests.base import RiskLevel
from resultarai.core.policy import ActionRequest, PolicyDecision


@pytest.fixture
def sensitive_parameters() -> dict[str, Any]:
    """Fixture containing parameters with sensitive keys to test enmasking."""
    return {
        "public_id": "user_123",
        "db_password": "supersecretpassword",
        "SECRET_VAL": "dont-share-this",
        "apiToken": "tkn_99812",
        "API_KEY": "sk_live_123",
        "user_credentials": "user:pass",
        "oauth_header": "Bearer mytoken",
        "private_info": "ssn_value",
        "nested_dict": {
            "normal_field": "safe_value",
            "password": "nested_password",
            "nested_secret": "nested_secret_val",
        },
        "nested_list": [
            {"safe_field": "safe"},
            {"secret_key": "masked_in_list"},
        ],
    }


def test_audit_event_mapping_and_coverage(sensitive_parameters: dict[str, Any]) -> None:
    """Verify that create_audit_event maps all fields correctly for all decision effects."""
    effects = ["allow", "deny", "escalate_hitl"]

    for effect in effects:
        request = ActionRequest(
            user="Alice",
            tenant="totalpec",
            agent="agent_1",
            skill="erp_skill",
            tool="erp_read_invoices",
            operation_type="read",
            risk_level=RiskLevel.LOW,
            environment="production",
            parameters={"id": "123"},
        )
        decision = PolicyDecision(
            effect=effect,  # type: ignore
            reason=f"Effect is {effect}",
            applied_policy="erp_read_only_policy",
        )

        event = create_audit_event(request, decision)

        # Verify mapping matches request & decision
        assert event.user == request.user
        assert event.tenant == request.tenant
        assert event.agent == request.agent
        assert event.skill == request.skill
        assert event.tool == request.tool
        assert event.operation_type == request.operation_type
        assert event.environment == request.environment
        assert event.effect == decision.effect
        assert event.applied_policy == decision.applied_policy
        assert event.reason == decision.reason
        assert event.corrects is None


def test_audit_event_secrets_enmasking(sensitive_parameters: dict[str, Any]) -> None:
    """Verify that sensitive parameter keys (case-insensitive) are enmasked."""
    request = ActionRequest(
        user="Alice",
        tenant="totalpec",
        agent="agent_1",
        skill="erp_skill",
        tool="erp_read_invoices",
        operation_type="read",
        risk_level=RiskLevel.LOW,
        environment="production",
        parameters=sensitive_parameters,
    )
    decision = PolicyDecision(
        effect="allow",
        reason="Action permitted",
        applied_policy="erp_read_only_policy",
    )

    event = create_audit_event(request, decision)
    params = event.parameters

    # Check non-sensitive keys remain unchanged
    assert params["public_id"] == "user_123"
    assert params["nested_dict"]["normal_field"] == "safe_value"
    assert params["nested_list"][0]["safe_field"] == "safe"

    # Check sensitive keys are enmasked (case-insensitively)
    assert params["db_password"] == "[ENMASKED]"
    assert params["SECRET_VAL"] == "[ENMASKED]"
    assert params["apiToken"] == "[ENMASKED]"
    assert params["API_KEY"] == "[ENMASKED]"
    assert params["user_credentials"] == "[ENMASKED]"
    assert params["oauth_header"] == "[ENMASKED]"
    assert params["private_info"] == "[ENMASKED]"

    # Check nested dictionary masking
    assert params["nested_dict"]["password"] == "[ENMASKED]"
    assert params["nested_dict"]["nested_secret"] == "[ENMASKED]"

    # Check nested list dictionary masking
    assert params["nested_list"][1]["secret_key"] == "[ENMASKED]"


def test_audit_event_correction() -> None:
    """Verify that a correction event points to the original event's ID."""
    request = ActionRequest(
        user="Alice",
        tenant="totalpec",
        agent="agent_1",
        skill="erp_skill",
        tool="erp_read_invoices",
        operation_type="read",
        risk_level=RiskLevel.LOW,
        environment="production",
        parameters={"id": "123"},
    )
    decision = PolicyDecision(
        effect="allow",
        reason="Corrected decision",
        applied_policy="erp_read_only_policy",
    )

    original_event_id = "orig_evt_abc123"
    event = create_audit_event(request, decision, corrects=original_event_id)

    assert event.corrects == original_event_id
