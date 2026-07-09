"""LLMPort Protocol definition."""

from typing import Any, Protocol


class LLMPort(Protocol):
    """Protocol for LLM interactions.

    Will be implemented by the model gateway adapter in b05.
    """

    def generate(self, prompt: str, **kwargs: Any) -> str:
        """Generate response text from a given prompt."""
        ...
