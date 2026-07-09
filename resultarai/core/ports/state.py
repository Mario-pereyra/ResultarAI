"""StatePort Protocol definition."""

from typing import Any, Protocol


class StatePort(Protocol):
    """Protocol for state storage.

    Will be implemented by the persistence adapter (Postgres) in b04.
    """

    def load_state(self, thread_id: str) -> dict[str, Any] | None:
        """Load state by thread identifier."""
        ...

    def save_state(self, thread_id: str, state: dict[str, Any]) -> None:
        """Save state under thread identifier."""
        ...
