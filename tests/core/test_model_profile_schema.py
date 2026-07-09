"""Tests for the ModelProfile Pydantic schema validation."""

import pytest
from pydantic import ValidationError

from resultarai.core.model_profile import ModelProfile


def test_valid_model_profile() -> None:
    """Verify that a valid profile passes validation and exposes correct values."""
    profile = ModelProfile(
        id="gpt_4o",
        provider="openai",
        model="gpt-4o-2024-05-13",
        parameters={"temperature": 0.5, "max_tokens": 100},
        cache_hit_rate=0.0000025,
        cache_miss_rate=0.000005,
    )
    assert profile.id == "gpt_4o"
    assert profile.provider == "openai"
    assert profile.model == "gpt-4o-2024-05-13"
    assert profile.parameters == {"temperature": 0.5, "max_tokens": 100}
    assert profile.cache_hit_rate == 0.0000025
    assert profile.cache_miss_rate == 0.000005


def test_valid_model_profile_default_parameters() -> None:
    """Verify that parameters default to an empty dictionary."""
    profile = ModelProfile(
        id="claude_3_opus",
        provider="anthropic",
        model="claude-3-opus-20240229",
        cache_hit_rate=0.0,
        cache_miss_rate=0.0,
    )
    assert profile.parameters == {}


def test_invalid_profile_missing_tariffs() -> None:
    """Verify validation fails if cache tariffs are missing."""
    with pytest.raises(ValidationError) as exc_info:
        ModelProfile(  # type: ignore[call-arg]
            id="gpt_4o",
            provider="openai",
            model="gpt-4o",
        )
    assert "cache_hit_rate" in str(exc_info.value)
    assert "cache_miss_rate" in str(exc_info.value)


def test_invalid_profile_empty_provider_and_model() -> None:
    """Verify validation fails if provider or model are empty strings."""
    with pytest.raises(ValidationError) as exc_info:
        ModelProfile(
            id="gpt_4o",
            provider="",
            model="gpt-4o",
            cache_hit_rate=0.0,
            cache_miss_rate=0.0,
        )
    assert "provider" in str(exc_info.value)

    with pytest.raises(ValidationError) as exc_info:
        ModelProfile(
            id="gpt_4o",
            provider="openai",
            model="",
            cache_hit_rate=0.0,
            cache_miss_rate=0.0,
        )
    assert "model" in str(exc_info.value)


def test_invalid_id_patterns() -> None:
    """Verify validation fails for invalid id patterns (non snake_case)."""
    invalid_ids = ["GPT-4", "gpt-4o-mini", "gpt_4o_mini!", "", "123model"]
    for invalid_id in invalid_ids:
        with pytest.raises(ValidationError):
            ModelProfile(
                id=invalid_id,
                provider="openai",
                model="gpt-4o",
                cache_hit_rate=0.0,
                cache_miss_rate=0.0,
            )


def test_strict_mode_rejects_coercions() -> None:
    """Verify that strict mode rejects implicit conversions and extra fields."""
    # Extra field forbidden
    with pytest.raises(ValidationError) as exc_info:
        ModelProfile(
            id="gpt_4o",
            provider="openai",
            model="gpt-4o",
            cache_hit_rate=0.0,
            cache_miss_rate=0.0,
            extra_arg="not allowed",  # type: ignore[call-arg]
        )
    assert "extra_arg" in str(exc_info.value)

    # String instead of float for tariff
    with pytest.raises(ValidationError):
        ModelProfile(
            id="gpt_4o",
            provider="openai",
            model="gpt-4o",
            cache_hit_rate="0.0",  # type: ignore[arg-type]
            cache_miss_rate=0.0,
        )

    # Integer instead of string for provider
    with pytest.raises(ValidationError):
        ModelProfile(
            id="gpt_4o",
            provider=123,  # type: ignore[arg-type]
            model="gpt-4o",
            cache_hit_rate=0.0,
            cache_miss_rate=0.0,
        )
