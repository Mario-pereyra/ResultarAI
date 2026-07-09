"""Dummy test doubles for ports to avoid network or external dependencies in tests."""

from typing import Any

from resultarai.core.manifests.policy import PolicyManifest
from resultarai.core.policy.models import ActionRequest, PolicyDecision
from resultarai.core.ports.llm import LLMPort, LLMResponse
from resultarai.core.ports.policy import PolicyPort
from resultarai.core.ports.state import StatePort
from resultarai.core.ports.tool import ToolPort
from resultarai.core.ports.trace import TracePort


class DummyPolicyPort(PolicyPort):
    """Dummy policy gate port for testing."""

    def __init__(
        self,
        default_effect: str = "allow",
        default_reason: str = "Allowed by default policy double",
    ) -> None:
        """Initialize the dummy policy port."""
        self.default_effect = default_effect
        self.default_reason = default_reason
        self.decision_override: PolicyDecision | None = None
        self.evaluations: list[ActionRequest] = []

    def evaluate(
        self, request: ActionRequest, active_policies: list[PolicyManifest]
    ) -> PolicyDecision:
        """Record evaluation and return pre-configured decision."""
        self.evaluations.append(request)
        if self.decision_override is not None:
            return self.decision_override
        return PolicyDecision(
            effect=self.default_effect,  # type: ignore[arg-type]
            reason=self.default_reason,
            applied_policy="dummy_policy_gate_double",
        )


class DummyLLMPort(LLMPort):
    """Dummy LLM port for testing."""

    def __init__(self, default_text: str = "Dummy response text") -> None:
        """Initialize the dummy LLM port."""
        self.default_text = default_text
        self.response_override: LLMResponse | None = None
        self.generations: list[dict[str, Any]] = []

    def generate(self, prompt: str, **kwargs: Any) -> LLMResponse:
        """Record generation and return pre-configured response."""
        self.generations.append({"prompt": prompt, "kwargs": kwargs})
        if self.response_override is not None:
            return self.response_override

        fallback_cascade = kwargs.get("fallback_cascade", [])
        profile_id = fallback_cascade[0] if fallback_cascade else "dummy_profile"

        return LLMResponse(
            text=self.default_text,
            model_profile_id=profile_id,
            is_alternate_model=False,
            primary_model_profile_id=None,
            fallback_reason=None,
            cache_hit_tokens=None,
            cache_miss_tokens=None,
            cost_usd=None,
            needs_pro=False,
        )


class DummyTracePort(TracePort):
    """Dummy trace/observability port for testing."""

    def __init__(self) -> None:
        """Initialize the dummy trace port."""
        self.traced_steps: list[dict[str, Any]] = []

    def trace_step(self, step_name: str, inputs: dict[str, Any], outputs: dict[str, Any]) -> None:
        """Record traced step in memory."""
        self.traced_steps.append({"step_name": step_name, "inputs": inputs, "outputs": outputs})


class DummyStatePort(StatePort):
    """Dummy state/persistence port for testing."""

    def __init__(self) -> None:
        """Initialize the dummy state port."""
        self.states: dict[str, dict[str, Any]] = {}

    def load_state(self, thread_id: str) -> dict[str, Any] | None:
        """Load from in-memory state dictionary."""
        return self.states.get(thread_id)

    def save_state(self, thread_id: str, state: dict[str, Any]) -> None:
        """Save to in-memory state dictionary."""
        self.states[thread_id] = state


class DummyToolPort(ToolPort):
    """Dummy tool execution port for testing."""

    def __init__(self) -> None:
        """Initialize the dummy tool port."""
        self.executions: list[dict[str, Any]] = []
        self.result_override: Any = "Dummy tool output"

    def execute(self, tool_name: str, arguments: dict[str, Any], decision: PolicyDecision) -> Any:
        """Record execution and return pre-configured output."""
        self.executions.append(
            {"tool_name": tool_name, "arguments": arguments, "decision": decision}
        )
        return self.result_override
