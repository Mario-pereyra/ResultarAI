"""Langfuse client initialization and utilities for ResultarAI."""

import hashlib
import os
from typing import Any

from langfuse import Langfuse


def mask_user_identity(user_id: str) -> str:
    """Mask user identity using a stable SHA-256 hash to ensure PII is protected."""
    if not user_id:
        return ""
    return hashlib.sha256(user_id.encode("utf-8")).hexdigest()


class MockSpan:
    """Mock observation span for Langfuse client."""

    def __init__(self, span_id: str, trace_id: str, client: "MockLangfuse") -> None:
        self.id = span_id
        self.trace_id = trace_id
        self.client = client

    def update(self, **kwargs: Any) -> None:
        """Update span values in mock storage."""
        trace = self.client.traces.get(self.trace_id)
        if trace:
            for span in trace.get("spans", []):
                if span.get("id") == self.id:
                    span.update(kwargs)
                    break


class MockTrace:
    """Mock trace for Langfuse client."""

    def __init__(self, trace_id: str, client: "MockLangfuse") -> None:
        self.id = trace_id
        self.client = client

    def span(self, **kwargs: Any) -> MockSpan:
        """Create a mock span under the trace."""
        existing_spans = self.client.traces[self.id].get("spans", [])
        span_id = kwargs.get("id") or f"mock-span-{len(existing_spans) + 1}"
        span_data = {
            "id": span_id,
            "name": kwargs.get("name"),
            "input": kwargs.get("input"),
            "output": kwargs.get("output"),
            "metadata": kwargs.get("metadata", {}),
            "level": kwargs.get("level"),
            "status_message": kwargs.get("status_message"),
        }
        self.client.traces[self.id].setdefault("spans", []).append(span_data)
        return MockSpan(span_id, self.id, self.client)

    def event(self, **kwargs: Any) -> dict[str, Any]:
        """Create a mock event under the trace."""
        existing_events = self.client.traces[self.id].get("events", [])
        event_id = kwargs.get("id") or f"mock-event-{len(existing_events) + 1}"
        event_data = {
            "id": event_id,
            "name": kwargs.get("name"),
            "input": kwargs.get("input"),
            "output": kwargs.get("output"),
            "metadata": kwargs.get("metadata", {}),
        }
        self.client.traces[self.id].setdefault("events", []).append(event_data)
        return event_data

    def generation(self, **kwargs: Any) -> MockSpan:
        """Create a mock generation span under the trace."""
        existing_spans = self.client.traces[self.id].get("spans", [])
        span_id = kwargs.get("id") or f"mock-span-{len(existing_spans) + 1}"
        span_data = {
            "id": span_id,
            "name": kwargs.get("name"),
            "input": kwargs.get("input"),
            "output": kwargs.get("output"),
            "metadata": kwargs.get("metadata", {}),
            "level": kwargs.get("level"),
            "status_message": kwargs.get("status_message"),
            "model": kwargs.get("model"),
            "usage": kwargs.get("usage", {}),
            "cost": kwargs.get("cost"),
        }
        self.client.traces[self.id].setdefault("spans", []).append(span_data)
        return MockSpan(span_id, self.id, self.client)

    def update(self, **kwargs: Any) -> None:
        """Update trace values in mock storage."""
        trace = self.client.traces.get(self.id)
        if trace:
            trace.update(kwargs)


class MockLangfuse:
    """Mock Langfuse client for testing/simulated mode."""

    def __init__(
        self,
        public_key: str | None = None,
        secret_key: str | None = None,
        host: str | None = None,
    ) -> None:
        self.public_key = public_key
        self.secret_key = secret_key
        self.host = host
        self.traces: dict[str, dict[str, Any]] = {}
        self.scores: list[dict[str, Any]] = []

    def mask_user_identity(self, user_id: str) -> str:
        """Mask user identity."""
        return mask_user_identity(user_id)

    def trace(self, **kwargs: Any) -> MockTrace:
        """Initialize a new trace in the mock client."""
        trace_id = kwargs.get("id") or f"mock-trace-{len(self.traces) + 1}"
        user_id = kwargs.get("user_id")

        self.traces[trace_id] = {
            "id": trace_id,
            "name": kwargs.get("name"),
            "user_id": user_id,
            "session_id": kwargs.get("session_id"),
            "metadata": kwargs.get("metadata", {}),
            "tags": kwargs.get("tags", []),
            "input": kwargs.get("input"),
            "output": kwargs.get("output"),
            "spans": [],
            "events": [],
        }
        return MockTrace(trace_id, self)

    def score(self, **kwargs: Any) -> dict[str, Any]:
        """Create a score in the mock client."""
        self.scores.append(kwargs)
        return kwargs


def get_langfuse_client(mock_mode: bool | None = None) -> Any:
    """Initialize and configure the Langfuse client.

    Raises:
        ValueError: If credentials are missing and we are not in mock/test mode.
    """
    is_mock = mock_mode
    if is_mock is None:
        is_mock = (
            os.environ.get("LANGFUSE_MOCK", "").lower() in ("true", "1", "yes")
            or "PYTEST_CURRENT_TEST" in os.environ
        )

    public_key = os.environ.get("LANGFUSE_PUBLIC_KEY")
    secret_key = os.environ.get("LANGFUSE_SECRET_KEY")
    host = os.environ.get("LANGFUSE_HOST")

    if is_mock:
        mock_client = MockLangfuse(public_key=public_key, secret_key=secret_key, host=host)
        return mock_client

    if not public_key or not secret_key or not host:
        raise ValueError(
            "Langfuse credentials missing. Please set LANGFUSE_PUBLIC_KEY, "
            "LANGFUSE_SECRET_KEY, and LANGFUSE_HOST, or enable mock mode."
        )

    real_client = Langfuse(
        public_key=public_key,
        secret_key=secret_key,
        host=host,
    )
    # Integrate mask_user_identity with client
    real_client.mask_user_identity = mask_user_identity  # type: ignore[attr-defined]
    return real_client
