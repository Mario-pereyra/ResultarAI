"""Tests for the LLMResponse contract schema and validation logic."""

import pytest
from pydantic import ValidationError

from resultarai.core.ports.llm import LLMResponse


def test_llm_response_required_fields() -> None:
    """Verify that required fields must be present and have correct types."""
    # Valid minimal payload
    response = LLMResponse(
        text="Hello world",
        model_profile_id="gpt-4o",
        is_alternate_model=False,
    )
    assert response.text == "Hello world"
    assert response.model_profile_id == "gpt-4o"
    assert response.is_alternate_model is False

    # Missing text
    with pytest.raises(ValidationError) as exc_info:
        LLMResponse(  # type: ignore[call-arg]
            model_profile_id="gpt-4o",
            is_alternate_model=False,
        )
    assert "text" in str(exc_info.value)

    # Missing model_profile_id
    with pytest.raises(ValidationError) as exc_info:
        LLMResponse(  # type: ignore[call-arg]
            text="Hello world",
            is_alternate_model=False,
        )
    assert "model_profile_id" in str(exc_info.value)

    # Missing is_alternate_model
    with pytest.raises(ValidationError) as exc_info:
        LLMResponse(  # type: ignore[call-arg]
            text="Hello world",
            model_profile_id="gpt-4o",
        )
    assert "is_alternate_model" in str(exc_info.value)


def test_llm_response_default_values() -> None:
    """Verify that optional fields have the correct default values."""
    response = LLMResponse(
        text="Hello world",
        model_profile_id="gpt-4o",
        is_alternate_model=False,
    )
    assert response.primary_model_profile_id is None
    assert response.fallback_reason is None
    assert response.cache_hit_tokens is None
    assert response.cache_miss_tokens is None
    assert response.cost_usd is None
    assert response.needs_pro is False


def test_llm_response_strict_types() -> None:
    """Verify that type coercion is rejected under strict mode."""
    # Pydantic is configured with strict=True, so string instead of bool should fail.
    with pytest.raises(ValidationError):
        LLMResponse(
            text="Hello world",
            model_profile_id="gpt-4o",
            is_alternate_model="False",  # type: ignore[arg-type]
        )

    # float instead of int for cache tokens should fail
    with pytest.raises(ValidationError):
        LLMResponse(
            text="Hello world",
            model_profile_id="gpt-4o",
            is_alternate_model=False,
            cache_hit_tokens=12.5,  # type: ignore[arg-type]
        )


def test_llm_response_extra_fields_forbidden() -> None:
    """Verify that extra fields are forbidden in the model."""
    with pytest.raises(ValidationError) as exc_info:
        LLMResponse(
            text="Hello world",
            model_profile_id="gpt-4o",
            is_alternate_model=False,
            extra_field="not allowed",  # type: ignore[call-arg]
        )
    assert "extra_field" in str(exc_info.value)
    assert "Extra inputs are not permitted" in str(exc_info.value)


def test_llm_response_needs_pro_explicit_setting() -> None:
    """Verify that needs_pro can be set to True or False explicitly."""
    response_true = LLMResponse(
        text="Normal response text",
        model_profile_id="gpt-4o",
        is_alternate_model=False,
        needs_pro=True,
    )
    assert response_true.needs_pro is True

    response_false = LLMResponse(
        text="Normal response text <<<NEEDS_PRO>>>",
        model_profile_id="gpt-4o",
        is_alternate_model=False,
        needs_pro=False,
    )
    assert response_false.needs_pro is False
