"""Contract test verifying replaying subsequent turns acts as new message

without rolling back compaction.
"""

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


def test_subsequent_turn_after_compaction_keeps_compacted_history(
    session_state_over_limit: dict[str, Any],
) -> None:
    """Verify that after compaction has run, a subsequent turn functions normally

    and does not rollback compaction.
    """
    policy_port = DummyPolicyPort(default_effect="allow")
    # Setup LLM port to return distinct answers
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

    # --- TURN 1 (Triggers Compaction) ---
    state_turn1 = cast(
        GraphState,
        {
            **session_state_over_limit,
            "model_profile_id": session_state_over_limit["model_profile"],
            "model_profile_window": 100,
            "thread_id": "thread_replay",
            "user": "user_abc",
            "tenant": "tenant_xyz",
            "agent": "agent_foo",
            "environment": "production",
            "prompt": "Prompt 1",
            "status": "active",
            "intent": "general_question",
        },
    )

    result_turn1 = default_chat_graph.invoke(state_turn1, config=config)

    assert result_turn1["already_compacted"] is True
    # 2 original + 1 summary + 1 user prompt + 1 assistant reply = 5 messages
    assert len(result_turn1["messages"]) == 5
    assert result_turn1["messages"][2]["role"] == "system"

    # --- TURN 2 (Subsequent Turn) ---
    llm_port.default_text = "Reply 2"
    state_turn2 = cast(
        GraphState,
        {
            **result_turn1,
            "prompt": "Prompt 2",
        },
    )

    result_turn2 = default_chat_graph.invoke(state_turn2, config=config)

    assert result_turn2["already_compacted"] is True
    # 5 messages from turn 1 + 1 user prompt + 1 assistant reply = 7 messages
    assert len(result_turn2["messages"]) == 7

    # Assert that history is preserved and NOT rolled back
    assert result_turn2["messages"][0] == session_state_over_limit["messages"][0]
    assert result_turn2["messages"][1] == session_state_over_limit["messages"][1]
    assert result_turn2["messages"][2]["role"] == "system"
    assert "Summary text" in result_turn2["messages"][2]["content"]
    assert result_turn2["messages"][3]["role"] == "user"
    assert result_turn2["messages"][3]["content"] == "Prompt 1"
    assert result_turn2["messages"][4]["role"] == "assistant"

    # Verify new messages
    assert result_turn2["messages"][5]["role"] == "user"
    assert result_turn2["messages"][5]["content"] == "Prompt 2"
    assert result_turn2["messages"][6]["role"] == "assistant"
    assert result_turn2["messages"][6]["content"] == "Reply 2"
