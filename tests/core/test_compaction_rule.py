"""Tests for context window compaction rule."""

from resultarai.core.routing import should_compact


def test_should_compact_already_compacted() -> None:
    """Verify that if compaction already occurred in this session, it won't fire again."""
    # Even if usage is at 95% of context window
    assert (
        should_compact(session_context_usage=95, model_profile_window=100, already_compacted=True)
        is False
    )


def test_should_compact_exact_threshold() -> None:
    """Verify that compaction is triggered exactly at 80% of context window usage."""
    assert (
        should_compact(session_context_usage=80, model_profile_window=100, already_compacted=False)
        is True
    )


def test_should_compact_above_threshold() -> None:
    """Verify that compaction is triggered when usage is above 80%."""
    assert (
        should_compact(session_context_usage=81, model_profile_window=100, already_compacted=False)
        is True
    )


def test_should_compact_below_threshold() -> None:
    """Verify that compaction is not triggered when usage is below 80%."""
    assert (
        should_compact(session_context_usage=79, model_profile_window=100, already_compacted=False)
        is False
    )


def test_should_compact_zero_and_negative_windows() -> None:
    """Verify that compaction returns False if model context window is 0 or negative."""
    # Zero window
    assert (
        should_compact(session_context_usage=10, model_profile_window=0, already_compacted=False)
        is False
    )

    # Negative window
    assert (
        should_compact(session_context_usage=10, model_profile_window=-10, already_compacted=False)
        is False
    )


def test_should_compact_zero_usage() -> None:
    """Verify that zero usage does not trigger compaction for a valid window."""
    assert (
        should_compact(session_context_usage=0, model_profile_window=100, already_compacted=False)
        is False
    )
