"""Contract test verifying compaction trigger boundaries (threshold of 80%)."""

from typing import Any, cast

from langchain_core.runnables import RunnableConfig

from resultarai.adapters.runtime_langgraph import GraphState, default_chat_graph
from tests.contracts.fixtures.doubles import (
    DummyLLMPort,
    DummyPolicyPort,
    DummyStatePort,
    DummyTracePort,
)
from tests.contracts.fixtures.session_near_limit import (
    session_state_near_limit,
    session_state_over_limit,
)

# Keep pytest fixtures in scope
_unused = [session_state_near_limit, session_state_over_limit]


def test_compaction_not_triggered_below_80_percent(
    session_state_near_limit: dict[str, Any],
) -> None:
    """Verify that a session usage below 80% of window does not trigger compaction."""
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
            **session_state_near_limit,
            "model_profile_id": session_state_near_limit["model_profile"],
            "model_profile_window": 100,  # 78 usage is below 80% of 100
            "thread_id": "thread_near_limit",
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

    assert result["already_compacted"] is False
    # No compaction summary message appended
    # Original messages (2) + prompt (1) + assistant reply (1) = 4
    assert len(result["messages"]) == 4
    # Assert no compaction trace
    traced_steps = [step["step_name"] for step in trace_port.traced_steps]
    assert "compaction" not in traced_steps


def test_compaction_triggered_at_or_above_80_percent(
    session_state_over_limit: dict[str, Any],
) -> None:
    """Verify that session usage at or above 80% of window triggers compaction

    on next turn start.
    """
    policy_port = DummyPolicyPort(default_effect="allow")
    llm_port = DummyLLMPort(default_text="Compacted summary text")
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
            "model_profile_id": session_state_over_limit["model_profile"],
            "model_profile_window": 100,  # 82 usage is above 80% of 100
            "thread_id": "thread_over_limit",
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
    # Original messages (2) + summary msg (1) + prompt (1) + assistant reply (1) = 5
    assert len(result["messages"]) == 5

    # Check compaction summary message content
    summary_msg = result["messages"][2]
    assert summary_msg["role"] == "system"
    assert "Compacted summary text" in summary_msg["content"]

    # Verify compaction trace was logged
    traced_steps = [step["step_name"] for step in trace_port.traced_steps]
    assert "compaction" in traced_steps
    compaction_trace = next(
        step for step in trace_port.traced_steps if step["step_name"] == "compaction"
    )
    assert compaction_trace["outputs"]["compacted"] is True
    assert len(compaction_trace["outputs"]["range"]) == 2  # The 2 original messages compacted
