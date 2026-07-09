"""Tests for the LLM port exception hierarchy."""

from resultarai.core.ports.llm_errors import (
    LLMCascadeExhaustedError,
    LLMError,
    LLMProfileUnavailableError,
)


def test_llm_error_base() -> None:
    """Verify LLMError can be instantiated and behaves like a standard exception."""
    error = LLMError("General LLM failure")
    assert isinstance(error, Exception)
    assert str(error) == "General LLM failure"


def test_llm_profile_unavailable_error() -> None:
    """Verify LLMProfileUnavailableError exposes profile_id and subclasses LLMError."""
    error = LLMProfileUnavailableError(profile_id="gpt-4o", message="Custom message")
    assert isinstance(error, LLMError)
    assert error.profile_id == "gpt-4o"
    assert str(error) == "Custom message"

    # Default message test
    error_default = LLMProfileUnavailableError(profile_id="claude-3-opus")
    assert error_default.profile_id == "claude-3-opus"
    assert "claude-3-opus" in str(error_default)


def test_llm_cascade_exhausted_error() -> None:
    """Verify LLMCascadeExhaustedError exposes attributes and subclasses LLMError."""
    attempted = ["gpt-4o", "claude-3-haiku"]
    failures = {
        "gpt-4o": "Rate limit exceeded",
        "claude-3-haiku": "Service unavailable",
    }
    error = LLMCascadeExhaustedError(
        attempted_profiles=attempted,
        failures=failures,
        message="Cascade failed completely",
    )
    assert isinstance(error, LLMError)
    assert error.attempted_profiles == attempted
    assert error.failures == failures
    assert str(error) == "Cascade failed completely"

    # Default message test
    error_default = LLMCascadeExhaustedError(
        attempted_profiles=attempted,
        failures=failures,
    )
    assert error_default.attempted_profiles == attempted
    assert error_default.failures == failures
    assert "gpt-4o" in str(error_default)
    assert "claude-3-haiku" in str(error_default)
