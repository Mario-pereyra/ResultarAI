"""Tests for port protocols conformance."""

from typing import Any

from resultarai.core.policy import PolicyDecision
from resultarai.core.ports import LLMPort, StatePort, ToolPort, TracePort


class DummyLLM:
    """Mock LLMPort."""

    def generate(self, prompt: str, **kwargs: Any) -> str:
        return f"generated from {prompt}"


class DummyTool:
    """Mock ToolPort."""

    def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        decision: PolicyDecision,
    ) -> Any:
        return f"executed {tool_name} with {arguments}"


class DummyTrace:
    """Mock TracePort."""

    def trace_step(
        self,
        step_name: str,
        inputs: dict[str, Any],
        outputs: dict[str, Any],
    ) -> None:
        pass


class DummyState:
    """Mock StatePort."""

    def load_state(self, thread_id: str) -> dict[str, Any] | None:
        return {"thread_id": thread_id}

    def save_state(self, thread_id: str, state: dict[str, Any]) -> None:
        pass


def test_protocols_conformance() -> None:
    """Verify that dummy implementations structurally conform to the Protocols."""
    # These assignments will fail during mypy type checking if the protocols are not satisfied.
    llm: LLMPort = DummyLLM()
    tool: ToolPort = DummyTool()
    trace: TracePort = DummyTrace()
    state: StatePort = DummyState()

    assert llm.generate("hello") == "generated from hello"

    decision = PolicyDecision(
        effect="allow",
        reason="authorized",
        applied_policy="policy_1",
    )
    assert tool.execute("erp_read", {"id": 1}, decision) == "executed erp_read with {'id': 1}"

    trace.trace_step("test_step", {}, {})

    assert state.load_state("thread_1") == {"thread_id": "thread_1"}
    state.save_state("thread_1", {})
