# ruff: noqa: E402
"""Integration tests for GET /api/agents/{agent_id} (d13-chat-conversacion, tarea 3.5)."""

from __future__ import annotations

import datetime
import os
import uuid
from collections.abc import Iterator
from pathlib import Path

from cryptography.fernet import Fernet

# Fijar una clave estable en el entorno antes de importar nada que inicialice TotpConfig
# (mismo patron que tests/app/identity/test_endpoints.py y tests/app/chat/test_sessions.py).
_STABLE_KEY = Fernet.generate_key().decode("utf-8")
os.environ.setdefault("IDENTITY_TOTP_ENCRYPTION_KEY", _STABLE_KEY)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as DbSession

from resultarai.adapters.persistence_postgres.connection import SessionLocal
from resultarai.app.api import create_app
from resultarai.app.api.chat import get_registries
from resultarai.app.identity import SessionConfig, get_db, get_session_config, hash_password
from resultarai.app.startup import bootstrap
from tests.app.identity.conftest import make_user

_CONFIG = SessionConfig(
    signing_key="test-chat-key-for-agent-lookup",
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
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def login(client: TestClient, username: str, pwd: str) -> None:
    r = client.post("/api/auth/login", json={"username": username, "password": pwd})
    assert r.status_code == 200
    assert r.json() == {"status": "success"}


def test_get_default_chat_agent_returns_starter_prompts_and_escalation_flag(
    client: TestClient,
) -> None:
    """`GET /api/agents/default_chat` expone `starter_prompts`/`escalation_enabled`
    del Agent Manifest real, lo que la vista 05 necesita antes de crear una sesión.
    """
    pwd = "ValidPassword123!"
    username = _unique_username("chat-agent-lookup")
    make_user(username, role="funcional", password_hash=hash_password(pwd))
    login(client, username, pwd)

    response = client.get("/api/agents/default_chat")
    assert response.status_code == 200
    data = response.json()

    assert data["id"] == "default_chat"
    assert data["name"] == "Chat por Defecto"
    assert isinstance(data["starter_prompts"], list)
    assert len(data["starter_prompts"]) >= 1
    assert all(isinstance(item, str) and item for item in data["starter_prompts"])
    assert data["escalation_enabled"] is True


def test_get_unknown_agent_returns_404(client: TestClient) -> None:
    """Un id que no está catalogado (o no es invocable) devuelve 404."""
    pwd = "ValidPassword123!"
    username = _unique_username("chat-agent-missing")
    make_user(username, role="funcional", password_hash=hash_password(pwd))
    login(client, username, pwd)

    response = client.get("/api/agents/agente_que_no_existe")
    assert response.status_code == 404


def test_get_agent_requires_authentication(client: TestClient) -> None:
    """Sin sesión válida, la lectura del agente devuelve 401 (mismo criterio que
    el resto de los endpoints de chat: es una lectura autenticada, no pública).
    """
    response = client.get("/api/agents/default_chat")
    assert response.status_code == 401
