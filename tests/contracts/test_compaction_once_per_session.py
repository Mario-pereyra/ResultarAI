"""Contract test verifying already-compacted sessions do not compact again."""

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


def test_already_compacted_session_does_not_compact_again(
    session_state_over_limit: dict[str, Any],
) -> None:
    """Verify that a session with already_compacted=True does not trigger compaction

    even when usage is over limit.
    """
    policy_port = DummyPolicyPort(default_effect="allow")
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

    initial_state = cast(
        GraphState,
        {
            **session_state_over_limit,
            "already_compacted": True,  # Mark as already compacted
            "model_profile_id": session_state_over_limit["model_profile"],
            "model_profile_window": 100,  # Usage is 82, which would normally trigger compaction
            "thread_id": "thread_already_compacted",
            "user": "user_abc",
            "tenant": "tenant_xyz",
            "agent": "agent_foo",
            "environment": "production",
            "prompt": "Hello",
            "status": "active",
            "intent": "general_question",
        },
    )

    result = default_chat_graph.invoke(initial_state, config=config)

    assert result["already_compacted"] is True
    # Verify no additional compaction occurred:
    # Original messages (2) + prompt (1) + assistant reply (1) = 4
    assert len(result["messages"]) == 4

    traced_steps = [step["step_name"] for step in trace_port.traced_steps]
    assert "compaction" not in traced_steps
