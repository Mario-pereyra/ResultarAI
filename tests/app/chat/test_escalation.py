# ruff: noqa: E402
"""Integration tests for POST /sessions/{id}/escalate.

d13-chat-conversacion, tarea 1.8.
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
# (mismo patrón que tests/app/chat/test_sessions.py).
_STABLE_KEY = Fernet.generate_key().decode("utf-8")
os.environ.setdefault("IDENTITY_TOTP_ENCRYPTION_KEY", _STABLE_KEY)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from resultarai.adapters.persistence_postgres.connection import SessionLocal, get_db_session
from resultarai.adapters.persistence_postgres.models import Message
from resultarai.adapters.persistence_postgres.models import Session as SessionModel
from resultarai.app.api import create_app
from resultarai.app.api.chat import get_registries, get_response_generator
from resultarai.app.identity import (
    SessionConfig,
    get_db,
    get_session_config,
    hash_password,
)
from resultarai.app.startup import bootstrap
from resultarai.core.registries import Registries
from tests.app.identity.conftest import make_user

_CONFIG = SessionConfig(
    signing_key="test-chat-key-for-escalation",
    idle_timeout=datetime.timedelta(minutes=30),
    absolute_lifetime=datetime.timedelta(hours=8),
    cookie_secure=False,  # deshabilitado Secure para extraer la cookie en el test client
)


class _EchoResponseGenerator:
    """Doble mínimo de `ResponseGenerator`: texto fijo, no depende de ningún LLM."""

    def __call__(self, *, session: Any, history: Any) -> str:
        return "respuesta del agente"


@pytest.fixture
def response_generator() -> _EchoResponseGenerator:
    return _EchoResponseGenerator()


@pytest.fixture
def registries() -> Registries:
    """Registries reales de `manifests/`, en fixture propia (no resuelta dentro de
    `client`) para que un test pueda mutar el Agent Manifest en memoria
    (`escalation.enabled`/`escalation.target_profile`) *antes* de que el override
    del endpoint lo lea -- mismo patrón que `tests/app/chat/test_streaming.py`.
    """
    return bootstrap(Path("manifests"))


@pytest.fixture
def client(
    response_generator: _EchoResponseGenerator, registries: Registries
) -> Iterator[TestClient]:
    """TestClient con overrides de DB, config de sesión, Registries reales (mutables
    vía la fixture `registries`) y el doble de generación de respuesta síncrona.
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
    app.dependency_overrides[get_registries] = lambda: registries
    app.dependency_overrides[get_response_generator] = lambda: response_generator

    with TestClient(app) as test_client:
        yield test_client


def _unique_username(prefix: str) -> str:
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


def _send_message(client: TestClient, session_id: str, text: str) -> Any:
    return post_csrf(client, f"/api/sessions/{session_id}/messages", json={"text": text})


def _escalate(client: TestClient, session_id: str, origin_message_id: str | None = None) -> Any:
    payload: dict[str, Any] = {}
    if origin_message_id is not None:
        payload["origin_message_id"] = origin_message_id
    return post_csrf(client, f"/api/sessions/{session_id}/escalate", json=payload)


# --- Escalación habilitada ----------------------------------------------------------


def test_escalation_enabled_creates_linked_session_with_origin_intact(
    client: TestClient,
) -> None:
    """Escalación habilitada crea una sesión nueva enlazada con el `model_profile`
    de escalación configurado, sembrada con el re-planteo del último turno de
    usuario; la sesión original queda intacta (mismos mensajes antes y después).
    """
    _create_user_and_login(client, "escalate-user")
    session_id = _create_session(client)

    turn = _send_message(client, session_id, "necesito ayuda avanzada")
    assert turn.status_code == 201

    with get_db_session() as db:
        origin_messages_before = (
            db.execute(select(Message).where(Message.session_id == session_id)).scalars().all()
        )
    assert len(origin_messages_before) == 2
    origin_ids_before = {str(m.id) for m in origin_messages_before}

    response = _escalate(client, session_id)
    assert response.status_code == 201
    data = response.json()

    assert data["origin_session_id"] == session_id
    assert data["model_profile"] == "deepseek_v4_pro"
    assert data["created"] is True
    # Tarea 2.2: el primer turno genera un título automático; la escalada lo hereda + " (Pro)"
    assert data["origin_session_title"] == "necesito ayuda avanzada"
    assert data["escalated_session_title"] == "necesito ayuda avanzada (Pro)"
    escalated_session_id = data["escalated_session_id"]
    assert escalated_session_id != session_id
    assert escalated_session_id.startswith("sess_")

    with get_db_session() as db:
        escalated_session = db.get(SessionModel, escalated_session_id)
        assert escalated_session is not None
        assert escalated_session.forked_from_id == session_id
        assert escalated_session.model_profile == "deepseek_v4_pro"
        assert escalated_session.agent_id == "default_chat"
        assert escalated_session.owner_user_id is not None

        seeded_message = db.get(Message, uuid.UUID(data["seeded_message_id"]))
        assert seeded_message is not None
        assert seeded_message.session_id == escalated_session_id
        assert seeded_message.role == "user"
        assert seeded_message.parent_id is None
        assert seeded_message.content == "necesito ayuda avanzada"
        assert seeded_message.model_profile == "deepseek_v4_pro"

        # Ninguna respuesta de agente se genera al sembrar: un único mensaje.
        escalated_messages = (
            db.execute(select(Message).where(Message.session_id == escalated_session_id))
            .scalars()
            .all()
        )
        assert len(escalated_messages) == 1

        # La sesión original permanece intacta: mismos mensajes, mismo model_profile.
        origin_messages_after = (
            db.execute(select(Message).where(Message.session_id == session_id)).scalars().all()
        )
        assert {str(m.id) for m in origin_messages_after} == origin_ids_before
        origin_session = db.get(SessionModel, session_id)
        assert origin_session is not None
        assert origin_session.model_profile != "deepseek_v4_pro"


def test_escalation_with_explicit_origin_message_id_reprises_that_turn(
    client: TestClient,
) -> None:
    """Con `origin_message_id` explícito, la siembra re-plantea ESE turno, no el
    último mensaje de usuario de la rama activa.
    """
    _create_user_and_login(client, "escalate-explicit")
    session_id = _create_session(client)

    first_turn = _send_message(client, session_id, "primer turno")
    assert first_turn.status_code == 201
    first_user_message_id = first_turn.json()["user_message"]["id"]

    second_turn = _send_message(client, session_id, "segundo turno, distinto")
    assert second_turn.status_code == 201

    response = _escalate(client, session_id, origin_message_id=first_user_message_id)
    assert response.status_code == 201
    data = response.json()

    with get_db_session() as db:
        seeded_message = db.get(Message, uuid.UUID(data["seeded_message_id"]))
        assert seeded_message is not None
        assert seeded_message.content == "primer turno"


def test_escalation_title_derived_from_origin_title(client: TestClient) -> None:
    """El título de la sesión escalada se deriva del de la origen ("<título> (Pro)")."""
    _create_user_and_login(client, "escalate-title")
    session_id = _create_session(client)
    turn = _send_message(client, session_id, "consulta con título")
    assert turn.status_code == 201

    with get_db_session() as db:
        origin_session = db.get(SessionModel, session_id)
        assert origin_session is not None
        origin_session.title = "Consulta de prueba"
        db.commit()

    response = _escalate(client, session_id)
    assert response.status_code == 201
    data = response.json()
    assert data["origin_session_title"] == "Consulta de prueba"
    assert data["escalated_session_title"] == "Consulta de prueba (Pro)"


# --- Escalación deshabilitada ---------------------------------------------------------


def test_escalation_disabled_rejects_without_creating_anything(
    client: TestClient, registries: Registries
) -> None:
    """Con `escalation.enabled: false` en el Agent Manifest, escalar se rechaza
    (403) sin crear ninguna sesión ni mensaje nuevo en toda la base.
    """
    agent = registries.agents.get_invocable("default_chat")
    assert agent is not None
    agent.escalation.enabled = False

    _create_user_and_login(client, "escalate-disabled")
    session_id = _create_session(client)
    turn = _send_message(client, session_id, "consulta cualquiera")
    assert turn.status_code == 201

    with get_db_session() as db:
        sessions_before = db.execute(select(SessionModel)).scalars().all()
        messages_before = db.execute(select(Message)).scalars().all()

    response = _escalate(client, session_id)
    assert response.status_code == 403

    with get_db_session() as db:
        sessions_after = db.execute(select(SessionModel)).scalars().all()
        messages_after = db.execute(select(Message)).scalars().all()

    assert len(sessions_after) == len(sessions_before)
    assert len(messages_after) == len(messages_before)


def test_escalation_missing_target_profile_returns_422_without_creating_anything(
    client: TestClient, registries: Registries
) -> None:
    """`escalation.enabled: true` pero sin `target_profile`: 422 explícito (agente
    mal configurado), sin crear ninguna sesión nueva.
    """
    agent = registries.agents.get_invocable("default_chat")
    assert agent is not None
    agent.escalation.target_profile = None

    _create_user_and_login(client, "escalate-misconfigured")
    session_id = _create_session(client)
    turn = _send_message(client, session_id, "consulta cualquiera")
    assert turn.status_code == 201

    with get_db_session() as db:
        sessions_before = db.execute(select(SessionModel)).scalars().all()

    response = _escalate(client, session_id)
    assert response.status_code == 422

    with get_db_session() as db:
        sessions_after = db.execute(select(SessionModel)).scalars().all()
    assert len(sessions_after) == len(sessions_before)


def test_escalation_foreign_session_returns_404(client: TestClient) -> None:
    """Escalar una sesión ajena responde 404 sin crear nada."""
    _create_user_and_login(client, "escalate-owner")
    owner_session_id = _create_session(client)
    turn = _send_message(client, owner_session_id, "hola")
    assert turn.status_code == 201

    _create_user_and_login(client, "escalate-intruder")
    response = _escalate(client, owner_session_id)
    assert response.status_code == 404

    with get_db_session() as db:
        escalated = (
            db.execute(select(SessionModel).where(SessionModel.forked_from_id == owner_session_id))
            .scalars()
            .all()
        )
    assert escalated == []


# --- Idempotencia (soporta la tarea 5.3 de UI: doble clic/doble pestaña) ------------


def test_escalation_is_idempotent_across_repeated_calls(client: TestClient) -> None:
    """Dos llamadas seguidas sobre el mismo turno de origen devuelven la MISMA
    sesión escalada: la segunda responde 200 con `created: false`, sin crear una
    segunda sesión escalada en la base.
    """
    _create_user_and_login(client, "escalate-idem")
    session_id = _create_session(client)
    turn = _send_message(client, session_id, "turno a escalar dos veces")
    assert turn.status_code == 201

    first = _escalate(client, session_id)
    assert first.status_code == 201
    first_data = first.json()
    assert first_data["created"] is True

    second = _escalate(client, session_id)
    assert second.status_code == 200
    second_data = second.json()
    assert second_data["created"] is False
    assert second_data["escalated_session_id"] == first_data["escalated_session_id"]
    assert second_data["seeded_message_id"] == first_data["seeded_message_id"]

    with get_db_session() as db:
        escalated_sessions = (
            db.execute(select(SessionModel).where(SessionModel.forked_from_id == session_id))
            .scalars()
            .all()
        )
        assert len(escalated_sessions) == 1
