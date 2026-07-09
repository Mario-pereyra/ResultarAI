import datetime
import time
from collections.abc import Generator

import pytest
import uuid6
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, IntegrityError

from resultarai.adapters.persistence_postgres.connection import get_db_session
from resultarai.adapters.persistence_postgres.models import (
    Attachment,
    CompactionMarker,
    Extraction,
    Message,
    MessageAttachment,
    Session,
)


@pytest.fixture(autouse=True)
def cleanup_db() -> Generator[None, None, None]:
    """Truncates the tables before and after each test to ensure a clean state."""
    with get_db_session() as session:
        session.execute(
            text(
                "TRUNCATE TABLE compaction_markers, messages, sessions, "
                "extractions, attachments, message_attachments CASCADE"
            )
        )
        session.commit()

    yield

    with get_db_session() as session:
        session.execute(
            text(
                "TRUNCATE TABLE compaction_markers, messages, sessions, "
                "extractions, attachments, message_attachments CASCADE"
            )
        )
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


def test_attachment_fields_and_status_constraint() -> None:
    """Valida que un adjunto guarde todos los campos requeridos

    y que un status no permitido sea rechazado.
    """
    # 1. Successful insert with all fields
    with get_db_session() as db_session:
        att = Attachment(
            uploaded_by="user-123",
            original_name="test.txt",
            declared_mime="text/plain",
            detected_type="text",
            size_bytes=1024,
            sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
            storage_path=uuid6.uuid7(),
            scan_result={"safe": True, "details": "no threat found"},
            status="uploaded",
            tenant="tenant-abc",
        )
        db_session.add(att)
        db_session.flush()
        att_id = att.id

    # Verify loaded data matches
    with get_db_session() as db_session:
        loaded = db_session.get(Attachment, att_id)
        assert loaded is not None
        assert loaded.uploaded_by == "user-123"
        assert loaded.original_name == "test.txt"
        assert loaded.declared_mime == "text/plain"
        assert loaded.detected_type == "text"
        assert loaded.size_bytes == 1024
        assert loaded.sha256 == "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
        assert loaded.storage_path is not None
        assert loaded.scan_result == {"safe": True, "details": "no threat found"}
        assert loaded.status == "uploaded"
        assert loaded.tenant == "tenant-abc"
        assert loaded.created_at is not None

    # 2. Invalid status rejected by check constraint
    def try_invalid_status() -> None:
        with get_db_session() as db_session:
            att_invalid = Attachment(
                uploaded_by="user-123",
                original_name="test.txt",
                declared_mime="text/plain",
                size_bytes=1024,
                sha256="e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
                status="invalid_status_name",
                tenant="tenant-abc",
            )
            db_session.add(att_invalid)

    with pytest.raises(IntegrityError) as exc_info:
        try_invalid_status()
    assert (
        "ck_attachments_status" in str(exc_info.value)
        or "check constraint" in str(exc_info.value).lower()
    )


def test_message_attachment_immutability() -> None:
    """Comprueba que intentar hacer UPDATE o DELETE sobre message_attachments

    sea rechazado por el trigger.
    """
    session_id = "session-immutability-ma"
    model_profile = "profile-1"

    # Create session
    with get_db_session() as db_session:
        db_sess = Session(id=session_id, model_profile=model_profile)
        db_session.add(db_sess)
        db_session.flush()

        # Create message
        msg = Message(
            session_id=session_id,
            role="user",
            content="Hello with attachment",
            model_profile=model_profile,
        )
        db_session.add(msg)

        # Create attachment
        att = Attachment(
            uploaded_by="user-123",
            original_name="test.txt",
            declared_mime="text/plain",
            size_bytes=100,
            sha256="abc123sha",
            status="ready",
            tenant="tenant-abc",
        )
        db_session.add(att)
        db_session.flush()

        msg_id = msg.id
        att_id = att.id

    # Create message attachment
    with get_db_session() as db_session:
        ma = MessageAttachment(
            message_id=msg_id,
            attachment_id=att_id,
            inserted_text="This is the text inserted.",
            token_count=5,
            truncated=False,
        )
        db_session.add(ma)

    # Try UPDATE
    def try_update_ma() -> None:
        with get_db_session() as db_session:
            ma_loaded = db_session.get(MessageAttachment, (msg_id, att_id))
            assert ma_loaded is not None
            ma_loaded.inserted_text = "Modified text"

    with pytest.raises(DBAPIError) as exc_info:
        try_update_ma()
    assert "prevent_update_or_delete" in str(exc_info.value) or "append-only" in str(exc_info.value)

    # Try DELETE
    def try_delete_ma() -> None:
        with get_db_session() as db_session:
            ma_loaded = db_session.get(MessageAttachment, (msg_id, att_id))
            assert ma_loaded is not None
            db_session.delete(ma_loaded)

    with pytest.raises(DBAPIError) as exc_info:
        try_delete_ma()
    assert "prevent_update_or_delete" in str(exc_info.value) or "append-only" in str(exc_info.value)


def test_deduplication_by_tenant_and_sha256() -> None:
    """Comprueba que si se guardan dos adjuntos con el mismo sha256 en el mismo tenant,

    estos compartan la misma Extraction (extraction_id idéntico), pero si corresponden
    a tenants diferentes, tengan extracciones independientes.
    """
    tenant_1 = "tenant-1"
    tenant_2 = "tenant-2"
    sha = "hash123"

    # 1. Create first extraction for tenant 1
    with get_db_session() as db_session:
        ext1 = Extraction(
            tenant=tenant_1,
            sha256=sha,
            full_text="Extracted text from tenant 1",
            extractor_version="v1",
        )
        db_session.add(ext1)
        db_session.flush()
        ext1_id = ext1.id

    # 2. Try to create duplicate extraction for tenant 1 (must fail due to UniqueConstraint)
    def try_duplicate_extraction() -> None:
        with get_db_session() as db_session:
            ext_dup = Extraction(
                tenant=tenant_1,
                sha256=sha,
                full_text="Duplicate extracted text",
                extractor_version="v1",
            )
            db_session.add(ext_dup)

    with pytest.raises(IntegrityError) as exc_info:
        try_duplicate_extraction()
    assert "uq_extractions_tenant_sha256" in str(exc_info.value)

    # 3. Create extraction for tenant 2 with SAME sha256 (must succeed)
    with get_db_session() as db_session:
        ext2 = Extraction(
            tenant=tenant_2,
            sha256=sha,
            full_text="Extracted text from tenant 2",
            extractor_version="v1",
        )
        db_session.add(ext2)
        db_session.flush()
        ext2_id = ext2.id

    assert ext1_id != ext2_id

    # 4. Now save two attachments in tenant 1 with same sha256, sharing the same extraction_id
    with get_db_session() as db_session:
        # Find extraction for tenant 1
        db_ext = db_session.query(Extraction).filter_by(tenant=tenant_1, sha256=sha).one()

        att1 = Attachment(
            uploaded_by="user-1",
            original_name="doc1.pdf",
            declared_mime="application/pdf",
            size_bytes=500,
            sha256=sha,
            status="ready",
            tenant=tenant_1,
            extraction_id=db_ext.id,
        )
        att2 = Attachment(
            uploaded_by="user-2",
            original_name="doc2.pdf",
            declared_mime="application/pdf",
            size_bytes=500,
            sha256=sha,
            status="ready",
            tenant=tenant_1,
            extraction_id=db_ext.id,
        )
        db_session.add_all([att1, att2])
        db_session.flush()
        att1_id, att2_id = att1.id, att2.id

    # Verify both attachments in tenant 1 share the same extraction_id
    with get_db_session() as db_session:
        a1 = db_session.get(Attachment, att1_id)
        a2 = db_session.get(Attachment, att2_id)
        assert a1 is not None
        assert a2 is not None
        assert a1.extraction_id == ext1_id
        assert a2.extraction_id == ext1_id

    # 5. Save an attachment in tenant 2 with the same sha256, pointing to tenant 2's extraction
    with get_db_session() as db_session:
        db_ext2 = db_session.query(Extraction).filter_by(tenant=tenant_2, sha256=sha).one()
        att_t2 = Attachment(
            uploaded_by="user-3",
            original_name="doc3.pdf",
            declared_mime="application/pdf",
            size_bytes=500,
            sha256=sha,
            status="ready",
            tenant=tenant_2,
            extraction_id=db_ext2.id,
        )
        db_session.add(att_t2)
        db_session.flush()
        att_t2_id = att_t2.id

    with get_db_session() as db_session:
        a_t2 = db_session.get(Attachment, att_t2_id)
        assert a_t2 is not None
        assert a_t2.extraction_id == ext2_id
        assert a_t2.extraction_id != ext1_id


def test_retention_purging() -> None:
    """Comprueba que si se borra la fila en extractions, el registro de message_attachments

    y su inserted_text permanecen intactos.
    """
    session_id = "session-purging"
    model_profile = "profile-1"
    tenant = "tenant-abc"
    sha = "hash999"

    # Create session, message, extraction, attachment, message_attachment
    with get_db_session() as db_session:
        db_sess = Session(id=session_id, model_profile=model_profile)
        db_session.add(db_sess)
        db_session.flush()

        msg = Message(
            session_id=session_id,
            role="user",
            content="Context text",
            model_profile=model_profile,
        )
        db_session.add(msg)

        ext = Extraction(
            tenant=tenant,
            sha256=sha,
            full_text="Very long extracted text that we want to purge later",
            extractor_version="v1",
        )
        db_session.add(ext)
        db_session.flush()

        att = Attachment(
            uploaded_by="user-123",
            original_name="raw.txt",
            declared_mime="text/plain",
            size_bytes=1024,
            sha256=sha,
            status="ready",
            tenant=tenant,
            extraction_id=ext.id,
        )
        db_session.add(att)
        db_session.flush()

        ma = MessageAttachment(
            message_id=msg.id,
            attachment_id=att.id,
            inserted_text="Snippet of raw.txt used in LLM prompt",
            token_count=10,
            truncated=True,
        )
        db_session.add(ma)

        msg_id = msg.id
        att_id = att.id
        ext_id = ext.id

    # Now verify everything is linked
    with get_db_session() as db_session:
        db_att = db_session.get(Attachment, att_id)
        assert db_att is not None
        assert db_att.extraction_id == ext_id

        db_ma = db_session.get(MessageAttachment, (msg_id, att_id))
        assert db_ma is not None
        assert db_ma.inserted_text == "Snippet of raw.txt used in LLM prompt"

    # Delete the extraction row
    with get_db_session() as db_session:
        db_ext = db_session.get(Extraction, ext_id)
        assert db_ext is not None
        db_session.delete(db_ext)

    # Verify that:
    # 1. Extraction row is deleted
    # 2. Attachment extraction_id is set to NULL (due to ondelete="SET NULL")
    # 3. MessageAttachment and its inserted_text remain intact
    with get_db_session() as db_session:
        assert db_session.get(Extraction, ext_id) is None

        db_att = db_session.get(Attachment, att_id)
        assert db_att is not None
        assert db_att.extraction_id is None

        db_ma = db_session.get(MessageAttachment, (msg_id, att_id))
        assert db_ma is not None
        assert db_ma.inserted_text == "Snippet of raw.txt used in LLM prompt"
