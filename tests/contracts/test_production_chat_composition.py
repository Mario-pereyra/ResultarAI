"""Contract test verifying the production composition of the chat response generators.

Tests that the wiring of b06 runtime (default_chat_graph) + b05 gateway (LiteLLMClient)
+ Policy Gate + default_chat_policy manifest produces a valid response, using the
FakeProvider from the llm_litellm contract tests as the simulated LLM backend.
"""

from __future__ import annotations

from pathlib import Path

from resultarai.adapters.llm_litellm.client import LiteLLMClient
from resultarai.adapters.runtime_langgraph.production_generators import (
    build_streaming_graph_runner,
    build_sync_graph_runner,
)
from resultarai.adapters.runtime_langgraph.production_generators_helpers import (
    build_prompt,
    graph_messages_from_history,
)
from resultarai.app.attachments.spotlight import DATA_NOT_INSTRUCTION_DECLARATION
from resultarai.app.startup import bootstrap
from resultarai.app.use_cases.chat._marker import strip_escalation_marker
from resultarai.app.use_cases.chat.streaming import TurnCompletion, TurnFragment
from resultarai.core.model_profile import ModelProfile
from tests.contracts.llm_litellm.fake_provider import FakeProvider, ModelBehavior


class _FakeSession:
    """Minimal session-like object matching the fields used by the generators."""

    def __init__(self, model_profile: str = "test_profile") -> None:
        self.id = "session_test_001"
        self.owner_user_id = "user_test_001"
        self.agent_id = "default_chat"
        self.model_profile = model_profile


class _FakeMessage:
    """Minimal message-like object matching the fields used by history conversion."""

    def __init__(self, role: str, content: str) -> None:
        self.role = role
        self.content = content
        self.id = "msg_test"
        self.created_at = None


def test_sync_generator_composition() -> None:
    """Verify that the synchronous graph runner produces valid text through the full
    composition chain: FakeProvider -> LiteLLMClient -> default_chat_graph -> generator.
    """
    import litellm

    fake = FakeProvider()
    fake.configure_behavior(
        "fake/test-model",
        ModelBehavior(response_text="Production sync response from fake LLM"),
    )

    original_completion = litellm.completion
    litellm.completion = fake.completion
    try:
        llm_client = LiteLLMClient(
            model_profiles={
                "test_profile": ModelProfile(
                    id="test_profile",
                    provider="fake",
                    model="fake/test-model",
                    parameters={"temperature": 0.0, "max_tokens": 4096},
                    cache_hit_rate=0.0,
                    cache_miss_rate=0.0,
                    active=True,
                ),
            }
        )
        registries = bootstrap(Path("manifests"))

        generator = build_sync_graph_runner(
            llm_client,
            registries,
            data_declaration=DATA_NOT_INSTRUCTION_DECLARATION,
            strip_marker=strip_escalation_marker,
        )
        session = _FakeSession()
        history = [_FakeMessage("user", "¿Cuál es la capital de Bolivia?")]

        result = generator(session=session, history=history)

        assert isinstance(result, str)
        assert "Production sync response from fake LLM" in result
        assert len(fake.calls) == 1
    finally:
        litellm.completion = original_completion


def test_streaming_generator_composition() -> None:
    """Verify that the streaming graph runner produces a valid stream of
    raw dicts (fragment + completion) that can be wrapped in TurnFragment/TurnCompletion.
    """
    import litellm

    fake = FakeProvider()
    fake.configure_behavior(
        "fake/test-model",
        ModelBehavior(response_text="Streaming response from fake LLM"),
    )

    original_completion = litellm.completion
    litellm.completion = fake.completion
    try:
        llm_client = LiteLLMClient(
            model_profiles={
                "test_profile": ModelProfile(
                    id="test_profile",
                    provider="fake",
                    model="fake/test-model",
                    parameters={"temperature": 0.0, "max_tokens": 4096},
                    cache_hit_rate=0.0,
                    cache_miss_rate=0.0,
                    active=True,
                ),
            }
        )
        registries = bootstrap(Path("manifests"))

        generator = build_streaming_graph_runner(
            llm_client,
            registries,
            data_declaration=DATA_NOT_INSTRUCTION_DECLARATION,
            strip_marker=strip_escalation_marker,
        )
        session = _FakeSession()
        history = [_FakeMessage("user", "¿Cuál es la capital de Bolivia?")]

        raw_items = list(generator(session=session, history=history))

        # The adapter yields raw dicts; wrap them as the app layer does
        items: list[TurnFragment | TurnCompletion] = []
        for item in raw_items:
            if item["type"] == "fragment":
                items.append(TurnFragment(text=item["text"]))
            elif item["type"] == "completion":
                items.append(
                    TurnCompletion(
                        model_profile_id=item["model_profile_id"],
                        is_alternate_model=item["is_alternate_model"],
                        primary_model_profile_id=item.get("primary_model_profile_id"),
                        fallback_reason=item.get("fallback_reason"),
                        cache_hit_tokens=item.get("cache_hit_tokens"),
                        cache_miss_tokens=item.get("cache_miss_tokens"),
                        cost_usd=item.get("cost_usd"),
                        needs_pro=item.get("needs_pro", False),
                    )
                )

        assert len(items) >= 2
        assert isinstance(items[0], TurnFragment)
        assert "Streaming response from fake LLM" in items[0].text
        assert isinstance(items[-1], TurnCompletion)
        assert items[-1].model_profile_id == "test_profile"
        assert len(fake.calls) == 1
    finally:
        litellm.completion = original_completion


def test_default_chat_policy_passes_gate() -> None:
    """Verify that the default_chat_policy manifest authorizes the default_chat skill
    through the real Policy Gate (not a DummyPolicyPort).
    """
    from resultarai.core.manifests.base import RiskLevel
    from resultarai.core.policy import policy_gate
    from resultarai.core.policy.models import ActionRequest

    registries = bootstrap(Path("manifests"))
    active_policies = list(registries.policies.invocable())

    policy_ids = [p.id for p in active_policies]
    assert "default_chat_policy" in policy_ids

    request = ActionRequest(
        user="test_user",
        tenant=None,
        agent="default_chat",
        skill="default_chat",
        tool="",
        operation_type="read",
        risk_level=RiskLevel.LOW,
        environment="production",
    )

    decision = policy_gate(request, active_policies)
    assert decision.effect == "allow"


def test_helpers_build_prompt_includes_declaration() -> None:
    """Verify that build_prompt prepends DATA_NOT_INSTRUCTION_DECLARATION."""
    history = [_FakeMessage("user", "test message")]
    prompt = build_prompt(history, DATA_NOT_INSTRUCTION_DECLARATION)
    assert prompt.startswith(DATA_NOT_INSTRUCTION_DECLARATION)
    assert "test message" in prompt


def test_helpers_graph_messages_from_history() -> None:
    """Verify history-to-graph-messages conversion."""
    history = [
        _FakeMessage("user", "first"),
        _FakeMessage("assistant", "reply"),
        _FakeMessage("user", "second"),
    ]
    messages = graph_messages_from_history(history)

    assert len(messages) == 3
    assert messages[0]["role"] == "user"
    assert messages[0]["content"] == "first"
    assert messages[0]["parent_id"] is None
    assert messages[1]["role"] == "assistant"
    assert messages[1]["parent_id"] == "hist_0"
    assert messages[2]["role"] == "user"
    assert messages[2]["content"] == "second"
    assert messages[2]["parent_id"] == "hist_1"
