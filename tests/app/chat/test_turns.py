# ruff: noqa: E402
"""Integration tests for POST /sessions/{id}/messages y POST /messages/{id}/regenerate.

d13-chat-conversacion, tareas 1.2 (turno / edición) y 1.3 (regenerar).
"""

from __future__ import annotations

import datetime
import os
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet

# Fijar una clave estable en el entorno antes de importar nada que inicialice TotpConfig
# (mismo patron que tests/app/chat/test_sessions.py).
_STABLE_KEY = Fernet.generate_key().decode("utf-8")
os.environ.setdefault("IDENTITY_TOTP_ENCRYPTION_KEY", _STABLE_KEY)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from resultarai.adapters.persistence_postgres.connection import SessionLocal, get_db_session
from resultarai.adapters.persistence_postgres.models import Message
from resultarai.app.api import create_app
from resultarai.app.api.chat import get_registries, get_response_generator
from resultarai.app.identity import (
    SessionConfig,
    get_db,
    get_session_config,
    hash_password,
)
from resultarai.app.startup import bootstrap
from tests.app.identity.conftest import make_user

_CONFIG = SessionConfig(
    signing_key="test-chat-key-for-turns-and-regenerate",
    idle_timeout=datetime.timedelta(minutes=30),
    absolute_lifetime=datetime.timedelta(hours=8),
    cookie_secure=False,  # deshabilitado Secure para extraer la cookie en el test client
)


class _CountingResponseGenerator:
    """Doble de `ResponseGenerator`: devuelve texto distinto en cada llamada.

    Permite distinguir en los asserts qué invocación produjo cada mensaje persistido,
    sin depender de ningún runtime real (tareas 1.2/1.3 son síncronas por diseño).
    """

    def __init__(self) -> None:
        self.calls = 0
        # Respuesta fija opcional: permite forzar texto adversarial (p. ej. el
        # marcador de escalación crudo) sin duplicar la fixture del cliente.
        self.reply_override: str | None = None

    def __call__(self, *, session: Any, history: Any) -> str:
        self.calls += 1
        if self.reply_override is not None:
            return self.reply_override
        return f"respuesta generada #{self.calls}"


@pytest.fixture
def response_generator() -> _CountingResponseGenerator:
    return _CountingResponseGenerator()


@pytest.fixture
def client(response_generator: _CountingResponseGenerator) -> Iterator[TestClient]:
    """TestClient con overrides de DB, config de sesión, Registries reales y el doble
    de generación de respuesta (`get_response_generator`).
    """
    app = create_app()

    def _override_db() -> Iterator[DbSession]:
        session = SessionLocal()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_session_config] = lambda: _CONFIG
    app.dependency_overrides[get_registries] = lambda: bootstrap(Path("manifests"))
    app.dependency_overrides[get_response_generator] = lambda: response_generator

    with TestClient(app) as test_client:
        yield test_client


def _unique_username(prefix: str) -> str:
    """Genera un username único por invocación (ver `test_sessions.py`: la suite de
    chat no trunca `users`).
    """
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def login(client: TestClient, username: str, pwd: str) -> None:
    r = client.post("/api/auth/login", json={"username": username, "password": pwd})
    assert r.status_code == 200
    assert r.json() == {"status": "success"}


def post_csrf(client: TestClient, url: str, json: dict[str, Any] | None = None) -> Any:
    """Adjunta el header CSRF a partir de la cookie de sesión actual."""
    csrf_token = client.cookies.get("resultarai_csrf")
    headers = {}
    if csrf_token:
        headers["X-CSRF-Token"] = csrf_token
    return client.post(url, json=json, headers=headers)


def _create_user_and_login(client: TestClient, prefix: str, role: str = "funcional") -> None:
    pwd = "ValidPassword123!"
    username = _unique_username(prefix)
    make_user(username, role=role, password_hash=hash_password(pwd))
    login(client, username, pwd)


def _create_session(client: TestClient) -> str:
    response = post_csrf(client, "/api/sessions", json={"agent_id": "default_chat"})
    assert response.status_code == 201
    session_id: str = response.json()["id"]
    return session_id


def _send_message(
    client: TestClient, session_id: str, text: str, edits_message_id: str | None = None
) -> Any:
    payload: dict[str, Any] = {"text": text}
    if edits_message_id is not None:
        payload["edits_message_id"] = edits_message_id
    return post_csrf(client, f"/api/sessions/{session_id}/messages", json=payload)


# --- Tarea 1.2: turno normal ------------------------------------------------------


def test_send_turn_chains_user_message_to_active_leaf(client: TestClient) -> None:
    """Un turno normal cuelga el mensaje de usuario del leaf de la rama activa."""
    _create_user_and_login(client, "turn-user")
    session_id = _create_session(client)

    first = _send_message(client, session_id, "primer turno")
    assert first.status_code == 201
    first_data = first.json()
    assert first_data["user_message"]["parent_id"] is None  # sesión vacía: cuelga de la raíz
    assert first_data["assistant_message"]["parent_id"] == first_data["user_message"]["id"]
    assert first_data["assistant_message"]["role"] == "assistant"
    assert first_data["assistant_message"]["status"] == "complete"
    assert first_data["reprocessed_count"] == 0

    second = _send_message(client, session_id, "segundo turno")
    assert second.status_code == 201
    second_data = second.json()
    # El segundo turno cuelga del leaf del primero (la respuesta del agente anterior).
    assert second_data["user_message"]["parent_id"] == first_data["assistant_message"]["id"]

    with get_db_session() as db:
        messages = (
            db.execute(select(Message).where(Message.session_id == session_id)).scalars().all()
        )
        assert len(messages) == 4

        session_row = db.get(Message, uuid.UUID(second_data["assistant_message"]["id"]))
        assert session_row is not None
        assert session_row.model_profile is not None


def test_send_turn_updates_session_last_activity(client: TestClient) -> None:
    """Cada turno actualiza `last_activity_at` de la sesión (avanza respecto de la
    marca fijada al crearla, tarea 1.1).
    """
    from resultarai.adapters.persistence_postgres.models import Session as SessionModel

    _create_user_and_login(client, "turn-activity")
    session_id = _create_session(client)

    with get_db_session() as db:
        session_row = db.get(SessionModel, session_id)
        assert session_row is not None
        assert session_row.last_activity_at is not None
        activity_at_creation = session_row.last_activity_at

    response = _send_message(client, session_id, "hola")
    assert response.status_code == 201

    with get_db_session() as db:
        session_row = db.get(SessionModel, session_id)
        assert session_row is not None
        assert session_row.last_activity_at is not None
        assert session_row.last_activity_at >= activity_at_creation


def test_send_turn_to_foreign_session_returns_404(client: TestClient) -> None:
    """Enviar un turno a una sesión ajena responde 404 sin crear ningún mensaje."""
    _create_user_and_login(client, "turn-owner")
    owner_session_id = _create_session(client)

    _create_user_and_login(client, "turn-intruder")
    response = _send_message(client, owner_session_id, "intento ajeno")
    assert response.status_code == 404

    with get_db_session() as db:
        messages = (
            db.execute(select(Message).where(Message.session_id == owner_session_id))
            .scalars()
            .all()
        )
        assert len(messages) == 0


# --- Tarea 1.2: edición crea rama hermana -----------------------------------------


def test_edit_message_creates_sibling_branch_without_touching_original(
    client: TestClient,
) -> None:
    """Editar un mensaje intermedio crea un hermano bajo el mismo `parent_id`; el
    original y todos sus descendientes permanecen intactos y navegables.
    """
    _create_user_and_login(client, "edit-user")
    session_id = _create_session(client)

    turn1 = _send_message(client, session_id, "primer mensaje original")
    assert turn1.status_code == 201
    turn1_data = turn1.json()
    u1_id = turn1_data["user_message"]["id"]
    a1_id = turn1_data["assistant_message"]["id"]

    turn2 = _send_message(client, session_id, "segundo mensaje")
    assert turn2.status_code == 201
    turn2_data = turn2.json()
    u2_id = turn2_data["user_message"]["id"]
    a2_id = turn2_data["assistant_message"]["id"]

    # Editar el PRIMER mensaje de usuario (tiene 3 descendientes: a1, u2, a2).
    edit_response = _send_message(
        client, session_id, "primer mensaje EDITADO", edits_message_id=u1_id
    )
    assert edit_response.status_code == 201
    edit_data = edit_response.json()

    assert edit_data["user_message"]["content"] == "primer mensaje EDITADO"
    # Hermano: mismo parent_id que el mensaje original editado (None, raíz de la sesión).
    assert edit_data["user_message"]["parent_id"] is None
    assert edit_data["user_message"]["id"] != u1_id
    assert edit_data["reprocessed_count"] == 3

    with get_db_session() as db:
        # El original y sus tres descendientes siguen intactos y navegables.
        original = db.get(Message, uuid.UUID(u1_id))
        assert original is not None
        assert original.content == "primer mensaje original"
        assert original.parent_id is None

        a1 = db.get(Message, uuid.UUID(a1_id))
        assert a1 is not None
        assert a1.parent_id == uuid.UUID(u1_id)

        u2 = db.get(Message, uuid.UUID(u2_id))
        assert u2 is not None
        assert u2.parent_id == uuid.UUID(a1_id)

        a2 = db.get(Message, uuid.UUID(a2_id))
        assert a2 is not None
        assert a2.parent_id == uuid.UUID(u2_id)

        # La sesión completa tiene 6 mensajes: los 4 originales + la rama de edición (2).
        all_messages = (
            db.execute(select(Message).where(Message.session_id == session_id)).scalars().all()
        )
        assert len(all_messages) == 6

        # Ambos mensajes raíz (original editado y su hermano nuevo) cuelgan de parent_id=None.
        roots = [m for m in all_messages if m.parent_id is None]
        assert len(roots) == 2
        root_ids = {str(m.id) for m in roots}
        assert root_ids == {u1_id, edit_data["user_message"]["id"]}


def test_edit_foreign_message_rejected_without_creating_branch(client: TestClient) -> None:
    """Editar un mensaje que no pertenece a la sesión propia se rechaza (403) sin
    crear ninguna fila nueva.
    """
    _create_user_and_login(client, "edit-owner")
    owner_session_id = _create_session(client)
    owner_turn = _send_message(client, owner_session_id, "mensaje del dueño")
    assert owner_turn.status_code == 201
    owner_message_id = owner_turn.json()["user_message"]["id"]

    _create_user_and_login(client, "edit-intruder")
    intruder_session_id = _create_session(client)

    response = _send_message(
        client, intruder_session_id, "intento de edicion ajena", edits_message_id=owner_message_id
    )
    assert response.status_code == 403

    with get_db_session() as db:
        # La sesión del intruso sigue vacía: no se creó ninguna fila.
        intruder_messages = (
            db.execute(select(Message).where(Message.session_id == intruder_session_id))
            .scalars()
            .all()
        )
        assert len(intruder_messages) == 0

        # El mensaje del dueño permanece intacto.
        owner_message = db.get(Message, uuid.UUID(owner_message_id))
        assert owner_message is not None
        assert owner_message.content == "mensaje del dueño"


# --- Tarea 1.3: regenerar --------------------------------------------------------


def test_regenerate_twice_creates_three_navigable_versions(client: TestClient) -> None:
    """Regenerar dos veces crea 3 versiones hermanas del mensaje de agente, todas
    navegables, sin borrar ni modificar ninguna anterior.
    """
    _create_user_and_login(client, "regen-user")
    session_id = _create_session(client)

    turn = _send_message(client, session_id, "cuéntame un chiste")
    assert turn.status_code == 201
    turn_data = turn.json()
    user_message_id = turn_data["user_message"]["id"]
    version1_id = turn_data["assistant_message"]["id"]
    version1_content = turn_data["assistant_message"]["content"]

    regen1 = post_csrf(client, f"/api/messages/{version1_id}/regenerate")
    assert regen1.status_code == 201
    regen1_data = regen1.json()
    assert regen1_data["version"] == 2
    assert regen1_data["version_count"] == 2
    version2_id = regen1_data["message"]["id"]
    assert regen1_data["message"]["parent_id"] == user_message_id

    regen2 = post_csrf(client, f"/api/messages/{version2_id}/regenerate")
    assert regen2.status_code == 201
    regen2_data = regen2.json()
    assert regen2_data["version"] == 3
    assert regen2_data["version_count"] == 3
    version3_id = regen2_data["message"]["id"]
    assert regen2_data["message"]["parent_id"] == user_message_id

    with get_db_session() as db:
        siblings = (
            db.execute(
                select(Message)
                .where(Message.parent_id == uuid.UUID(user_message_id), Message.role == "assistant")
                .order_by(Message.created_at.asc())
            )
            .scalars()
            .all()
        )
        assert len(siblings) == 3
        sibling_ids = {str(m.id) for m in siblings}
        assert sibling_ids == {version1_id, version2_id, version3_id}

        # Ninguna versión anterior fue modificada.
        v1 = db.get(Message, uuid.UUID(version1_id))
        assert v1 is not None
        assert v1.content == version1_content
        v2 = db.get(Message, uuid.UUID(version2_id))
        assert v2 is not None
        assert v2.content == regen1_data["message"]["content"]


def test_regenerate_non_assistant_message_returns_422(client: TestClient) -> None:
    """Regenerar un mensaje de rol `user` (no una respuesta del agente) se rechaza."""
    _create_user_and_login(client, "regen-invalid")
    session_id = _create_session(client)

    turn = _send_message(client, session_id, "hola")
    assert turn.status_code == 201
    user_message_id = turn.json()["user_message"]["id"]

    response = post_csrf(client, f"/api/messages/{user_message_id}/regenerate")
    assert response.status_code == 422


def test_regenerate_in_foreign_session_returns_404_without_creating_anything(
    client: TestClient,
) -> None:
    """Regenerar un mensaje de una sesión ajena responde 404 sin crear nada."""
    _create_user_and_login(client, "regen-owner")
    owner_session_id = _create_session(client)
    turn = _send_message(client, owner_session_id, "hola")
    assert turn.status_code == 201
    owner_assistant_id = turn.json()["assistant_message"]["id"]

    _create_user_and_login(client, "regen-intruder")
    response = post_csrf(client, f"/api/messages/{owner_assistant_id}/regenerate")
    assert response.status_code == 404

    with get_db_session() as db:
        siblings = (
            db.execute(
                select(Message).where(Message.parent_id.is_not(None), Message.role == "assistant")
            )
            .scalars()
            .all()
        )
        # Solo existe la respuesta original del dueño; no se creó ninguna versión nueva.
        matching = [m for m in siblings if m.session_id == owner_session_id]
        assert len(matching) == 1
        assert str(matching[0].id) == owner_assistant_id


def test_sync_paths_never_persist_raw_escalation_marker(
    client: TestClient, response_generator: _CountingResponseGenerator
) -> None:
    """El marcador crudo tampoco se persiste por el camino síncrono (review 10.1).

    El gateway de b05 deja `<<<NEEDS_PRO>>>` dentro de `LLMResponse.text` (solo
    señala `needs_pro`); `send_turn`/`regenerate_response` deben filtrarlo antes
    del INSERT — si no, saldría por el detalle de sesión y los snippets de
    búsqueda. Espejo síncrono de la garantía ya testeada en streaming (1.4).
    """
    _create_user_and_login(client, "marker-sync")
    session_id = _create_session(client)
    response_generator.reply_override = "puedo ayudarte <<<NEEDS_PRO>>> con eso"

    send = post_csrf(
        client,
        f"/api/sessions/{session_id}/messages",
        json={"text": "consulta que dispara el marcador"},
    )
    assert send.status_code == 201
    assistant_content = send.json()["assistant_message"]["content"]
    assert "<<<NEEDS_PRO>>>" not in assistant_content
    assert "puedo ayudarte" in assistant_content

    regen = post_csrf(client, f"/api/messages/{send.json()['assistant_message']['id']}/regenerate")
    assert regen.status_code == 201
    assert "<<<NEEDS_PRO>>>" not in regen.json()["message"]["content"]

    detail = client.get(f"/api/sessions/{session_id}")
    assert detail.status_code == 200
    for message in detail.json()["messages"]:
        assert "<<<NEEDS_PRO>>>" not in message["content"]
