"""Fixture creating a session state near the context window limit for testing compaction."""

import datetime
import uuid
from typing import Any

import pytest


def create_session_state(
    token_count: int,
    already_compacted: bool = False,
    model_profile: str = "profile_1",
) -> dict[str, Any]:
    """Helper to generate a mock session state with a specific size/token count."""
    messages = []
    parent_id = None

    # We can create a few messages to distribute the content size
    msg_id_1 = str(uuid.uuid4())
    messages.append(
        {
            "id": msg_id_1,
            "role": "user",
            "content": "x" * (token_count // 2),
            "parent_id": parent_id,
            "created_at": datetime.datetime.now(datetime.UTC).replace(tzinfo=None),
        }
    )

    msg_id_2 = str(uuid.uuid4())
    messages.append(
        {
            "id": msg_id_2,
            "role": "assistant",
            "content": "y" * (token_count - (token_count // 2)),
            "parent_id": msg_id_1,
            "created_at": datetime.datetime.now(datetime.UTC).replace(tzinfo=None),
        }
    )

    return {
        "model_profile": model_profile,
        "already_compacted": already_compacted,
        "messages": messages,
    }


@pytest.fixture
def session_state_near_limit() -> dict[str, Any]:
    """Fixture returning a session state just below the 80% compaction threshold."""
    # Under a window of 100 tokens, 80% is 80.
    # 78 tokens is just below 80%
    return create_session_state(token_count=78, already_compacted=False)


@pytest.fixture
def session_state_over_limit() -> dict[str, Any]:
    """Fixture returning a session state just above the 80% compaction threshold."""
    # 82 tokens is above 80% threshold of 100
    return create_session_state(token_count=82, already_compacted=False)
