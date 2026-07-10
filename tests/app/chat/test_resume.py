# ruff: noqa: E402
"""Integration tests de la tarea 2.5 (d13-chat-conversacion): "reanudar" una sesión.

Cubre el requirement "Reanudar sesión en su última rama activa"
(`openspec/changes/d13-chat-conversacion/specs/session-history/spec.md`): abrir una
sesión existente carga posicionada en su última rama activa, y si un turno seguía en
streaming en otra pestaña/dispositivo, el sistema reconcilia sin duplicarlo -- el
turno aparece UNA sola vez con su estado más reciente.

Reutiliza los dobles y helpers de `test_streaming.py` (mismo
`_PausableStreamingDoubleGenerator` para pausar un turno a mitad de generación, mismos
helpers de parseo SSE/hilo) para no duplicar esa infraestructura; lo propio de este
módulo es tener DOS `TestClient` independientes -- "dos pestañas" -- autenticados como
el MISMO usuario sobre la MISMA app (mismo `TurnStreamRegistry` de proceso), algo que
ningún test de `test_streaming.py` necesita.
"""

from __future__ import annotations

import datetime
import os
import threading
import time
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet

# Fijar una clave estable en el entorno antes de importar nada que inicialice TotpConfig
# (mismo patrón que tests/app/chat/test_streaming.py).
_STABLE_KEY = Fernet.generate_key().decode("utf-8")
os.environ.setdefault("IDENTITY_TOTP_ENCRYPTION_KEY", _STABLE_KEY)

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from resultarai.adapters.persistence_postgres.connection import SessionLocal, get_db_session
from resultarai.adapters.persistence_postgres.models import Message
from resultarai.app.api import create_app
from resultarai.app.api.chat import get_registries, get_turn_stream_registry
from resultarai.app.api.chat_stream import get_streaming_response_generator
from resultarai.app.identity import (
    SessionConfig,
    get_db,
    get_session_config,
    hash_password,
)
from resultarai.app.startup import bootstrap
from resultarai.app.use_cases.chat.stream_registry import TurnStreamRegistry
from resultarai.core.registries import Registries
from tests.app.chat.test_streaming import (
    _create_session,
    _parse_sse,
    _PausableStreamingDoubleGenerator,
    _start_stream_in_thread,
    _unique_username,
    _wait_until,
    login,
    post_csrf,
)
from tests.app.identity.conftest import make_user

_CONFIG = SessionConfig(
    signing_key="test-chat-key-for-resume",
    idle_timeout=datetime.timedelta(minutes=30),
    absolute_lifetime=datetime.timedelta(hours=8),
    cookie_secure=False,  # deshabilitado Secure para extraer la cookie en el test client
)


@pytest.fixture
def pausable_generator() -> _PausableStreamingDoubleGenerator:
    """Instancia vacía: cada test fija `chunks`/`pause_before_index` antes de usarla
    (mismo patrón que `test_streaming.py`).
    """
    return _PausableStreamingDoubleGenerator([], pause_before_index=0)


@pytest.fixture
def registries() -> Registries:
    """Registries reales de `manifests/` (mismo motivo que en `test_streaming.py`:
    una instancia propia por test, compartida por ambos `TestClient` de la misma app).
    """
    return bootstrap(Path("manifests"))


@pytest.fixture
def turn_registry() -> TurnStreamRegistry:
    """Registro de buffers propio del test: se inyecta en la app para poder observar
    el turno en curso sin sondeos ciegos (mismo motivo que `test_streaming.py`).
    """
    return TurnStreamRegistry()


def _build_app(
    pausable_generator: _PausableStreamingDoubleGenerator,
    registries_instance: Registries,
    turn_registry_instance: TurnStreamRegistry,
) -> FastAPI:
    """Construye una única app con los overrides comunes -- DOS `TestClient`
    independientes sobre esta MISMA app simulan "dos pestañas" del mismo usuario,
    compartiendo el mismo `TurnStreamRegistry` de proceso (mismo criterio que
    `test_list_sessions_never_leaks_across_users` de `test_history.py`, que usa dos
    `TestClient` sobre una app para aislar cookies de sesión sin aislar el proceso).

    No se sobreescribe `get_response_generator` (el turno síncrono no-streaming):
    ningún test de este módulo lo ejercita.
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
    app.dependency_overrides[get_registries] = lambda: registries_instance
    app.dependency_overrides[get_streaming_response_generator] = lambda: pausable_generator
    app.dependency_overrides[get_turn_stream_registry] = lambda: turn_registry_instance
    return app


@contextmanager
def _same_user_two_clients(
    app: FastAPI, prefix: str
) -> Iterator[tuple[TestClient, TestClient, str]]:
    """Crea un único usuario y lo autentica en DOS `TestClient` independientes sobre
    `app` -- "dos pestañas/dispositivos" del mismo usuario, cada una con su propia
    cookie de sesión (login no revoca sesiones previas del mismo usuario, ver
    `resultarai/app/use_cases/identity.py`, `login_user`: cada login crea una
    `AuthSession` nueva). Produce `(client_a, client_b, username)`.
    """
    pwd = "ValidPassword123!"
    username = _unique_username(prefix)
    make_user(username, role="funcional", password_hash=hash_password(pwd))

    with TestClient(app) as client_a, TestClient(app) as client_b:
        login(client_a, username, pwd)
        login(client_b, username, pwd)
        yield client_a, client_b, username


# --- Test principal: reconciliación sin duplicar el turno ---------------------------


def test_resume_reconciles_in_progress_turn_without_duplicating(
    pausable_generator: _PausableStreamingDoubleGenerator,
    registries: Registries,
    turn_registry: TurnStreamRegistry,
) -> None:
    """Cliente A arranca un turno pausado a mitad de generación; cliente B (misma
    sesión de usuario, "otra pestaña") abre la sesión y ve el mensaje de usuario UNA
    sola vez, sin respuesta de agente persistida todavía, más `in_progress_turn` con
    el turno vivo. B se re-attachea a la reconexión (tarea 1.6) usando ese `turn_id` y,
    tras despausar, recibe el resto del turno. Al final el árbol persistido tiene UN
    solo mensaje de usuario y UNA sola respuesta (verificado con una consulta directa
    a la base, sin pasar por la API) -- el turno nunca se duplicó, y `active_leaf_id`
    apunta a la respuesta recién cerrada (rama más reciente).
    """
    pausable_generator.chunks = ["Hola", ", mundo", "!"]
    pausable_generator.pause_before_index = 1  # pausa justo antes de ", mundo"

    app = _build_app(pausable_generator, registries, turn_registry)
    with _same_user_two_clients(app, "resume-main") as (client_a, client_b, _username):
        session_id = _create_session(client_a)

        post_thread, post_result = _start_stream_in_thread(client_a, session_id, "hola")

        assert pausable_generator.reached_pause.wait(timeout=10.0), "el doble nunca se pausó"

        # Cliente B abre la sesión mientras el turno de A sigue vivo.
        detail_response = client_b.get(f"/api/sessions/{session_id}")
        assert detail_response.status_code == 200
        detail = detail_response.json()

        user_messages = [m for m in detail["messages"] if m["role"] == "user"]
        assistant_messages = [m for m in detail["messages"] if m["role"] == "assistant"]
        assert len(user_messages) == 1, "el mensaje de usuario aparece una sola vez"
        assert assistant_messages == [], "la respuesta todavía no se persistió"

        in_progress = detail["in_progress_turn"]
        assert in_progress is not None
        turn_id = in_progress["turn_id"]
        assert turn_id.startswith("turn_")
        assert in_progress["user_message_id"] == user_messages[0]["id"]
        last_event_id = in_progress["last_event_id"]
        assert last_event_id >= 1, "ya hay al menos el primer fragmento bufferizado"

        # B se re-attachea a la reconexión (tarea 1.6) con el `turn_id` reconciliado,
        # en vez de reenviar el mismo texto (lo que duplicaría el turno).
        reconnect_result: dict[str, Any] = {}

        def _reconnect() -> None:
            reconnect_result["response"] = client_b.get(
                f"/api/turns/{turn_id}/stream",
                headers={"Last-Event-ID": str(last_event_id)},
            )

        reconnect_thread = threading.Thread(target=_reconnect)
        reconnect_thread.start()

        time.sleep(0.2)
        pausable_generator.resume.set()

        reconnect_thread.join(timeout=10.0)
        post_thread.join(timeout=10.0)
        assert not reconnect_thread.is_alive()
        assert not post_thread.is_alive()

        reconnect_response = reconnect_result["response"]
        assert reconnect_response.status_code == 200
        events, _ = _parse_sse(reconnect_response.text)
        assert events[-1]["event"] == "done"

        original_response = post_result["response"]
        assert original_response.status_code == 200

        # Persistencia final: consulta directa, sin pasar por la API -- UN mensaje de
        # usuario, UNA respuesta, nada duplicado por la reconciliación de B.
        with get_db_session() as db:
            messages = (
                db.execute(select(Message).where(Message.session_id == session_id)).scalars().all()
            )
        final_user_messages = [m for m in messages if m.role == "user"]
        final_assistant_messages = [m for m in messages if m.role == "assistant"]
        assert len(final_user_messages) == 1
        assert len(final_assistant_messages) == 1
        assert final_assistant_messages[0].content == "Hola, mundo!"
        assert final_assistant_messages[0].status == "complete"

        # `active_leaf_id` sigue correcto tras el cierre: apunta a la respuesta recién
        # cerrada (la rama más reciente de la sesión).
        final_detail = client_a.get(f"/api/sessions/{session_id}").json()
        assert final_detail["active_leaf_id"] == str(final_assistant_messages[0].id)
        assert final_detail["in_progress_turn"] is None


# --- Garantía server-side: un solo turno en curso por sesión -------------------------


def test_second_client_send_while_turn_in_progress_returns_409_then_succeeds_after_close(
    pausable_generator: _PausableStreamingDoubleGenerator,
    registries: Registries,
    turn_registry: TurnStreamRegistry,
) -> None:
    """Mientras el turno de A sigue en curso, B intenta `POST .../messages/stream`
    (el "reenviar" accidental que la reconciliación busca evitar): responde 409 con
    el `turn_id` del turno vivo, sin crear ningún mensaje nuevo. Cerrado el turno de
    A, el mismo endpoint vuelve a funcionar normalmente para B.
    """
    pausable_generator.chunks = ["Hola", "!"]
    pausable_generator.pause_before_index = 1

    app = _build_app(pausable_generator, registries, turn_registry)
    with _same_user_two_clients(app, "resume-409") as (client_a, client_b, _username):
        session_id = _create_session(client_a)

        post_thread, post_result = _start_stream_in_thread(client_a, session_id, "primero")
        assert pausable_generator.reached_pause.wait(timeout=10.0), "el doble nunca se pausó"

        with get_db_session() as db:
            live_user_message = (
                db.execute(
                    select(Message).where(Message.session_id == session_id, Message.role == "user")
                )
                .scalars()
                .one()
            )
        live_buffer = turn_registry.get_by_user_message_id(live_user_message.id)
        assert live_buffer is not None

        response = post_csrf(
            client_b,
            f"/api/sessions/{session_id}/messages/stream",
            json={"text": "reenvío accidental desde otra pestaña"},
        )
        assert response.status_code == 409
        assert response.json()["detail"] == {"turn_id": live_buffer.turn_id}

        # No se creó ningún mensaje nuevo por el intento rechazado.
        with get_db_session() as db:
            messages_after_409 = (
                db.execute(select(Message).where(Message.session_id == session_id)).scalars().all()
            )
        assert len(messages_after_409) == 1  # solo el mensaje de usuario del turno de A

        pausable_generator.resume.set()
        post_thread.join(timeout=10.0)
        assert not post_thread.is_alive()
        assert post_result["response"].status_code == 200
        assert _wait_until(lambda: live_buffer.closed)

        # Turno cerrado: el mismo endpoint vuelve a funcionar para B.
        response = post_csrf(
            client_b,
            f"/api/sessions/{session_id}/messages/stream",
            json={"text": "segundo turno, ya sin conflicto"},
        )
        assert response.status_code == 200
        events, _ = _parse_sse(response.text)
        assert events[-1]["event"] == "done"

        with get_db_session() as db:
            final_messages = (
                db.execute(select(Message).where(Message.session_id == session_id)).scalars().all()
            )
        assert len(final_messages) == 4  # dos turnos completos (usuario + agente cada uno)


# --- Caso base: sin turno vivo, `in_progress_turn` es null ---------------------------


def test_session_without_live_turn_has_null_in_progress_turn(
    pausable_generator: _PausableStreamingDoubleGenerator,
    registries: Registries,
    turn_registry: TurnStreamRegistry,
) -> None:
    """Una sesión sin ningún turno en streaming en curso expone `in_progress_turn: null`
    -- incluso si tiene mensajes persistidos de un turno ya cerrado.
    """
    pausable_generator.chunks = ["respuesta completa, sin pausas"]
    pausable_generator.pause_before_index = 99  # nunca se alcanza: no hay pausa

    app = _build_app(pausable_generator, registries, turn_registry)
    with _same_user_two_clients(app, "resume-no-live-turn") as (client_a, client_b, _username):
        session_id = _create_session(client_a)

        response = client_a.get(f"/api/sessions/{session_id}")
        assert response.status_code == 200
        assert response.json()["in_progress_turn"] is None

        # Turno completo y cerrado; sigue sin haber ningún turno en curso.
        stream_response = post_csrf(
            client_a, f"/api/sessions/{session_id}/messages/stream", json={"text": "hola"}
        )
        assert stream_response.status_code == 200

        response = client_b.get(f"/api/sessions/{session_id}")
        assert response.status_code == 200
        assert response.json()["in_progress_turn"] is None
