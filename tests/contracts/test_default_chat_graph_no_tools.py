"""Contract test asserting no node in default_chat_graph directly calls ToolPort."""

from typing import Any

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


class ThrowingToolPort:
    """ToolPort double that raises an exception if any method is called."""

    def execute(self, *args: Any, **kwargs: Any) -> None:
        raise AssertionError("ToolPort should not be called by the default chat graph.")


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


def test_default_chat_graph_never_invokes_tool_port() -> None:
    """Assert that default_chat_graph never directly invokes ToolPort.

    Checks both direct answer and skill activation cases.
    """
    policy_port = DummyPolicyPort()
    llm_port = DummyLLMPort()
    trace_port = DummyTracePort()
    state_port = DummyStatePort()
    tool_port = ThrowingToolPort()
    registries = _setup_registries()

    config: RunnableConfig = {
        "configurable": {
            "policy_port": policy_port,
            "llm_port": llm_port,
            "trace_port": trace_port,
            "state_port": state_port,
            "tool_port": tool_port,
            "registries": registries,
        }
    }

    # 1. Test direct answer
    state_direct: GraphState = {
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
    result_direct = default_chat_graph.invoke(state_direct, config=config)
    assert result_direct["status"] == "active"

    # 2. Test skill activation placeholder (executes execute_graph placeholder
    # but should NOT execute tools)
    state_skill: GraphState = {
        "thread_id": "thread_skill",
        "user": "user_abc",
        "tenant": "tenant_xyz",
        "agent": "agent_foo",
        "environment": "production",
        "messages": [],
        "already_compacted": False,
        "model_profile_id": "profile_1",
        "model_profile_window": 100,
        "prompt": "Run skill",
        "status": "active",
        "intent": "example_task",
    }
    result_skill = default_chat_graph.invoke(state_skill, config=config)
    assert result_skill["status"] == "active"
