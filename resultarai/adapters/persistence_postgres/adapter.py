"""PostgreSQL implementation of StatePort."""

import datetime
import uuid
from typing import Any

from resultarai.adapters.persistence_postgres.connection import get_db_session
from resultarai.adapters.persistence_postgres.models import (
    Message as DbMessage,
)
from resultarai.adapters.persistence_postgres.models import (
    Session as DbSession,
)
from resultarai.core.ports.state import StatePort


class PersistenceStatePort(StatePort):
    """Adapter implementing StatePort using PostgreSQL."""

    def load_state(self, thread_id: str) -> dict[str, Any] | None:
        """Load state by thread identifier."""
        with get_db_session() as db:
            session_obj = db.query(DbSession).filter(DbSession.id == thread_id).first()
            if session_obj is None:
                return None

            # Reconstruct the state dictionary from session metadata and messages
            state = dict(session_obj.state_data) if session_obj.state_data is not None else {}
            state["model_profile"] = session_obj.model_profile
            state["forked_from_id"] = session_obj.forked_from_id

            # Get all messages ordered by id (UUIDv7) ascending
            messages = (
                db.query(DbMessage)
                .filter(DbMessage.session_id == thread_id)
                .order_by(DbMessage.id)
                .all()
            )

            state["messages"] = [
                {
                    "id": str(msg.id),
                    "role": msg.role,
                    "content": msg.content,
                    "parent_id": str(msg.parent_id) if msg.parent_id is not None else None,
                    "model_profile": msg.model_profile,
                    "created_at": msg.created_at,  # Return naive datetime object
                }
                for msg in messages
            ]

            return state

    def save_state(self, thread_id: str, state: dict[str, Any]) -> None:
        """Save state under thread identifier."""
        model_profile = state.get("model_profile", "default")
        forked_from_id = state.get("forked_from_id")

        # Exclude messages, model_profile, forked_from_id from state_data
        state_data = {
            k: v
            for k, v in state.items()
            if k not in ("messages", "model_profile", "forked_from_id")
        }

        with get_db_session() as db:
            # Find the session by id
            session_obj = db.query(DbSession).filter(DbSession.id == thread_id).first()
            if session_obj is None:
                session_obj = DbSession(
                    id=thread_id,
                    model_profile=model_profile,
                    forked_from_id=forked_from_id,
                    state_data=state_data,
                )
                db.add(session_obj)
            else:
                # Deny different model_profile
                if session_obj.model_profile != model_profile:
                    raise ValueError(
                        f"Cannot change model_profile of session '{thread_id}' "
                        f"from '{session_obj.model_profile}' to '{model_profile}'"
                    )
                # Update state_data
                session_obj.state_data = state_data
                if forked_from_id is not None:
                    session_obj.forked_from_id = forked_from_id

            # Process messages: sort them topologically based on parent-child relationships
            # to ensure parents are inserted before children (avoiding ForeignKeyViolation)
            messages = state.get("messages", [])
            msg_map = {str(m["id"]): m for m in messages if "id" in m}
            processed_ids = set()

            remaining = list(messages)
            iterations = 0
            max_iterations = len(remaining) * 2

            while remaining and iterations < max_iterations:
                iterations += 1
                msg_dict = remaining.pop(0)
                msg_id_val = msg_dict.get("id")
                if msg_id_val is None:
                    continue

                parent_id_val = msg_dict.get("parent_id")
                parent_ready = True
                if parent_id_val is not None:
                    parent_id_str = str(parent_id_val)
                    if parent_id_str in msg_map and parent_id_str not in processed_ids:
                        parent_ready = False

                if parent_ready:
                    # Convert id to UUID
                    if isinstance(msg_id_val, str):
                        msg_uuid = uuid.UUID(msg_id_val)
                    elif isinstance(msg_id_val, uuid.UUID):
                        msg_uuid = msg_id_val
                    else:
                        raise ValueError(f"Invalid message ID: {msg_id_val}")

                    # Check if message already exists in DB
                    existing_msg = db.query(DbMessage).filter(DbMessage.id == msg_uuid).first()
                    if existing_msg is None:
                        # Prepare fields for new message
                        role = msg_dict.get("role")
                        content = msg_dict.get("content")
                        if role is None or content is None:
                            raise ValueError("Message role and content are required.")

                        parent_uuid = None
                        if parent_id_val is not None:
                            if isinstance(parent_id_val, str):
                                parent_uuid = uuid.UUID(parent_id_val)
                            elif isinstance(parent_id_val, uuid.UUID):
                                parent_uuid = parent_id_val
                            else:
                                raise ValueError(f"Invalid parent ID: {parent_id_val}")

                        msg_model_profile = msg_dict.get("model_profile", model_profile)

                        created_at = msg_dict.get("created_at")
                        if created_at is not None:
                            if isinstance(created_at, str):
                                created_at = datetime.datetime.fromisoformat(created_at)
                            if (
                                isinstance(created_at, datetime.datetime)
                                and created_at.tzinfo is not None
                            ):
                                created_at = created_at.astimezone(datetime.UTC).replace(
                                    tzinfo=None
                                )

                        # Create message record
                        new_msg = DbMessage(
                            id=msg_uuid,
                            session_id=thread_id,
                            parent_id=parent_uuid,
                            role=role,
                            content=content,
                            model_profile=msg_model_profile,
                            created_at=created_at,
                        )
                        db.add(new_msg)

                    # Mark as processed
                    processed_ids.add(str(msg_id_val))
                else:
                    # Put back at the end of the queue
                    remaining.append(msg_dict)
