# ruff: noqa: E402
"""Integration tests for POST /sessions and model_profile stickiness (d13, tarea 1.1)."""

from __future__ import annotations

import datetime
import os
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet

# Fijar una clave estable en el entorno antes de importar nada que inicialice TotpConfig
# (mismo patron que tests/app/identity/test_endpoints.py).
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
from resultarai.app.api.chat import get_registries
from resultarai.app.identity import (
    SessionConfig,
    get_db,
    get_session_config,
    hash_password,
)
from resultarai.app.startup import bootstrap
from tests.app.identity.conftest import make_user

_CONFIG = SessionConfig(
    signing_key="test-chat-key-for-sessions-and-stickiness",
    idle_timeout=datetime.timedelta(minutes=30),
    absolute_lifetime=datetime.timedelta(hours=8),
    cookie_secure=False,  # deshabilitado Secure para extraer la cookie en el test client
)


@pytest.fixture
def client() -> Iterator[TestClient]:
    """TestClient con overrides de DB, config de sesion y Registries reales de manifests/."""
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

    with TestClient(app) as test_client:
        yield test_client


def _unique_username(prefix: str) -> str:
    """Genera un username unico por invocacion.

    Esta suite (a diferencia de `tests/app/identity/`) solo trunca `sessions` y
    `messages` (alcance de la tarea 1.1), no `users`: usar un sufijo unico evita
    colisiones de `uq_users_username` si estos tests corren mas de una vez seguidas
    dentro de la misma base (p. ej. junto al resto de la suite).
    """
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def login(client: TestClient, username: str, pwd: str) -> None:
    """Login simple (sin TOTP): un usuario funcional/tecnico sin acuerdo pendiente
    pasa el `wizard_guard` limpio en una base recien truncada.
    """
    r = client.post("/api/auth/login", json={"username": username, "password": pwd})
    assert r.status_code == 200
    assert r.json() == {"status": "success"}


def post_csrf(client: TestClient, url: str, json: dict[str, Any] | None = None) -> Any:
    """Adjunta el header CSRF a partir de la cookie de sesion actual."""
    csrf_token = client.cookies.get("resultarai_csrf")
    headers = {}
    if csrf_token:
        headers["X-CSRF-Token"] = csrf_token
    return client.post(url, json=json, headers=headers)


def test_create_session_with_default_chat_fixes_initial_model_profile(
    client: TestClient,
) -> None:
    """Crear una sesion con `default_chat` fija el primer perfil de su fallback_cascade."""
    pwd = "ValidPassword123!"
    username = _unique_username("chat-create-user")
    make_user(username, role="funcional", password_hash=hash_password(pwd))
    login(client, username, pwd)

    response = post_csrf(client, "/api/sessions", json={"agent_id": "default_chat"})
    assert response.status_code == 201
    data = response.json()

    assert data["agent_id"] == "default_chat"
    assert data["model_profile"] == "openai_gpt_4o"  # primer elemento de fallback_cascade
    assert data["id"].startswith("sess_")
    assert "created_at" in data

    # Confirmar en base que la sesion quedo asociada al usuario dueño.
    with get_db_session() as db:
        session_row = db.get(SessionModel, data["id"])
        assert session_row is not None
        assert session_row.agent_id == "default_chat"
        assert session_row.model_profile == "openai_gpt_4o"
        assert session_row.owner_user_id is not None


def test_create_session_with_unknown_agent_returns_404_and_creates_nothing(
    client: TestClient,
) -> None:
    """Un agente inexistente en el catalogo devuelve 404 y no crea ninguna sesion."""
    pwd = "ValidPassword123!"
    username = _unique_username("chat-unknown-agent-user")
    make_user(username, role="funcional", password_hash=hash_password(pwd))
    login(client, username, pwd)

    with get_db_session() as db:
        count_before = db.execute(select(SessionModel)).scalars().all()

    response = post_csrf(client, "/api/sessions", json={"agent_id": "agente_que_no_existe"})
    assert response.status_code == 404

    with get_db_session() as db:
        count_after = db.execute(select(SessionModel)).scalars().all()

    assert len(count_after) == len(count_before)


def test_session_model_profile_stickiness_across_turns(client: TestClient) -> None:
    """El model_profile de la sesion no cambia tras turnos posteriores (stickiness).

    El envio real de turnos (`POST /sessions/{id}/messages`) llega en la tarea 1.2 de
    este mismo change; aqui se simula insertando mensajes encadenados directamente via
    SQLAlchemy para verificar que, una vez creada la sesion, ni un turno normal ni
    ningun otro mecanismo cambian su `model_profile` -- invariante reforzado ademas a
    nivel de base por la FK compuesta `(session_id, model_profile)` de `messages` ->
    `sessions` (`uq_sessions_id_model_profile`, b04-persistencia-postgres): un mensaje
    no puede colgar de la sesion con un `model_profile` distinto al fijado al crearla.
    """
    pwd = "ValidPassword123!"
    username = _unique_username("chat-sticky-user")
    make_user(username, role="tecnico", password_hash=hash_password(pwd))
    login(client, username, pwd)

    response = post_csrf(client, "/api/sessions", json={"agent_id": "default_chat"})
    assert response.status_code == 201
    session_id = response.json()["id"]
    original_profile = response.json()["model_profile"]

    with get_db_session() as db:
        user_message = Message(
            session_id=session_id,
            parent_id=None,
            role="user",
            content="hola, esto es un turno de prueba",
            model_profile=original_profile,
        )
        db.add(user_message)
        db.flush()

        assistant_message = Message(
            session_id=session_id,
            parent_id=user_message.id,
            role="assistant",
            content="hola, en que puedo ayudarte",
            model_profile=original_profile,
        )
        db.add(assistant_message)
        db.commit()

    with get_db_session() as db:
        session_row = db.get(SessionModel, session_id)
        assert session_row is not None
        assert session_row.model_profile == original_profile

        messages = (
            db.execute(select(Message).where(Message.session_id == session_id)).scalars().all()
        )
        assert len(messages) == 2
        assert all(m.model_profile == original_profile for m in messages)

    # Un segundo turno posterior, todavia simulado directo en base, confirma que la
    # sesion sigue en el mismo model_profile (ningun turno individual la desvia).
    with get_db_session() as db:
        second_user_message = Message(
            session_id=session_id,
            parent_id=assistant_message.id,
            role="user",
            content="segundo turno",
            model_profile=original_profile,
        )
        db.add(second_user_message)
        db.commit()

    with get_db_session() as db:
        session_row = db.get(SessionModel, session_id)
        assert session_row is not None
        assert session_row.model_profile == original_profile


def test_create_session_requires_authentication(client: TestClient) -> None:
    """Sin cookie de sesion valida, crear una sesion de chat devuelve 401.

    Fija manualmente un par CSRF valido (cookie + header) para que la peticion pase
    el guard de CSRF y el 401 observado sea el de `get_current_user` (falta de
    sesion), no un 403 de CSRF -- ambos guards son independientes y el de CSRF corre
    primero a nivel de aplicacion.
    """
    csrf_token = "fake-csrf-token-for-unauthenticated-request"
    client.cookies.set("resultarai_csrf", csrf_token)

    response = client.post(
        "/api/sessions",
        json={"agent_id": "default_chat"},
        headers={"X-CSRF-Token": csrf_token},
    )
    assert response.status_code == 401
