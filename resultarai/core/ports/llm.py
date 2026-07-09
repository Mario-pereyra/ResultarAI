"""LLMPort Protocol definition."""

from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict


class LLMResponse(BaseModel):
    """Output contract for LLM generation."""

    model_config = ConfigDict(strict=True, extra="forbid")

    text: str
    model_profile_id: str
    is_alternate_model: bool
    primary_model_profile_id: str | None = None
    fallback_reason: str | None = None
    cache_hit_tokens: int | None = None
    cache_miss_tokens: int | None = None
    cost_usd: float | None = None
    needs_pro: bool = False


class LLMPort(Protocol):
    """Protocol for LLM interactions.

    Will be implemented by the model gateway adapter in b05.
    """

    def generate(self, prompt: str, **kwargs: Any) -> LLMResponse:
        """Generate response text from a given prompt."""
        ...
