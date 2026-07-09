"""Runtime LangGraph adapter package for ResultarAI."""

from typing import Any

from resultarai.adapters.runtime_langgraph.default_chat_graph import (
    GraphState,
    default_chat_graph,
)

__all__ = [
    "GraphState",
    "default_chat_graph",
    "resolve_graph",
]

_GRAPHS = {
    "default_chat_graph": default_chat_graph,
    "default_chat": default_chat_graph,
}


def resolve_graph(name: str) -> Any:
    """Dynamically resolve a LangGraph by name."""
    return _GRAPHS.get(name)
