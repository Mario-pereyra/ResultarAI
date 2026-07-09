"""ToolPort Protocol definition."""

from typing import TYPE_CHECKING, Any, Protocol

if TYPE_CHECKING:
    from resultarai.core.policy import PolicyDecision


class ToolPort(Protocol):
    """Protocol for executing tools.

    Will be implemented by the runtime/mcp adapters in b06/c09.
    """

    def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        decision: "PolicyDecision",
    ) -> Any:
        """Execute a tool given its name, arguments and the approved PolicyDecision."""
        ...
