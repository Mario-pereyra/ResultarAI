"""Contract tests for Langfuse feedback/response feedback scoring."""

from resultarai.adapters.tracing_langfuse.client import MockLangfuse
from resultarai.adapters.tracing_langfuse.feedback import (
    query_regression_candidates,
    submit_feedback,
)


def test_positive_and_negative_feedback_scores() -> None:
    """Verify positive and negative scores are recorded with correct fields."""
    client = MockLangfuse()

    # Submit positive thumbs up (1)
    submit_feedback(
        trace_id="trace-1",
        value=1,
        comment="Great response!",
        client=client,
    )

    assert len(client.scores) == 1
    score1 = client.scores[0]
    assert score1["trace_id"] == "trace-1"
    assert score1["name"] == "user-thumbs"
    assert score1["value"] == 1
    assert score1["dataType"] == "BOOLEAN"
    assert score1["comment"] == "Great response!"
    assert "regression-candidate" not in score1.get("tags", [])

    # Submit negative thumbs down (0)
    submit_feedback(
        trace_id="trace-2",
        value=0,
        comment="Incorrect response.",
        client=client,
    )

    assert len(client.scores) == 2
    score2 = client.scores[1]
    assert score2["trace_id"] == "trace-2"
    assert score2["name"] == "user-thumbs"
    assert score2["value"] == 0
    assert score2["dataType"] == "BOOLEAN"
    assert score2["comment"] == "Incorrect response."


def test_regression_candidate_tagging() -> None:
    """Verify thumbs down with comment adds regression-candidate tag, others do not."""
    client = MockLangfuse()

    # Thumbs down (0) WITH comment -> regression-candidate tag
    submit_feedback(
        trace_id="trace-bad-comment",
        value=0,
        comment="This is wrong",
        client=client,
    )
    score1 = client.scores[0]
    assert "regression-candidate" in score1["tags"]
    assert "regression-candidate" in score1["metadata"]["tags"]

    # Thumbs down (0) WITHOUT comment -> NO tag
    submit_feedback(
        trace_id="trace-bad-no-comment",
        value=0,
        comment=None,
        client=client,
    )
    score2 = client.scores[1]
    assert "tags" not in score2 or "regression-candidate" not in score2.get("tags", [])

    # Thumbs up (1) WITH comment -> NO tag
    submit_feedback(
        trace_id="trace-good-comment",
        value=1,
        comment="This is awesome",
        client=client,
    )
    score3 = client.scores[2]
    assert "tags" not in score3 or "regression-candidate" not in score3.get("tags", [])


def test_append_only_score_updates() -> None:
    """Verify submitting feedback on same trace_id appends a new score (never mutates)."""
    client = MockLangfuse()

    # Submit feedback first time
    submit_feedback(
        trace_id="trace-1",
        value=0,
        comment="First try",
        client=client,
    )
    assert len(client.scores) == 1
    assert client.scores[0]["comment"] == "First try"

    # Submit feedback second time for same trace_id
    submit_feedback(
        trace_id="trace-1",
        value=1,
        comment="Correction: user changed their mind",
        client=client,
    )

    # Verify we now have TWO scores, and first score is unchanged
    assert len(client.scores) == 2
    assert client.scores[0]["comment"] == "First try"
    assert client.scores[1]["comment"] == "Correction: user changed their mind"


def test_query_regression_candidates() -> None:
    """Verify querying regression candidates retrieves only tagged ones."""
    client = MockLangfuse()

    submit_feedback(
        trace_id="trace-1",
        value=0,
        comment="Regression comment",
        client=client,
    )
    submit_feedback(
        trace_id="trace-2",
        value=1,
        comment="Good response comment",
        client=client,
    )
    submit_feedback(
        trace_id="trace-3",
        value=0,
        comment=None,  # No comment, so not a candidate
        client=client,
    )

    candidates = query_regression_candidates(client=client)

    assert len(candidates) == 1
    assert candidates[0]["trace_id"] == "trace-1"
    assert candidates[0]["comment"] == "Regression comment"
