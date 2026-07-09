"""Tests for SkillRouter audit log and action request mappings."""

import pytest
from pydantic import ValidationError

from resultarai.core.manifests.base import RiskLevel
from resultarai.core.manifests.routing import RoutingAction
from resultarai.core.routing import RoutingDecision, to_action_request


class DummyTurnContext:
    """Mock turn context object."""

    def __init__(self, user: str, tenant: str | None, agent: str, environment: str) -> None:
        self.user = user
        self.tenant = tenant
        self.agent = agent
        self.environment = environment


def test_to_action_request_activate_skill_object_context() -> None:
    """Verify mapping for activate_skill decision using an object context."""
    decision = RoutingDecision(
        action=RoutingAction.ACTIVATE_SKILL,
        target="erp_balance_skill",
        reason="Matched intent check_balance",
    )
    context = DummyTurnContext(
        user="test_user",
        tenant="test_tenant",
        agent="test_agent",
        environment="staging",
    )

    action_request = to_action_request(decision, context)

    assert action_request.user == "test_user"
    assert action_request.tenant == "test_tenant"
    assert action_request.agent == "test_agent"
    assert action_request.environment == "staging"
    assert action_request.skill == "erp_balance_skill"
    assert action_request.tool == ""
    assert action_request.risk_level == RiskLevel.LOW
    assert action_request.operation_type == "read"


def test_to_action_request_answer_directly_dict_context() -> None:
    """Verify mapping for answer_directly decision using a dict context."""
    decision = RoutingDecision(
        action=RoutingAction.ANSWER_DIRECTLY,
        target=None,
        reason="Matched fallback",
    )
    context = {
        "user": "test_user_2",
        "tenant": "test_tenant_2",
        "agent": "test_agent_2",
        "environment": "production",
    }

    action_request = to_action_request(decision, context)

    assert action_request.user == "test_user_2"
    assert action_request.tenant == "test_tenant_2"
    assert action_request.agent == "test_agent_2"
    assert action_request.environment == "production"
    assert action_request.skill == "default_chat"
    assert action_request.tool == ""
    assert action_request.risk_level == RiskLevel.LOW
    assert action_request.operation_type == "read"


def test_to_action_request_missing_required_fields_fails() -> None:
    """Verify that if turn context lacks required fields, Pydantic validation fails."""
    decision = RoutingDecision(
        action=RoutingAction.ANSWER_DIRECTLY,
        target=None,
        reason="Fallback",
    )
    # Missing 'user' and 'agent' in context
    context = {
        "tenant": "test_tenant",
        "environment": "production",
    }

    with pytest.raises(ValidationError):
        to_action_request(decision, context)
