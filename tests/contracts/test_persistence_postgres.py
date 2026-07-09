import datetime
import time
from collections.abc import Generator

import pytest
import uuid6
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from resultarai.adapters.persistence_postgres.connection import get_db_session
from resultarai.adapters.persistence_postgres.models import CompactionMarker, Message, Session


@pytest.fixture(autouse=True)
def cleanup_db() -> Generator[None, None, None]:
    """Truncates the tables before and after each test to ensure a clean state."""
    with get_db_session() as session:
        session.execute(text("TRUNCATE TABLE compaction_markers, messages, sessions CASCADE"))
        session.commit()

    yield

    with get_db_session() as session:
        session.execute(text("TRUNCATE TABLE compaction_markers, messages, sessions CASCADE"))
        session.commit()


def test_connection_smoke() -> None:
    """Verifica que la conexión a la base de datos funciona y ejecuta consultas."""
    with get_db_session() as session:
        result = session.execute(text("SELECT 1"))
        row = result.fetchone()
        assert row is not None
        assert row[0] == 1


def test_transaction_rollback_on_error() -> None:
    """Verifica que si ocurre un error dentro de la sesión, se propaga y limpia."""
    with pytest.raises(ValueError, match="Smoke error"), get_db_session():
        raise ValueError("Smoke error")


def test_session_survives_restart() -> None:
    """Persiste una sesión y sus mensajes, simula el cierre de sesión,

    recupéralos y verifica que el árbol de parent_id sigue idéntico.
    """
    session_id = "session-restart-test"
    model_profile = "profile-1"

    msg1_id = uuid6.uuid7()
    msg2_id = uuid6.uuid7()
    msg3_id = uuid6.uuid7()

    # 1. Persist session and parent-child messages
    with get_db_session() as session:
        db_session = Session(id=session_id, model_profile=model_profile)
        session.add(db_session)
        session.flush()

        msg1 = Message(
            id=msg1_id,
            session_id=session_id,
            parent_id=None,
            role="user",
            content="Hello",
            model_profile=model_profile,
        )
        msg2 = Message(
            id=msg2_id,
            session_id=session_id,
            parent_id=msg1_id,
            role="assistant",
            content="Hi there!",
            model_profile=model_profile,
        )
        msg3 = Message(
            id=msg3_id,
            session_id=session_id,
            parent_id=msg2_id,
            role="user",
            content="How are you?",
            model_profile=model_profile,
        )
        session.add_all([msg1, msg2, msg3])

    # 2. Simulate closure/restart and reload from a fresh DB session
    with get_db_session() as session:
        db_messages = session.query(Message).filter_by(session_id=session_id).all()
        assert len(db_messages) == 3

        msg_map = {msg.id: msg for msg in db_messages}

        # Verify parent-child tree is identical
        assert msg_map[msg1_id].parent_id is None
        assert msg_map[msg2_id].parent_id == msg1_id
        assert msg_map[msg3_id].parent_id == msg2_id
        assert msg_map[msg3_id].parent.parent_id == msg1_id  # type: ignore[union-attr]


def test_messages_ordered_by_uuid7() -> None:
    """Inserta varios mensajes y comprueba que ordenarlos por id (UUIDv7)

    mantiene el orden cronológico de inserción sin depender del reloj de aplicación.
    """
    session_id = "session-uuid7-test"
    model_profile = "profile-1"

    with get_db_session() as session:
        db_session = Session(id=session_id, model_profile=model_profile)
        session.add(db_session)

    message_ids = []
    for i in range(5):
        with get_db_session() as session:
            msg = Message(
                session_id=session_id,
                role="user",
                content=f"Message {i}",
                model_profile=model_profile,
            )
            session.add(msg)
            session.flush()
            message_ids.append(msg.id)
        # Tiny sleep to ensure a tick of timestamp separation in UUIDv7
        time.sleep(0.005)

    # Fetch them back ordering by UUIDv7 primary key
    with get_db_session() as session:
        ordered_msgs = (
            session.query(Message).filter_by(session_id=session_id).order_by(Message.id).all()
        )
        assert len(ordered_msgs) == 5

        queried_ids = [msg.id for msg in ordered_msgs]
        assert queried_ids == message_ids


def test_immutability_triggers() -> None:
    """Comprueba que intentar hacer un UPDATE o DELETE en un mensaje o marcador

    de compactación lanza un error de la base de datos (trigger prevent_update_or_delete).
    """
    session_id = "session-immutability"
    model_profile = "profile-1"

    with get_db_session() as session:
        db_session = Session(id=session_id, model_profile=model_profile)
        session.add(db_session)

    # Insert a message
    msg_id = uuid6.uuid7()
    with get_db_session() as session:
        msg = Message(
            id=msg_id,
            session_id=session_id,
            role="user",
            content="Original content",
            model_profile=model_profile,
        )
        session.add(msg)

    # Try UPDATE message
    def try_update_message() -> None:
        with get_db_session() as session:
            msg = session.get(Message, msg_id)
            assert msg is not None
            msg.content = "Modified content"

    with pytest.raises(DBAPIError) as exc_info:
        try_update_message()
    assert "prevent_update_or_delete" in str(exc_info.value) or "append-only" in str(exc_info.value)

    # Try DELETE message
    def try_delete_message() -> None:
        with get_db_session() as session:
            msg = session.get(Message, msg_id)
            assert msg is not None
            session.delete(msg)

    with pytest.raises(DBAPIError) as exc_info:
        try_delete_message()
    assert "prevent_update_or_delete" in str(exc_info.value) or "append-only" in str(exc_info.value)

    # Insert compaction marker
    with get_db_session() as session:
        marker = CompactionMarker(message_id=msg_id)
        session.add(marker)

    # Try UPDATE compaction marker
    def try_update_marker() -> None:
        with get_db_session() as session:
            marker = session.get(CompactionMarker, msg_id)
            assert marker is not None
            marker.created_at = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)

    with pytest.raises(DBAPIError) as exc_info:
        try_update_marker()
    assert "prevent_update_or_delete" in str(exc_info.value) or "append-only" in str(exc_info.value)

    # Try DELETE compaction marker
    def try_delete_marker() -> None:
        with get_db_session() as session:
            marker = session.get(CompactionMarker, msg_id)
            assert marker is not None
            session.delete(marker)

    with pytest.raises(DBAPIError) as exc_info:
        try_delete_marker()
    assert "prevent_update_or_delete" in str(exc_info.value) or "append-only" in str(exc_info.value)


def test_stickiness_constraint() -> None:
    """Comprueba que intentar insertar un mensaje en una sesión con un model_profile

    diferente al de la sesión sea rechazado (composite foreign key constraint).
    """
    session_id = "session-stickiness"
    session_profile = "profile-a"
    message_profile = "profile-b"

    with get_db_session() as session:
        db_session = Session(id=session_id, model_profile=session_profile)
        session.add(db_session)

    # Insert a message with mismatched model profile
    def try_insert_stickiness_mismatch() -> None:
        with get_db_session() as session:
            msg = Message(
                session_id=session_id,
                role="user",
                content="Hello",
                model_profile=message_profile,
            )
            session.add(msg)

    with pytest.raises(IntegrityError) as exc_info:
        try_insert_stickiness_mismatch()
    assert (
        "fk_messages_session_id_model_profile_sessions" in str(exc_info.value)
        or "foreign key" in str(exc_info.value).lower()
    )


def test_compaction_marker_unique() -> None:
    """Comprueba que intentar registrar un segundo marcador de compactación para el mismo

    mensaje/turno falle con un error de clave primaria.
    """
    session_id = "session-compaction-unique"
    model_profile = "profile-1"

    with get_db_session() as session:
        db_session = Session(id=session_id, model_profile=model_profile)
        session.add(db_session)

    msg_id = uuid6.uuid7()
    with get_db_session() as session:
        msg = Message(
            id=msg_id,
            session_id=session_id,
            role="user",
            content="Hello",
            model_profile=model_profile,
        )
        session.add(msg)

    # First compaction marker
    with get_db_session() as session:
        marker1 = CompactionMarker(message_id=msg_id)
        session.add(marker1)

    # Second compaction marker for the same message must fail
    def try_insert_duplicate_marker() -> None:
        with get_db_session() as session:
            marker2 = CompactionMarker(message_id=msg_id)
            session.add(marker2)

    with pytest.raises(IntegrityError) as exc_info:
        try_insert_duplicate_marker()
    assert (
        "pk_compaction_markers" in str(exc_info.value)
        or "primary key" in str(exc_info.value).lower()
    )
