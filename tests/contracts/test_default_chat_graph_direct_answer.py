"""Contract test verifying direct answer workflow in default_chat_graph."""

from langchain_core.runnables import RunnableConfig

from resultarai.adapters.runtime_langgraph import GraphState, default_chat_graph
from tests.contracts.fixtures.doubles import (
    DummyLLMPort,
    DummyPolicyPort,
    DummyStatePort,
    DummyToolPort,
    DummyTracePort,
)


def test_direct_answer_calls_llm_and_no_tool() -> None:
    """Verify that a turn without skill activation responds via LLMPort and calls no ToolPort."""
    policy_port = DummyPolicyPort(default_effect="allow")
    llm_port = DummyLLMPort(default_text="Direct answer from LLM")
    trace_port = DummyTracePort()
    state_port = DummyStatePort()
    tool_port = DummyToolPort()

    config: RunnableConfig = {
        "configurable": {
            "policy_port": policy_port,
            "llm_port": llm_port,
            "trace_port": trace_port,
            "state_port": state_port,
            "tool_port": tool_port,
            "registries": None,
        }
    }

    initial_state: GraphState = {
        "thread_id": "thread_123",
        "user": "user_abc",
        "tenant": "tenant_xyz",
        "agent": "agent_foo",
        "environment": "production",
        "messages": [],
        "already_compacted": False,
        "model_profile_id": "profile_1",
        "model_profile_window": 100,
        "prompt": "Tell me a joke",
        "status": "active",
        "intent": "general_question",
    }

    result = default_chat_graph.invoke(initial_state, config=config)

    # Verify final execution state
    assert result["status"] == "active"
    assert result["response"] is not None
    assert result["response"].text == "Direct answer from LLM"

    # Verify messages are appended
    assert len(result["messages"]) == 2
    assert result["messages"][0]["role"] == "user"
    assert result["messages"][0]["content"] == "Tell me a joke"
    assert result["messages"][1]["role"] == "assistant"
    assert result["messages"][1]["content"] == "Direct answer from LLM"

    # Verify port invocations
    assert len(llm_port.generations) == 1
    assert llm_port.generations[0]["prompt"] == "Tell me a joke"
    assert len(tool_port.executions) == 0
