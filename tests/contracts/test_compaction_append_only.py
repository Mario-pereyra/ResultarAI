"""Contract test verifying compaction is append-only and does not alter original messages."""

from typing import Any, cast

from langchain_core.runnables import RunnableConfig
from resultarai.adapters.runtime_langgraph import GraphState, default_chat_graph
from tests.contracts.fixtures.doubles import (
    DummyLLMPort,
    DummyPolicyPort,
    DummyStatePort,
    DummyTracePort,
)
from tests.contracts.fixtures.session_near_limit import session_state_over_limit

# Keep pytest fixture in scope
_unused = [session_state_over_limit]


def test_compaction_is_append_only_and_preserves_history(
    session_state_over_limit: dict[str, Any],
) -> None:
    """Verify that compaction is append-only and leaves original messages completely untouched."""
    policy_port = DummyPolicyPort(default_effect="allow")
    llm_port = DummyLLMPort(default_text="Summary text")
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

    initial_messages = list(session_state_over_limit["messages"])

    initial_state = cast(GraphState, {
        **session_state_over_limit,
        "model_profile_id": session_state_over_limit["model_profile"],
        "model_profile_window": 100,
        "thread_id": "thread_append_only",
        "user": "user_abc",
        "tenant": "tenant_xyz",
        "agent": "agent_foo",
        "environment": "production",
        "prompt": "New Prompt",
        "status": "active",
        "intent": "general_question",
    })

    result = default_chat_graph.invoke(initial_state, config=config)

    # We expect 5 messages in total:
    # 0, 1: Original messages
    # 2: Summary message
    # 3: New Prompt
    # 4: Assistant response
    assert len(result["messages"]) == 5

    # Assert that the first 2 messages are exactly the original ones
    assert result["messages"][0] == initial_messages[0]
    assert result["messages"][1] == initial_messages[1]

    # Verify order and content of appended messages
    assert result["messages"][2]["role"] == "system"
    assert "Summary text" in result["messages"][2]["content"]

    assert result["messages"][3]["role"] == "user"
    assert result["messages"][3]["content"] == "New Prompt"

    assert result["messages"][4]["role"] == "assistant"
