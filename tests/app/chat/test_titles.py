# ruff: noqa: E402
"""Integration and unit tests for session title generation (tarea 2.2).

d13-chat-conversacion, tarea 2.2: generación automática de título a partir del
primer turno, editable por el usuario sin regeneración posterior.
"""

from __future__ import annotations

import datetime
import os
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet

# Fijar una clave estable en el entorno antes de importar nada que inicialice TotpConfig.
_STABLE_KEY = Fernet.generate_key().decode("utf-8")
os.environ.setdefault("IDENTITY_TOTP_ENCRYPTION_KEY", _STABLE_KEY)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as DbSession

from resultarai.adapters.persistence_postgres.connection import SessionLocal, get_db_session
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
from resultarai.app.use_cases.chat.titles import generate_session_title
from tests.app.identity.conftest import make_user

_CONFIG = SessionConfig(
    signing_key="test-chat-key-for-titles",
    idle_timeout=datetime.timedelta(minutes=30),
    absolute_lifetime=datetime.timedelta(hours=8),
    cookie_secure=False,
)


class _CountingResponseGenerator:
    """Doble de `ResponseGenerator`: devuelve texto distinto en cada llamada."""

    def __init__(self) -> None:
        self.calls = 0

    def __call__(self, *, session: Any, history: Any) -> str:
        self.calls += 1
        return f"respuesta generada #{self.calls}"


@pytest.fixture
def response_generator() -> _CountingResponseGenerator:
    return _CountingResponseGenerator()


@pytest.fixture
def client(response_generator: _CountingResponseGenerator) -> Iterator[TestClient]:
    """TestClient con overrides de DB, config de sesión, Registries reales y el doble."""
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
    """Genera un username único por invocación."""
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


def patch_csrf(client: TestClient, url: str, json: dict[str, Any] | None = None) -> Any:
    """Adjunta el header CSRF a un PATCH."""
    csrf_token = client.cookies.get("resultarai_csrf")
    headers = {}
    if csrf_token:
        headers["X-CSRF-Token"] = csrf_token
    return client.patch(url, json=json, headers=headers)


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
    payload = {"text": text}
    return post_csrf(client, f"/api/sessions/{session_id}/messages", json=payload)


# --- Unit tests de generate_session_title ----------------------------------------


def test_generate_title_short_text_unchanged() -> None:
    """Un texto corto (< 60 chars) se devuelve sin cambios."""
    text = "¿Cuánto es 2 + 2?"
    result = generate_session_title(text)
    assert result == text


def test_generate_title_collapses_whitespace() -> None:
    """Los saltos de línea y espacios múltiples se colapsan a espacio simple."""
    text = "Hola\n\n   mundo   \t\t\n   aquí"
    result = generate_session_title(text)
    assert result == "Hola mundo aquí"


def test_generate_title_long_text_truncates_at_space() -> None:
    """Un texto largo se recorta en el último espacio antes del límite y agrega '…'."""
    text = "Este es un texto muy largo que excede el límite de sesenta caracteres de propósito"
    result = generate_session_title(text)
    # Verifica que se cortó en un espacio (no en mitad de palabra).
    assert len(result) <= 60
    assert result.endswith("…")
    # El texto antes de '…' debe terminar en un espacio o ser una palabra completa.
    assert not result.endswith(" …")


def test_generate_title_empty_text_returns_default() -> None:
    """Texto vacío o solo espacios retorna el fallback."""
    assert generate_session_title("") == "Nueva conversación"
    assert generate_session_title("   ") == "Nueva conversación"
    assert generate_session_title("\n\n") == "Nueva conversación"


def test_generate_title_exact_limit() -> None:
    """Texto de exactamente 60 caracteres se devuelve sin truncar."""
    text = "a" * 60
    result = generate_session_title(text)
    assert result == text
    assert not result.endswith("…")


def test_generate_title_one_char_over_limit() -> None:
    """Texto de 61 caracteres se trunca y agrega '…'."""
    text = "a" * 61
    result = generate_session_title(text)
    assert result.endswith("…")
    # El resultado es 60 'a' + "…" = 61 caracteres (máximo de 60 + ellipsis).
    assert len(result) == 61
    assert result == "a" * 60 + "…"


def test_generate_title_word_longer_than_limit() -> None:
    """Una palabra individual más larga que 60 chars se trunca a 60 y agrega '…'."""
    text = "a" * 70
    result = generate_session_title(text)
    assert len(result) == 61  # 60 chars de 'a' + "…"
    assert result.endswith("…")


# --- Integration tests -------------------------------------------------------


def test_auto_title_generated_on_first_turn(client: TestClient) -> None:
    """La sesión genera un título automático completado el primer turno."""
    _create_user_and_login(client, "title-auto")
    session_id = _create_session(client)

    # Sesión recién creada: title es None.
    with get_db_session() as db:
        session_row = db.get(SessionModel, session_id)
        assert session_row is not None
        assert session_row.title is None
        assert session_row.title_edited is False

    # Envía el primer mensaje.
    user_text = "¿Cuál es la capital de Francia?"
    response = _send_message(client, session_id, user_text)
    assert response.status_code == 201

    # El título se genera a partir del primer mensaje.
    with get_db_session() as db:
        session_row = db.get(SessionModel, session_id)
        assert session_row is not None
        assert session_row.title == generate_session_title(user_text)
        assert session_row.title_edited is False


def test_title_not_regenerated_on_second_turn(client: TestClient) -> None:
    """El título se genera en el primer turno y no cambia en turnos posteriores."""
    _create_user_and_login(client, "title-stability")
    session_id = _create_session(client)

    # Primer turno.
    first_text = "Primer mensaje"
    response1 = _send_message(client, session_id, first_text)
    assert response1.status_code == 201

    with get_db_session() as db:
        session_row = db.get(SessionModel, session_id)
        assert session_row is not None
        first_title = session_row.title
        assert first_title == generate_session_title(first_text)

    # Segundo turno.
    second_text = (
        "Un texto completamente diferente y mucho más largo para que generara otro "
        "título si no fuera protegido"
    )
    response2 = _send_message(client, session_id, second_text)
    assert response2.status_code == 201

    # El título no cambió.
    with get_db_session() as db:
        session_row = db.get(SessionModel, session_id)
        assert session_row is not None
        assert session_row.title == first_title
        assert session_row.title_edited is False


def test_edit_title_via_patch(client: TestClient) -> None:
    """PATCH /sessions/{id} edita el título y marca como editado manualmente."""
    _create_user_and_login(client, "title-edit")
    session_id = _create_session(client)

    # Primer turno para generar un título automático.
    response = _send_message(client, session_id, "Primer mensaje")
    assert response.status_code == 201

    with get_db_session() as db:
        session_row = db.get(SessionModel, session_id)
        assert session_row is not None
        assert session_row.title is not None
        assert session_row.title_edited is False

    # Edita el título.
    new_title = "Mi título personalizado"
    patch_response = patch_csrf(client, f"/api/sessions/{session_id}", json={"title": new_title})
    assert patch_response.status_code == 200
    patch_data = patch_response.json()
    assert patch_data["id"] == session_id
    assert patch_data["title"] == new_title
    assert patch_data["title_edited"] is True

    with get_db_session() as db:
        session_row = db.get(SessionModel, session_id)
        assert session_row is not None
        assert session_row.title == new_title
        assert session_row.title_edited is True


def test_title_not_regenerated_after_manual_edit(client: TestClient) -> None:
    """Tras editar manualmente el título, un nuevo turno no lo regenera."""
    _create_user_and_login(client, "title-protect")
    session_id = _create_session(client)

    # Primer turno.
    response1 = _send_message(client, session_id, "Primer mensaje")
    assert response1.status_code == 201

    # Edita el título.
    new_title = "Título editado"
    patch_response = patch_csrf(client, f"/api/sessions/{session_id}", json={"title": new_title})
    assert patch_response.status_code == 200

    # Segundo turno.
    response2 = _send_message(client, session_id, "Segundo mensaje")
    assert response2.status_code == 201

    # El título sigue siendo el que editó manualmente.
    with get_db_session() as db:
        session_row = db.get(SessionModel, session_id)
        assert session_row is not None
        assert session_row.title == new_title
        assert session_row.title_edited is True


def test_patch_foreign_session_returns_404(client: TestClient) -> None:
    """Editar el título de una sesión ajena retorna 404."""
    _create_user_and_login(client, "title-owner")
    session_id = _create_session(client)
    _send_message(client, session_id, "Mensaje del dueño")

    _create_user_and_login(client, "title-intruder")
    response = patch_csrf(client, f"/api/sessions/{session_id}", json={"title": "Intento ajeno"})
    assert response.status_code == 404

    # El título original se mantiene intacto.
    with get_db_session() as db:
        session_row = db.get(SessionModel, session_id)
        assert session_row is not None
        original_title = session_row.title
        assert original_title is not None


def test_patch_title_empty_returns_422(client: TestClient) -> None:
    """PATCH con título vacío o solo espacios retorna 422."""
    _create_user_and_login(client, "title-validation")
    session_id = _create_session(client)
    _send_message(client, session_id, "Mensaje")

    # Intenta con string vacío.
    response1 = patch_csrf(client, f"/api/sessions/{session_id}", json={"title": ""})
    assert response1.status_code == 422

    # Intenta con solo espacios.
    response2 = patch_csrf(client, f"/api/sessions/{session_id}", json={"title": "   "})
    assert response2.status_code == 422

    # El título original no cambió.
    with get_db_session() as db:
        session_row = db.get(SessionModel, session_id)
        assert session_row is not None
        assert session_row.title is not None


def test_patch_title_exceeds_max_length_returns_422(client: TestClient) -> None:
    """PATCH con título > 120 caracteres retorna 422."""
    _create_user_and_login(client, "title-max")
    session_id = _create_session(client)
    _send_message(client, session_id, "Mensaje")

    # Título de 121 caracteres.
    oversized_title = "a" * 121
    response = patch_csrf(client, f"/api/sessions/{session_id}", json={"title": oversized_title})
    assert response.status_code == 422


def test_patch_title_max_length_accepted(client: TestClient) -> None:
    """PATCH con título de exactamente 120 caracteres es aceptado."""
    _create_user_and_login(client, "title-max-ok")
    session_id = _create_session(client)
    _send_message(client, session_id, "Mensaje")

    # Título de 120 caracteres.
    max_title = "a" * 120
    response = patch_csrf(client, f"/api/sessions/{session_id}", json={"title": max_title})
    assert response.status_code == 200
    assert response.json()["title"] == max_title


def test_auto_title_with_multiline_first_message(client: TestClient) -> None:
    """El título automático colapsa saltos de línea en el primer mensaje."""
    _create_user_and_login(client, "title-multiline")
    session_id = _create_session(client)

    # Mensaje con saltos de línea.
    user_text = "Primera línea\nSegunda línea\n\nTercera línea"
    response = _send_message(client, session_id, user_text)
    assert response.status_code == 201

    with get_db_session() as db:
        session_row = db.get(SessionModel, session_id)
        assert session_row is not None
        assert session_row.title == "Primera línea Segunda línea Tercera línea"
