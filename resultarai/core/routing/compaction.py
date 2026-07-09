"""Compaction rules for managing LLM context window size."""

from __future__ import annotations


def should_compact(
    session_context_usage: int, model_profile_window: int, already_compacted: bool
) -> bool:
    """Determine whether the conversation history should be compacted.

    Returns True if already_compacted is False, model_profile_window > 0, and
    session_context_usage is at least 80% of model_profile_window.
    """
    if already_compacted:
        return False

    if model_profile_window <= 0:
        return False

    # 80% of model_profile_window
    threshold = model_profile_window * 0.8
    return session_context_usage >= threshold
