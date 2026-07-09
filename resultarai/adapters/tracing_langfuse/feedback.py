"""Langfuse feedback adapter for ResultarAI."""

from typing import Any

from resultarai.adapters.tracing_langfuse.client import MockLangfuse, get_langfuse_client


def submit_feedback(
    trace_id: str,
    value: int,
    comment: str | None = None,
    prompt_version: str | None = None,
    client: Any = None,
) -> None:
    """Submit user feedback for a trace.

    Creates a score named "user-thumbs" with dataType="BOOLEAN" (value 1 or 0).
    If the value is 0 (thumbs down) and a comment is provided, tags it with "regression-candidate".
    """
    if client is None:
        client = get_langfuse_client()

    tags = []
    if value == 0 and comment is not None:
        tags.append("regression-candidate")

    kwargs: dict[str, Any] = {
        "trace_id": trace_id,
        "name": "user-thumbs",
        "value": value,
        "dataType": "BOOLEAN",
    }
    if comment is not None:
        kwargs["comment"] = comment
    if tags:
        kwargs["tags"] = tags
        kwargs["metadata"] = {"tags": tags}

    client.score(**kwargs)


def query_regression_candidates(client: Any = None) -> list[dict[str, Any]]:
    """Query all scores tagged as regression candidates."""
    if client is None:
        client = get_langfuse_client()

    # Handle Mock mode
    if isinstance(client, MockLangfuse):
        results = []
        for sc in client.scores:
            sc_tags = sc.get("tags") or []
            sc_metadata = sc.get("metadata") or {}
            meta_tags = sc_metadata.get("tags") or []
            if "regression-candidate" in sc_tags or "regression-candidate" in meta_tags:
                results.append(sc)
        return results

    # Handle Real Langfuse client
    results = []
    has_list_api = (
        hasattr(client, "api")
        and hasattr(client.api, "scores")
        and hasattr(client.api.scores, "list")
    )
    if has_list_api:
        scores_response = client.api.scores.list()
        for sc in scores_response.data:
            sc_tags = getattr(sc, "tags", []) or []
            sc_metadata = getattr(sc, "metadata", {}) or {}

            meta_tags = []
            if isinstance(sc_metadata, dict) or hasattr(sc_metadata, "get"):
                meta_tags = sc_metadata.get("tags") or []

            if "regression-candidate" in sc_tags or "regression-candidate" in meta_tags:
                if hasattr(sc, "model_dump"):
                    results.append(sc.model_dump())
                elif hasattr(sc, "dict"):
                    results.append(sc.dict())
                else:
                    results.append(dict(sc))
    return results
