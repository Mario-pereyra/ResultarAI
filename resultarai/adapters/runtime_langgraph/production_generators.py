"""Production generators wiring b06 runtime (default_chat_graph) with b05 gateway (LiteLLM).

Composes the LangGraph default_chat_graph with the LiteLLM client and the Policy Gate
to produce the `ResponseGenerator` and `StreamingResponseGenerator` callables expected
by the chat endpoints (resultarai/app/api/chat.py and chat_stream.py).

The graph's `respond` node calls `llm_port.generate(prompt=prompt, fallback_cascade=[...])`.
This module:
  1. Converts DB history messages to the graph's message format.
  2. Builds the prompt from the last user message.
  3. Prepends the data-not-instruction declaration (d14) to the prompt.
  4. Invokes the graph with the LLM port, policy port, and registries.
  5. Extracts the response text and metadata from the graph result.

Note: `data_declaration` and `strip_marker` are injected from the app layer to respect
the import hierarchy (adapters cannot import from app).

The streaming generator yields raw dicts instead of `TurnFragment`/`TurnCompletion` to
avoid importing from `app/use_cases/chat/streaming.py`. The app layer's override function
wraps them in the typed objects expected by the `StreamingResponseGenerator` protocol.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any

from langchain_core.runnables import RunnableConfig

from resultarai.adapters.runtime_langgraph.default_chat_graph import (
    GraphState,
    default_chat_graph,
)
from resultarai.adapters.runtime_langgraph.production_generators_helpers import (
    build_prompt,
    graph_messages_from_history,
    response_from_graph_result,
)
from resultarai.core.ports.llm import LLMPort
from resultarai.core.registries import Registries


class _PolicyGateAdapter:
    """Wraps the pure policy_gate function as a PolicyPort-compatible object.

    The graph nodes call `policy_port.evaluate(request, active_policies)`, but
    `policy_gate` is a plain function. This adapter bridges the gap without
    violating layer boundaries (adapters can import from core).
    """

    def __init__(self, gate_fn: Any) -> None:
        self._gate_fn = gate_fn

    def evaluate(self, request: Any, active_policies: list[Any]) -> Any:
        return self._gate_fn(request, active_policies)


def _invoke_graph(
    session: Any,
    history: list[Any],
    llm_port: LLMPort,
    registries: Registries,
    data_declaration: str,
    strip_marker: Callable[[str], str],
) -> tuple[str, dict[str, Any]]:
    """Shared graph invocation logic for sync and streaming generators.

    Returns (cleaned_text, raw_result_dict).
    """
    prompt = build_prompt(history, data_declaration)
    messages = graph_messages_from_history(history)

    initial_state: GraphState = {
        "thread_id": session.id,
        "user": str(session.owner_user_id),
        "tenant": None,
        "agent": session.agent_id or "default_chat",
        "environment": "production",
        "messages": messages,
        "already_compacted": False,
        "model_profile_id": session.model_profile,
        "model_profile_window": 0,
        "prompt": prompt,
        "status": "active",
        "intent": "",
        "audit_events": [],
    }

    from resultarai.core.policy import policy_gate

    config: RunnableConfig = {
        "configurable": {
            "policy_port": _PolicyGateAdapter(policy_gate),
            "llm_port": llm_port,
            "trace_port": None,
            "state_port": None,
            "registries": registries,
        }
    }

    result = default_chat_graph.invoke(initial_state, config=config)
    text = response_from_graph_result(result, strip_marker)
    return text, result


def build_sync_graph_runner(
    llm_port: LLMPort,
    registries: Registries,
    *,
    data_declaration: str,
    strip_marker: Callable[[str], str],
) -> Any:
    """Build a synchronous `ResponseGenerator` backed by the default_chat_graph."""

    def _generate(*, session: Any, history: Any) -> str:
        text, _result = _invoke_graph(
            session, history, llm_port, registries, data_declaration, strip_marker
        )
        return text

    return _generate


def build_streaming_graph_runner(
    llm_port: LLMPort,
    registries: Registries,
    *,
    data_declaration: str,
    strip_marker: Callable[[str], str],
) -> Any:
    """Build a raw streaming generator backed by the default_chat_graph.

    Yields dicts with a "type" key:
      - {"type": "fragment", "text": str}
      - {"type": "completion", "model_profile_id": str, "is_alternate_model": bool, ...}

    The app layer wraps these in TurnFragment/TurnCompletion to satisfy the
    StreamingResponseGenerator protocol.
    """

    def _generate(*, session: Any, history: Any) -> Iterator[dict[str, Any]]:
        text, result = _invoke_graph(
            session, history, llm_port, registries, data_declaration, strip_marker
        )
        yield {"type": "fragment", "text": text}

        response = result.get("response")
        yield {
            "type": "completion",
            "model_profile_id": result.get("model_profile_id", session.model_profile),
            "is_alternate_model": response.is_alternate_model if response is not None else False,
            "primary_model_profile_id": (
                response.primary_model_profile_id if response is not None else None
            ),
            "fallback_reason": response.fallback_reason if response is not None else None,
            "cache_hit_tokens": response.cache_hit_tokens if response is not None else None,
            "cache_miss_tokens": response.cache_miss_tokens if response is not None else None,
            "cost_usd": response.cost_usd if response is not None else None,
            "needs_pro": response.needs_pro if response is not None else False,
        }

    return _generate
