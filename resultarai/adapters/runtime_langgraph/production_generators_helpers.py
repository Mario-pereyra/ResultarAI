"""Shared helpers for production graph generators.

Separated from production_generators.py to keep each module focused and testable.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any


def graph_messages_from_history(history: list[Any]) -> list[dict[str, Any]]:
    """Convert DB Message objects to the graph's message format.

    Each message gets a deterministic ID based on its position in the history,
    and a parent_id chain matching the history order.
    """
    messages: list[dict[str, Any]] = []
    for i, msg in enumerate(history):
        messages.append(
            {
                "id": f"hist_{i}",
                "role": msg.role,
                "content": msg.content,
                "parent_id": f"hist_{i - 1}" if i > 0 else None,
                "created_at": msg.created_at,
            }
        )
    return messages


def build_prompt(history: list[Any], data_declaration: str) -> str:
    """Build the LLM prompt from the last user message, with anti-injection prefix.

    Prepends the data-not-instruction declaration to the prompt so the model
    knows that <adjunto> content is data, not instructions (static system prompt
    requirement from the d14 spec).

    `data_declaration` is injected from the app layer to avoid an adapters -> app
    import violation.
    """
    last_content = ""
    for msg in reversed(history):
        if msg.role == "user":
            last_content = msg.content
            break
    return f"{data_declaration}\n\n{last_content}"


def response_from_graph_result(result: dict[str, Any], strip_marker: Callable[[str], str]) -> str:
    """Extract and clean the response text from a graph invocation result.

    Strips the escalation marker (regla dura del change: never persist or deliver
    the literal marker to the client, even on the synchronous path).

    `strip_marker` is injected from the app layer to avoid an adapters -> app
    import violation.
    """
    response = result.get("response")
    if response is None:
        status = result.get("status", "unknown")
        raise RuntimeError(
            f"Graph did not produce a response (status={status}). "
            "The Policy Gate may have denied the turn."
        )
    return strip_marker(response.text)
