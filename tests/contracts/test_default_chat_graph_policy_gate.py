"""Contract test verifying Policy Gate step evaluation and AuditEvent structure."""

from datetime import datetime

from langchain_core.runnables import RunnableConfig

from resultarai.adapters.runtime_langgraph import GraphState, default_chat_graph
from resultarai.core.audit import AuditEvent
from resultarai.core.policy import PolicyDecision
from tests.contracts.fixtures.doubles import (
    DummyLLMPort,
    DummyPolicyPort,
    DummyStatePort,
    DummyTracePort,
)


def test_policy_gate_allow_continues() -> None:
    """Verify that 'allow' policy effect allows completion, status active,

    and generates AuditEvent.
    """
    policy_port = DummyPolicyPort()
    policy_port.decision_override = PolicyDecision(
        effect="allow",
        reason="Allow override for testing",
        applied_policy="policy_allow_test",
    )
    llm_port = DummyLLMPort()
    trace_port = DummyTracePort()
    state_port = DummyStatePort()

    config: RunnableConfig = {
        "configurable": {
            "policy_port": policy_port,
            "llm_port": llm_port,
            "trace_port": trace_port,
            "state_port": state_port,
            "registries": None,
        }
    }

    initial_state: GraphState = {
        "thread_id": "thread_allow",
        "user": "user_abc",
        "tenant": "tenant_xyz",
        "agent": "agent_foo",
        "environment": "production",
        "messages": [],
        "already_compacted": False,
        "model_profile_id": "profile_1",
        "model_profile_window": 100,
        "prompt": "Hello",
        "status": "active",
        "intent": "general_question",
        "audit_events": [],
    }

    result = default_chat_graph.invoke(initial_state, config=config)

    assert result["status"] == "active"
    assert result["response"] is not None

    # Verify audit events
    audit_events = result.get("audit_events", [])
    assert len(audit_events) == 1
    event = audit_events[0]
    assert isinstance(event, AuditEvent)
    assert event.user == "user_abc"
    assert event.tenant == "tenant_xyz"
    assert event.agent == "agent_foo"
    assert event.skill == "default_chat"
    assert event.tool == ""
    assert event.operation_type == "read"
    assert event.effect == "allow"
    assert event.applied_policy == "policy_allow_test"
    assert event.reason == "Allow override for testing"
    assert isinstance(event.timestamp, datetime)
    assert event.environment == "production"


def test_policy_gate_deny_stops() -> None:
    """Verify that 'deny' policy effect stops execution, status denied, and generates AuditEvent."""
    policy_port = DummyPolicyPort()
    policy_port.decision_override = PolicyDecision(
        effect="deny",
        reason="Deny override for testing",
        applied_policy="policy_deny_test",
    )
    llm_port = DummyLLMPort()
    trace_port = DummyTracePort()
    state_port = DummyStatePort()

    config: RunnableConfig = {
        "configurable": {
            "policy_port": policy_port,
            "llm_port": llm_port,
            "trace_port": trace_port,
            "state_port": state_port,
            "registries": None,
        }
    }

    initial_state: GraphState = {
        "thread_id": "thread_deny",
        "user": "user_abc",
        "tenant": "tenant_xyz",
        "agent": "agent_foo",
        "environment": "production",
        "messages": [],
        "already_compacted": False,
        "model_profile_id": "profile_1",
        "model_profile_window": 100,
        "prompt": "Hello",
        "status": "active",
        "intent": "general_question",
        "audit_events": [],
    }

    result = default_chat_graph.invoke(initial_state, config=config)

    assert result["status"] == "denied"
    # No response should be generated when denied
    assert result.get("response") is None

    # Verify audit events
    audit_events = result.get("audit_events", [])
    assert len(audit_events) == 1
    event = audit_events[0]
    assert isinstance(event, AuditEvent)
    assert event.effect == "deny"
    assert event.applied_policy == "policy_deny_test"
    assert event.reason == "Deny override for testing"


def test_policy_gate_escalate_hitl_suspends() -> None:
    """Verify that 'escalate_hitl' policy effect suspends execution,

    status suspended, and generates AuditEvent.
    """
    policy_port = DummyPolicyPort()
    policy_port.decision_override = PolicyDecision(
        effect="escalate_hitl",
        reason="Escalate HITL override for testing",
        applied_policy="policy_hitl_test",
    )
    llm_port = DummyLLMPort()
    trace_port = DummyTracePort()
    state_port = DummyStatePort()

    config: RunnableConfig = {
        "configurable": {
            "policy_port": policy_port,
            "llm_port": llm_port,
            "trace_port": trace_port,
            "state_port": state_port,
            "registries": None,
        }
    }

    initial_state: GraphState = {
        "thread_id": "thread_hitl",
        "user": "user_abc",
        "tenant": "tenant_xyz",
        "agent": "agent_foo",
        "environment": "production",
        "messages": [],
        "already_compacted": False,
        "model_profile_id": "profile_1",
        "model_profile_window": 100,
        "prompt": "Hello",
        "status": "active",
        "intent": "general_question",
        "audit_events": [],
    }

    result = default_chat_graph.invoke(initial_state, config=config)

    assert result["status"] == "suspended"
    # No response generated when suspended/HITL
    assert result.get("response") is None

    # Verify audit events
    audit_events = result.get("audit_events", [])
    assert len(audit_events) == 1
    event = audit_events[0]
    assert isinstance(event, AuditEvent)
    assert event.effect == "escalate_hitl"
    assert event.applied_policy == "policy_hitl_test"
    assert event.reason == "Escalate HITL override for testing"
