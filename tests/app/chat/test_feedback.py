# ruff: noqa: E402
"""Integration tests for POST /messages/{id}/feedback.

d13-chat-conversacion, tarea 1.8 -- endpoint de feedback exigido por el proposal
(§What Changes: "feedback 👍/👎 por respuesta ligado a la traza, b07-observabilidad").
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
from sqlalchemy.orm import Session as DbSession

from resultarai.adapters.persistence_postgres.connection import SessionLocal
from resultarai.app.api import create_app
from resultarai.app.api.chat import get_feedback_submitter, get_registries, get_response_generator
from resultarai.app.identity import (
    SessionConfig,
    get_db,
    get_session_config,
    hash_password,
)
from resultarai.app.startup import bootstrap
from tests.app.identity.conftest import make_user

_CONFIG = SessionConfig(
    signing_key="test-chat-key-for-feedback",
    idle_timeout=datetime.timedelta(minutes=30),
    absolute_lifetime=datetime.timedelta(hours=8),
    cookie_secure=False,  # deshabilitado Secure para extraer la cookie en el test client
)


class _RecordingFeedbackSubmitter:
    """Doble de `FeedbackSubmitter`: registra cada llamada recibida, en orden --
    permite verificar "reemplazo de voto" como la ÚLTIMA llamada, sin depender del
    modo mock global de Langfuse (`get_langfuse_client`).
    """

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def __call__(self, *, trace_id: str, value: int, comment: str | None) -> None:
        self.calls.append({"trace_id": trace_id, "value": value, "comment": comment})


class _EchoResponseGenerator:
    """Doble mínimo de `ResponseGenerator`: texto fijo, no depende de ningún LLM."""

    def __call__(self, *, session: Any, history: Any) -> str:
        return "respuesta del agente"


@pytest.fixture
def feedback_submitter() -> _RecordingFeedbackSubmitter:
    return _RecordingFeedbackSubmitter()


@pytest.fixture
def response_generator() -> _EchoResponseGenerator:
    return _EchoResponseGenerator()


@pytest.fixture
def client(
    feedback_submitter: _RecordingFeedbackSubmitter,
    response_generator: _EchoResponseGenerator,
) -> Iterator[TestClient]:
    """TestClient con overrides de DB, config de sesión, Registries reales, el
    doble de generación de respuesta síncrona y el doble de `FeedbackSubmitter`.
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
    app.dependency_overrides[get_feedback_submitter] = lambda: feedback_submitter

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


def _feedback(client: TestClient, message_id: str, vote: str, comment: str | None = None) -> Any:
    payload: dict[str, Any] = {"vote": vote}
    if comment is not None:
        payload["comment"] = comment
    return post_csrf(client, f"/api/messages/{message_id}/feedback", json=payload)


def test_feedback_up_without_comment_is_registered(
    client: TestClient, feedback_submitter: _RecordingFeedbackSubmitter
) -> None:
    """Votar 👍 sin comentario se registra ligado a la respuesta evaluada."""
    _create_user_and_login(client, "feedback-up")
    session_id = _create_session(client)
    turn = _send_message(client, session_id, "hola")
    assert turn.status_code == 201
    assistant_message_id = turn.json()["assistant_message"]["id"]

    response = _feedback(client, assistant_message_id, "up")
    assert response.status_code == 201
    data = response.json()
    assert data["message_id"] == assistant_message_id
    assert data["vote"] == "up"
    assert data["trace_id"]

    assert len(feedback_submitter.calls) == 1
    call = feedback_submitter.calls[0]
    assert call["value"] == 1
    assert call["comment"] is None
    assert call["trace_id"] == data["trace_id"]


def test_feedback_vote_change_replaces_previous_vote(
    client: TestClient, feedback_submitter: _RecordingFeedbackSubmitter
) -> None:
    """Cambiar de 👍 a 👎 sobre el mismo mensaje: el voto vigente queda en 👎,
    verificable como la ÚLTIMA llamada recibida por el doble del adapter -- ver el
    desvío documentado en `use_cases/chat/feedback.py`: `b07` es append-only por
    diseño (contract test `test_append_only_score_updates`), así que "reemplazar"
    nunca muta ni borra el score anterior en Langfuse, solo reenvía uno nuevo.
    """
    _create_user_and_login(client, "feedback-replace")
    session_id = _create_session(client)
    turn = _send_message(client, session_id, "hola de nuevo")
    assert turn.status_code == 201
    assistant_message_id = turn.json()["assistant_message"]["id"]

    up = _feedback(client, assistant_message_id, "up", comment="me sirvió")
    assert up.status_code == 201
    assert up.json()["vote"] == "up"

    down = _feedback(client, assistant_message_id, "down", comment="en realidad no")
    assert down.status_code == 201
    assert down.json()["vote"] == "down"

    # Nunca se muta el score anterior: quedan DOS llamadas, ambas conservadas.
    assert len(feedback_submitter.calls) == 2
    assert feedback_submitter.calls[0]["value"] == 1
    assert feedback_submitter.calls[0]["comment"] == "me sirvió"
    # El voto VIGENTE es la última llamada emitida.
    assert feedback_submitter.calls[-1]["value"] == 0
    assert feedback_submitter.calls[-1]["comment"] == "en realidad no"
    # Ligado al mismo mensaje en ambos casos (mismo trace_id derivado).
    assert feedback_submitter.calls[0]["trace_id"] == feedback_submitter.calls[-1]["trace_id"]


def test_feedback_on_foreign_message_returns_404(
    client: TestClient, feedback_submitter: _RecordingFeedbackSubmitter
) -> None:
    """Calificar un mensaje de una sesión ajena responde 404 sin registrar nada."""
    _create_user_and_login(client, "feedback-owner")
    session_id = _create_session(client)
    turn = _send_message(client, session_id, "hola")
    assert turn.status_code == 201
    assistant_message_id = turn.json()["assistant_message"]["id"]

    _create_user_and_login(client, "feedback-intruder")
    response = _feedback(client, assistant_message_id, "up")
    assert response.status_code == 404
    assert feedback_submitter.calls == []


def test_feedback_on_user_message_returns_422(
    client: TestClient, feedback_submitter: _RecordingFeedbackSubmitter
) -> None:
    """Solo se puede calificar una respuesta del agente, no el mensaje de usuario."""
    _create_user_and_login(client, "feedback-invalid")
    session_id = _create_session(client)
    turn = _send_message(client, session_id, "hola")
    assert turn.status_code == 201
    user_message_id = turn.json()["user_message"]["id"]

    response = _feedback(client, user_message_id, "down")
    assert response.status_code == 422
    assert feedback_submitter.calls == []


def test_feedback_unknown_message_returns_404(
    client: TestClient, feedback_submitter: _RecordingFeedbackSubmitter
) -> None:
    """Calificar un `message_id` que no existe responde 404 sin registrar nada."""
    _create_user_and_login(client, "feedback-unknown")
    response = _feedback(client, str(uuid.uuid4()), "up")
    assert response.status_code == 404
    assert feedback_submitter.calls == []
