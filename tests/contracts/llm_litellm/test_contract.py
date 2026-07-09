"""Contract tests for the LiteLLM adapter client."""

import litellm
import pytest
from tests.contracts.llm_litellm.fake_provider import FakeProvider, ModelBehavior

from resultarai.adapters.llm_litellm.client import LiteLLMClient
from resultarai.core.model_profile import ModelProfile
from resultarai.core.ports.llm import LLMResponse
from resultarai.core.ports.llm_errors import LLMCascadeExhaustedError


@pytest.fixture
def test_profiles() -> dict[str, ModelProfile]:
    """Provide a dictionary of model profiles for testing."""
    return {
        "profile_1": ModelProfile(
            id="profile_1",
            provider="openai",
            model="gpt-4o",
            parameters={"temperature": 0.0},
            cache_hit_rate=0.000002,
            cache_miss_rate=0.000005,
            active=True,
        ),
        "profile_2": ModelProfile(
            id="profile_2",
            provider="anthropic",
            model="claude-3-5-haiku-20241022",
            parameters={"temperature": 0.5},
            cache_hit_rate=0.000001,
            cache_miss_rate=0.000003,
            active=True,
        ),
        "profile_inactive": ModelProfile(
            id="profile_inactive",
            provider="openai",
            model="gpt-3.5-turbo",
            parameters={},
            cache_hit_rate=0.0,
            cache_miss_rate=0.0,
            active=False,
        ),
    }


@pytest.fixture
def fake_provider(monkeypatch: pytest.MonkeyPatch) -> FakeProvider:
    """Fixture to mock litellm.completion and return a FakeProvider instance."""
    provider = FakeProvider()
    monkeypatch.setattr(litellm, "completion", provider.completion)
    return provider


def test_client_first_profile_success(
    test_profiles: dict[str, ModelProfile], fake_provider: FakeProvider
) -> None:
    """Verify that if the first profile in the cascade succeeds, it is returned directly."""
    fake_provider.configure_behavior(
        "gpt-4o",
        ModelBehavior(
            response_text="Hello from primary",
            prompt_tokens=100,
            completion_tokens=20,
            cached_tokens=40,
        ),
    )

    client = LiteLLMClient(model_profiles=test_profiles)
    response = client.generate("Test prompt", fallback_cascade=["profile_1", "profile_2"])

    assert isinstance(response, LLMResponse)
    assert response.text == "Hello from primary"
    assert response.model_profile_id == "profile_1"
    assert response.is_alternate_model is False
    assert response.primary_model_profile_id is None
    assert response.fallback_reason is None

    # Verify call history
    assert len(fake_provider.calls) == 1
    assert fake_provider.calls[0]["model"] == "gpt-4o"
    assert fake_provider.calls[0]["kwargs"] == {"temperature": 0.0}


def test_client_fallback_to_second_profile(
    test_profiles: dict[str, ModelProfile], fake_provider: FakeProvider
) -> None:
    """Verify fallback to second profile when first profile raises an exception."""
    # Configure profile 1 to raise an exception, profile 2 to succeed
    fake_provider.configure_behavior(
        "gpt-4o", ModelBehavior(exception=RuntimeError("Connection timed out"))
    )
    fake_provider.configure_behavior(
        "claude-3-5-haiku-20241022",
        ModelBehavior(
            response_text="Hello from secondary",
            prompt_tokens=200,
            completion_tokens=50,
            cache_read_input_tokens=100,
        ),
    )

    client = LiteLLMClient(model_profiles=test_profiles)
    response = client.generate("Test prompt", fallback_cascade=["profile_1", "profile_2"])

    assert isinstance(response, LLMResponse)
    assert response.text == "Hello from secondary"
    assert response.model_profile_id == "profile_2"
    assert response.is_alternate_model is True
    assert response.primary_model_profile_id == "profile_1"
    assert "Connection timed out" in str(response.fallback_reason)

    # Verify both calls were recorded
    assert len(fake_provider.calls) == 2
    assert fake_provider.calls[0]["model"] == "gpt-4o"
    assert fake_provider.calls[1]["model"] == "claude-3-5-haiku-20241022"
    assert fake_provider.calls[1]["kwargs"] == {"temperature": 0.5}


def test_client_cascade_exhausted_error(
    test_profiles: dict[str, ModelProfile], fake_provider: FakeProvider
) -> None:
    """Verify LLMCascadeExhaustedError is raised when all profiles in the cascade fail."""
    fake_provider.configure_behavior("gpt-4o", ModelBehavior(exception=ValueError("Bad request")))
    fake_provider.configure_behavior(
        "claude-3-5-haiku-20241022", ModelBehavior(exception=RuntimeError("Rate limit exceeded"))
    )

    client = LiteLLMClient(model_profiles=test_profiles)

    with pytest.raises(LLMCascadeExhaustedError) as exc_info:
        client.generate("Test prompt", fallback_cascade=["profile_1", "profile_2"])

    error = exc_info.value
    assert error.attempted_profiles == ["profile_1", "profile_2"]
    assert "Bad request" in error.failures["profile_1"]
    assert "Rate limit exceeded" in error.failures["profile_2"]


def test_client_skips_missing_or_inactive_profiles(
    test_profiles: dict[str, ModelProfile], fake_provider: FakeProvider
) -> None:
    """Verify nonexistent and inactive profiles are recorded as failures, and cascade continues."""
    fake_provider.configure_behavior(
        "claude-3-5-haiku-20241022",
        ModelBehavior(
            response_text="Success on active fallback",
            prompt_tokens=100,
            completion_tokens=20,
        ),
    )

    client = LiteLLMClient(model_profiles=test_profiles)
    # profile_missing doesn't exist; profile_inactive is inactive
    response = client.generate(
        "Test prompt",
        fallback_cascade=["profile_missing", "profile_inactive", "profile_2"],
    )

    assert response.text == "Success on active fallback"
    assert response.model_profile_id == "profile_2"
    assert response.is_alternate_model is True
    assert response.primary_model_profile_id == "profile_missing"
    assert "not found" in str(response.fallback_reason)

    # Only profile_2 should have reached the provider
    assert len(fake_provider.calls) == 1
    assert fake_provider.calls[0]["model"] == "claude-3-5-haiku-20241022"


def test_client_cache_tokens_openai_style(
    test_profiles: dict[str, ModelProfile], fake_provider: FakeProvider
) -> None:
    """Verify cache hit and miss extraction from OpenAI style usage metadata."""
    fake_provider.configure_behavior(
        "gpt-4o",
        ModelBehavior(
            prompt_tokens=150,
            completion_tokens=30,
            cached_tokens=80,
        ),
    )

    client = LiteLLMClient(model_profiles=test_profiles)
    response = client.generate("Test prompt", fallback_cascade=["profile_1"])

    assert response.cache_hit_tokens == 80
    assert response.cache_miss_tokens == 70  # 150 - 80


def test_client_cache_tokens_anthropic_style(
    test_profiles: dict[str, ModelProfile], fake_provider: FakeProvider
) -> None:
    """Verify cache hit and miss extraction from Anthropic style usage metadata."""
    fake_provider.configure_behavior(
        "gpt-4o",
        ModelBehavior(
            prompt_tokens=150,
            completion_tokens=30,
            cache_read_input_tokens=90,
        ),
    )

    client = LiteLLMClient(model_profiles=test_profiles)
    response = client.generate("Test prompt", fallback_cascade=["profile_1"])

    assert response.cache_hit_tokens == 90
    assert response.cache_miss_tokens == 60  # 150 - 90


def test_client_absent_cache_counters(
    test_profiles: dict[str, ModelProfile], fake_provider: FakeProvider
) -> None:
    """Verify that absent cache counters report as None (not 0)."""
    fake_provider.configure_behavior(
        "gpt-4o",
        ModelBehavior(
            prompt_tokens=100,
            completion_tokens=20,
            absent_cache=True,
        ),
    )

    client = LiteLLMClient(model_profiles=test_profiles)
    response = client.generate("Test prompt", fallback_cascade=["profile_1"])

    assert response.cache_hit_tokens is None
    assert response.cache_miss_tokens is None


def test_client_cost_calculation(
    test_profiles: dict[str, ModelProfile], fake_provider: FakeProvider
) -> None:
    """Verify cost calculation under both present and absent cache counter scenarios."""
    # Scenario A: Cache counters present (OpenAI style)
    # hit rate = 0.000002, miss rate = 0.000005
    # hit tokens = 60, miss tokens = 40 (total 100)
    # Expected cost = 60 * 0.000002 + 40 * 0.000005 = 0.00012 + 0.00020 = 0.00032
    fake_provider.configure_behavior(
        "gpt-4o",
        ModelBehavior(
            prompt_tokens=100,
            completion_tokens=10,
            cached_tokens=60,
        ),
    )

    client = LiteLLMClient(model_profiles=test_profiles)
    response_present = client.generate("Test prompt", fallback_cascade=["profile_1"])
    assert pytest.approx(response_present.cost_usd) == 0.00032

    # Scenario B: Cache counters absent
    # prompt tokens = 100, miss rate = 0.000005
    # Expected cost = 100 * 0.000005 = 0.0005
    fake_provider.configure_behavior(
        "gpt-4o",
        ModelBehavior(
            prompt_tokens=100,
            completion_tokens=10,
            absent_cache=True,
        ),
    )

    response_absent = client.generate("Test prompt", fallback_cascade=["profile_1"])
    assert pytest.approx(response_absent.cost_usd) == 0.0005


def test_client_escalation_detection_marker_present(
    test_profiles: dict[str, ModelProfile], fake_provider: FakeProvider
) -> None:
    """Verify that NEEDS_PRO marker outside adjuntos triggers needs_pro=True."""
    fake_provider.configure_behavior(
        "gpt-4o",
        ModelBehavior(
            response_text="Some text <<<NEEDS_PRO>>> other text",
        ),
    )

    client = LiteLLMClient(model_profiles=test_profiles)
    response = client.generate("Test prompt", fallback_cascade=["profile_1"])
    assert response.needs_pro is True


def test_client_escalation_detection_marker_absent(
    test_profiles: dict[str, ModelProfile], fake_provider: FakeProvider
) -> None:
    """Verify that absence of NEEDS_PRO marker returns needs_pro=False."""
    fake_provider.configure_behavior(
        "gpt-4o",
        ModelBehavior(
            response_text="Some text without marker",
        ),
    )

    client = LiteLLMClient(model_profiles=test_profiles)
    response = client.generate("Test prompt", fallback_cascade=["profile_1"])
    assert response.needs_pro is False


def test_client_escalation_detection_marker_inside_adjunto(
    test_profiles: dict[str, ModelProfile], fake_provider: FakeProvider
) -> None:
    """Verify that NEEDS_PRO marker inside a well-formed adjunto does NOT trigger needs_pro."""
    fake_provider.configure_behavior(
        "gpt-4o",
        ModelBehavior(
            response_text="<adjunto id='att_123'> <<<NEEDS_PRO>>> </adjunto> normal text",
        ),
    )

    client = LiteLLMClient(model_profiles=test_profiles)
    response = client.generate("Test prompt", fallback_cascade=["profile_1"])
    assert response.needs_pro is False


def test_client_escalation_detection_marker_inside_unclosed_adjunto(
    test_profiles: dict[str, ModelProfile], fake_provider: FakeProvider
) -> None:
    """Verify that unclosed adjunto triggers fail-closed behavior (removes marker)."""
    fake_provider.configure_behavior(
        "gpt-4o",
        ModelBehavior(
            response_text="<adjunto id='att_123'> content and then <<<NEEDS_PRO>>>",
        ),
    )

    client = LiteLLMClient(model_profiles=test_profiles)
    response = client.generate("Test prompt", fallback_cascade=["profile_1"])
    assert response.needs_pro is False


def test_client_escalation_detection_faked_closing_tag(
    test_profiles: dict[str, ModelProfile], fake_provider: FakeProvider
) -> None:
    """Verify faked close tag attempt inside content is handled safely (removes marker)."""
    fake_provider.configure_behavior(
        "gpt-4o",
        ModelBehavior(
            response_text=(
                "<adjunto id='att_123'> content </adjunto> <<<NEEDS_PRO>>> </adjunto> outside text"
            ),
        ),
    )

    client = LiteLLMClient(model_profiles=test_profiles)
    response = client.generate("Test prompt", fallback_cascade=["profile_1"])
    assert response.needs_pro is False


def test_client_escalation_disabled_by_kwarg(
    test_profiles: dict[str, ModelProfile], fake_provider: FakeProvider
) -> None:
    """Verify that if escalation is disabled via kwarg, NEEDS_PRO is ignored."""
    fake_provider.configure_behavior(
        "gpt-4o",
        ModelBehavior(
            response_text="<<<NEEDS_PRO>>>",
        ),
    )

    client = LiteLLMClient(model_profiles=test_profiles)
    response = client.generate(
        "Test prompt",
        fallback_cascade=["profile_1"],
        escalation_enabled=False,
    )
    assert response.needs_pro is False


class MockAgentEscalation:
    def __init__(self, enabled: bool) -> None:
        self.enabled = enabled


class MockAgent:
    def __init__(self, escalation_enabled: bool) -> None:
        self.escalation = MockAgentEscalation(enabled=escalation_enabled)


def test_client_escalation_disabled_by_agent_manifest(
    test_profiles: dict[str, ModelProfile], fake_provider: FakeProvider
) -> None:
    """Verify that if escalation is disabled in the agent manifest object, NEEDS_PRO is ignored."""
    fake_provider.configure_behavior(
        "gpt-4o",
        ModelBehavior(
            response_text="<<<NEEDS_PRO>>>",
        ),
    )

    client = LiteLLMClient(model_profiles=test_profiles)

    # Escalation disabled
    response_disabled = client.generate(
        "Test prompt",
        fallback_cascade=["profile_1"],
        agent=MockAgent(escalation_enabled=False),
    )
    assert response_disabled.needs_pro is False

    # Escalation enabled
    response_enabled = client.generate(
        "Test prompt",
        fallback_cascade=["profile_1"],
        agent=MockAgent(escalation_enabled=True),
    )
    assert response_enabled.needs_pro is True
