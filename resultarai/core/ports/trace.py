"""TracePort Protocol definition."""

from typing import Any, Protocol


class TracePort(Protocol):
    """Protocol for logging/tracing execution steps.

    Will be implemented by the observability adapter (Langfuse) in b07.
    """

    def trace_step(
        self,
        step_name: str,
        inputs: dict[str, Any],
        outputs: dict[str, Any],
    ) -> None:
        """Trace a execution step with its inputs and outputs."""
        ...
