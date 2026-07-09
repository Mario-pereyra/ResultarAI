"""Contract test verifying turn cycle trace events and turn_id coherence."""

from langchain_core.runnables import RunnableConfig

from resultarai.adapters.runtime_langgraph import GraphState, default_chat_graph
from resultarai.core.manifests.base import ManifestStatus
from resultarai.core.manifests.routing import RoutingAction, RoutingManifest, RoutingRule
from resultarai.core.registries import (
    AgentRegistry,
    EvalTemplateRegistry,
    PolicyRegistry,
    Registries,
    RoutingRegistry,
    SkillRegistry,
    ToolRegistry,
)
from tests.contracts.fixtures.doubles import (
    DummyLLMPort,
    DummyPolicyPort,
    DummyStatePort,
    DummyTracePort,
)


def _setup_registries() -> Registries:
    routing_manifest = RoutingManifest(
        id="default_routing",
        status=ManifestStatus.ACTIVE,
        version="1.0.0",
        rules=[
            RoutingRule(
                intent="example_task",
                action=RoutingAction.ACTIVATE_SKILL,
                target="example_skill",
            )
        ],
    )
    return Registries(
        agents=AgentRegistry([]),
        skills=SkillRegistry([]),
        tools=ToolRegistry([]),
        policies=PolicyRegistry([]),
        routing=RoutingRegistry([routing_manifest]),
        evals=EvalTemplateRegistry([]),
        model_profiles={},
    )


def test_turn_cycle_direct_answer_trace_sequence() -> None:
    """Verify trace events for a direct answer turn cycle (receive, route, respond)."""
    policy_port = DummyPolicyPort(default_effect="allow")
    llm_port = DummyLLMPort()
    trace_port = DummyTracePort()
    state_port = DummyStatePort()
    registries = _setup_registries()

    config: RunnableConfig = {
        "configurable": {
            "policy_port": policy_port,
            "llm_port": llm_port,
            "trace_port": trace_port,
            "state_port": state_port,
            "registries": registries,
        }
    }

    initial_state: GraphState = {
        "thread_id": "thread_direct",
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
    }

    result = default_chat_graph.invoke(initial_state, config=config)

    assert result["status"] == "active"

    # Verify traced step names
    traced_steps = [step["step_name"] for step in trace_port.traced_steps]
    assert "receive" in traced_steps
    assert "route" in traced_steps
    assert "respond" in traced_steps
    assert "execute_graph" not in traced_steps

    # Verify they all share the same turn_id
    turn_ids = {
        step["outputs"].get("turn_id")
        for step in trace_port.traced_steps
        if step["step_name"] in {"receive", "route", "respond"}
    }
    assert len(turn_ids) == 1
    assert None not in turn_ids
    assert result["turn_id"] in turn_ids


def test_turn_cycle_skill_activation_trace_sequence() -> None:
    """Verify trace events for a skill activation turn cycle (receive, route, execute_graph)."""
    policy_port = DummyPolicyPort(default_effect="allow")
    llm_port = DummyLLMPort()
    trace_port = DummyTracePort()
    state_port = DummyStatePort()
    registries = _setup_registries()

    config: RunnableConfig = {
        "configurable": {
            "policy_port": policy_port,
            "llm_port": llm_port,
            "trace_port": trace_port,
            "state_port": state_port,
            "registries": registries,
        }
    }

    initial_state: GraphState = {
        "thread_id": "thread_skill",
        "user": "user_abc",
        "tenant": "tenant_xyz",
        "agent": "agent_foo",
        "environment": "production",
        "messages": [],
        "already_compacted": False,
        "model_profile_id": "profile_1",
        "model_profile_window": 100,
        "prompt": "Run task",
        "status": "active",
        "intent": "example_task",
    }

    result = default_chat_graph.invoke(initial_state, config=config)

    assert result["status"] == "active"

    traced_steps = [step["step_name"] for step in trace_port.traced_steps]
    assert "receive" in traced_steps
    assert "route" in traced_steps
    assert "execute_graph" in traced_steps
    assert "respond" not in traced_steps

    # Verify they all share the same turn_id
    turn_ids = {
        step["outputs"].get("turn_id")
        for step in trace_port.traced_steps
        if step["step_name"] in {"receive", "route", "execute_graph"}
    }
    assert len(turn_ids) == 1
    assert None not in turn_ids
    assert result["turn_id"] in turn_ids


def test_interrupted_turn_denied_prevents_subsequent_traces() -> None:
    """Verify that a denied policy check interrupts the turn and prevents later traces."""
    policy_port = DummyPolicyPort(default_effect="deny")
    llm_port = DummyLLMPort()
    trace_port = DummyTracePort()
    state_port = DummyStatePort()
    registries = _setup_registries()

    config: RunnableConfig = {
        "configurable": {
            "policy_port": policy_port,
            "llm_port": llm_port,
            "trace_port": trace_port,
            "state_port": state_port,
            "registries": registries,
        }
    }

    initial_state: GraphState = {
        "thread_id": "thread_denied",
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
    }

    result = default_chat_graph.invoke(initial_state, config=config)

    assert result["status"] == "denied"

    # Only receive and route are traced. policy gate is evaluated,
    # but execute_graph / respond are skipped.
    traced_steps = [step["step_name"] for step in trace_port.traced_steps]
    assert "receive" in traced_steps
    assert "route" in traced_steps
    assert "respond" not in traced_steps
    assert "execute_graph" not in traced_steps
