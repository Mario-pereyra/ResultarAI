# ruff: noqa: E402
"""Test de contrato SSE end-to-end sobre un servidor `uvicorn` REAL (tarea 9.4,
d13-chat-conversacion).

`tests/app/chat/test_streaming.py` y `test_resume.py` ya prueban la reconexión por
`Last-Event-ID` a NIVEL DE CONTRATO usando `TestClient` de Starlette -- pero
`TestClient` bufferiza el body completo de la respuesta antes de devolverla
(`TestClientTransport.handle_request`), así que NO puede simular un corte físico de la
conexión a mitad de un stream: el "corte" de esos tests es una construcción a nivel de
contrato (turno pausado + reconexión con `Last-Event-ID: N`), no un socket TCP real
cortándose (descubrimiento documentado en `openspec/BACKLOG-DESCUBRIMIENTOS.md`, tarea
1.6). Este módulo cierra ese hueco: levanta la app real en un `uvicorn.Server` de
verdad, escuchando en un socket TCP efímero (`port=0`) en un hilo aparte, y usa
`httpx.Client` para abrir la conexión SSE, leer solo los primeros eventos por el cable,
y CERRAR la conexión sin consumir el resto -- un corte físico de verdad, verificado
empíricamente: `httpx` no puede devolver al pool una conexión HTTP/1.1 con el body a
medio leer, así que la cierra.

Reutiliza las clases doble de `test_streaming.py` (`_PausableStreamingDoubleGenerator`,
`_StreamingDoubleGenerator`) y el helper `_wait_until` -- mismo patrón ya establecido
por `test_resume.py` (que importa de `test_streaming.py` en vez de duplicar) -- pero
NO sus fixtures `pausable_generator`/`streaming_generator`/`registries`/
`turn_registry`: se redefinen localmente (mismo criterio que `test_resume.py`) para no
generar imports "usados solo por nombre de parámetro" que `ruff` (F401) marcaría como
no usados. Tampoco reutiliza `login`/`post_csrf`/`_create_session` (tipados para
`TestClient`): este módulo define sus propios equivalentes tipados para `httpx.Client`,
ya que ambos clientes exponen APIs compatibles en tiempo de ejecución pero no son el
mismo tipo bajo `mypy --strict`.

Lo propio de este módulo es el servidor `uvicorn` real (`_LiveServer`) y los helpers de
`httpx.Client` para consumir SSE de forma incremental y perezosa (`_iter_sse_frames`),
en vez de esperar a que el body completo del stream esté disponible.
"""

from __future__ import annotations

import datetime
import json
import os
import threading
import time
import uuid
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet

# Fijar una clave estable en el entorno antes de importar nada que inicialice TotpConfig
# (mismo patrón que tests/app/chat/test_streaming.py y test_resume.py).
_STABLE_KEY = Fernet.generate_key().decode("utf-8")
os.environ.setdefault("IDENTITY_TOTP_ENCRYPTION_KEY", _STABLE_KEY)

import httpx
import pytest
import uvicorn
from fastapi import FastAPI
from sqlalchemy.orm import Session as DbSession

from resultarai.adapters.persistence_postgres.connection import SessionLocal, get_db_session
from resultarai.adapters.persistence_postgres.models import Message
from resultarai.app.api import create_app
from resultarai.app.api.chat import get_registries
from resultarai.app.api.chat_stream import (
    get_streaming_response_generator,
    get_turn_stream_registry,
)
from resultarai.app.identity import SessionConfig, get_db, get_session_config, hash_password
from resultarai.app.startup import bootstrap
from resultarai.app.use_cases.chat.stream_registry import TurnStreamRegistry
from resultarai.core.registries import Registries
from tests.app.chat.test_streaming import (
    _PausableStreamingDoubleGenerator,
    _StreamingDoubleGenerator,
    _unique_username,
    _wait_until,
)
from tests.app.identity.conftest import make_user

_CONFIG = SessionConfig(
    signing_key="test-chat-key-for-sse-contract-uvicorn",
    idle_timeout=datetime.timedelta(minutes=30),
    absolute_lifetime=datetime.timedelta(hours=8),
    cookie_secure=False,  # deshabilitado Secure: httpx habla HTTP plano al servidor de prueba
)


# --- Servidor uvicorn real (fixture) -------------------------------------------------


class _LiveServer:
    """Servidor `uvicorn` real corriendo en un hilo, escuchando en un puerto TCP
    efímero (`port=0`): a diferencia de `TestClient`, expone un socket de verdad sobre
    el que `httpx.Client` puede cortar la conexión físicamente.
    """

    def __init__(self, app: FastAPI) -> None:
        config = uvicorn.Config(
            app,
            host="127.0.0.1",
            port=0,
            log_level="warning",
            # Acota el apagado: en teardown ya no debería haber conexiones vivas (los
            # tests consumen sus streams hasta el cierre o los cortan explícitamente),
            # pero si alguna quedara colgada, no se quiere que el teardown se cuelgue.
            timeout_graceful_shutdown=1,
        )
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, daemon=True)

    def start(self) -> None:
        """Arranca el servidor y bloquea hasta que `server.started` es verdadero.

        `uvicorn.Server.capture_signals` ya no instala manejadores de señales fuera
        del hilo principal (los ignora en silencio), así que no hace falta
        sobreescribirlo -- verificado leyendo la implementación instalada.
        """
        self._thread.start()
        deadline = time.monotonic() + 10.0
        while not self._server.started:
            if time.monotonic() > deadline:
                raise RuntimeError("uvicorn no arrancó a tiempo (server.started nunca fue True)")
            time.sleep(0.01)

    @property
    def base_url(self) -> str:
        """URL base con el puerto efímero real, resuelto recién tras `start()`."""
        port = self._server.servers[0].sockets[0].getsockname()[1]
        return f"http://127.0.0.1:{port}"

    def stop(self) -> None:
        """Señala el apagado y espera (acotado) a que el hilo del servidor termine."""
        self._server.should_exit = True
        self._thread.join(timeout=10.0)


@pytest.fixture
def live_server_factory() -> Iterator[Callable[[FastAPI], _LiveServer]]:
    """Fábrica de `_LiveServer` con teardown limpio automático al final del test."""
    servers: list[_LiveServer] = []

    def _factory(app: FastAPI) -> _LiveServer:
        server = _LiveServer(app)
        server.start()
        servers.append(server)
        return server

    yield _factory

    for server in servers:
        server.stop()


def _build_live_app(
    streaming_response_generator: Any,
    registries_instance: Registries,
    turn_registry_instance: TurnStreamRegistry,
) -> FastAPI:
    """Construye la app real con los mismos overrides que `test_streaming.py`
    (`_build_test_client`), pero sin `get_response_generator` (el turno síncrono):
    ningún test de este módulo lo ejercita, igual que `test_resume.py`.
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
    app.dependency_overrides[get_streaming_response_generator] = lambda: (
        streaming_response_generator
    )
    app.dependency_overrides[get_turn_stream_registry] = lambda: turn_registry_instance
    return app


# --- Fixtures de dobles/registries (redefinidas localmente, ver docstring del módulo) --


@pytest.fixture
def pausable_generator() -> _PausableStreamingDoubleGenerator:
    return _PausableStreamingDoubleGenerator([], pause_before_index=0)


@pytest.fixture
def streaming_generator() -> _StreamingDoubleGenerator:
    return _StreamingDoubleGenerator(["hola ", "mundo"])


@pytest.fixture
def registries() -> Registries:
    return bootstrap(Path("manifests"))


@pytest.fixture
def turn_registry() -> TurnStreamRegistry:
    return TurnStreamRegistry()


# --- Helpers de auth/SSE tipados para httpx.Client ------------------------------------


def _login_live(client: httpx.Client, username: str, pwd: str) -> None:
    response = client.post("/api/auth/login", json={"username": username, "password": pwd})
    assert response.status_code == 200
    assert response.json() == {"status": "success"}


def _post_csrf_live(client: httpx.Client, url: str, json_body: dict[str, Any]) -> httpx.Response:
    csrf_token = client.cookies.get("resultarai_csrf")
    headers = {"X-CSRF-Token": csrf_token} if csrf_token else {}
    return client.post(url, json=json_body, headers=headers)


def _create_user_and_login_live(client: httpx.Client, prefix: str, role: str = "funcional") -> None:
    pwd = "ValidPassword123!"
    username = _unique_username(prefix)
    make_user(username, role=role, password_hash=hash_password(pwd))
    _login_live(client, username, pwd)


def _create_session_live(client: httpx.Client) -> str:
    response = _post_csrf_live(client, "/api/sessions", {"agent_id": "default_chat"})
    assert response.status_code == 201
    session_id: str = response.json()["id"]
    return session_id


def _iter_sse_frames(lines: Iterator[str]) -> Iterator[dict[str, str]]:
    """Parsea un iterador de líneas SSE de forma PEREZOSA (equivalente incremental de
    `_parse_sse` de `test_streaming.py`, que solo puede operar sobre el texto crudo ya
    completo): entrega cada frame apenas se completa (línea en blanco), sin esperar a
    que el stream entero termine -- necesario para leer solo los primeros eventos por
    el cable y cortar la conexión antes de que llegue el resto.
    """
    current: dict[str, str] = {}
    for line in lines:
        if line == "":
            if current:
                yield current
                current = {}
            continue
        if line.startswith(":"):
            continue
        if line.startswith("id:"):
            current["id"] = line[len("id:") :].strip()
        elif line.startswith("event:"):
            current["event"] = line[len("event:") :].strip()
        elif line.startswith("data:"):
            current["data"] = line[len("data:") :].strip()
    if current:
        yield current


# --- Tarea 9.4: corte físico de conexión + reconexión ---------------------------------


def test_physical_disconnect_then_reconnect_replays_without_duplicates_and_single_invocation(
    pausable_generator: _PausableStreamingDoubleGenerator,
    registries: Registries,
    turn_registry: TurnStreamRegistry,
    live_server_factory: Callable[[FastAPI], _LiveServer],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Corte FÍSICO de la conexión (socket TCP real, no `TestClient`) a mitad de un
    turno pausado, seguido de reconexión con `Last-Event-ID` mientras el turno sigue
    vivo: retoma exactamente en el id siguiente, sin duplicar fragmentos ni dejar
    huecos (la concatenación reconstruye el texto completo), y el
    `StreamingResponseGenerator` inyectado -- el equivalente de este contrato al
    `LLMPort` -- se invoca UNA sola vez en total.
    """
    monkeypatch.setenv("RESULTARAI_SSE_HEARTBEAT_INTERVAL_SECONDS", "0.05")
    pausable_generator.chunks = ["Hola", ", mundo", "!"]
    pausable_generator.pause_before_index = 1  # pausa justo antes de ", mundo"

    app = _build_live_app(pausable_generator, registries, turn_registry)
    server = live_server_factory(app)

    with httpx.Client(base_url=server.base_url, timeout=15.0) as client:
        _create_user_and_login_live(client, "sse-uvicorn-reconnect")
        session_id = _create_session_live(client)

        csrf_token = client.cookies.get("resultarai_csrf")
        headers = {"X-CSRF-Token": csrf_token} if csrf_token else {}

        first_connection_events: list[dict[str, str]] = []
        with client.stream(
            "POST",
            f"/api/sessions/{session_id}/messages/stream",
            json={"text": "hola"},
            headers=headers,
        ) as response:
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("text/event-stream")
            turn_id = response.headers["X-Turn-Id"]
            user_message_id = response.headers["X-User-Message-Id"]
            assert turn_id.startswith("turn_")

            for frame in _iter_sse_frames(response.iter_lines()):
                first_connection_events.append(frame)
                break  # corte físico: el "cliente" solo confirma el primer evento

        # Al salir del `with`, httpx cerró la conexión sin consumir el resto del body
        # -- no puede devolver al pool una conexión HTTP/1.1 con el body a medio leer
        # (verificado empíricamente): esto es un corte físico de socket real, no una
        # fachada de `TestClient` que nunca llegó a completar el body.

        assert first_connection_events == [
            {"id": "1", "event": "fragment", "data": json.dumps({"text": "Hola"})}
        ]
        assert pausable_generator.reached_pause.wait(timeout=10.0), "el doble nunca se pausó"

        # Verificación SERVER-SIDE (tarea 9.4): el productor sigue vivo -- el hilo
        # daemon que drena `_produce_turn_events` (`_iter_sse_bytes._drain`) es
        # independiente del socket que acaba de cortarse -- y el buffer retiene el
        # evento ya emitido, todavía sin cerrarse.
        buffer = turn_registry.get(turn_id)
        assert buffer is not None, "el buffer del turno debe seguir vivo tras el corte físico"
        assert not buffer.closed
        assert [e.id for e in buffer.events_after(0)] == [1]

        # Reconexión mientras el turno sigue vivo: la conexión de reconexión queda
        # abierta hasta el `done`, así que corre en un hilo aparte (patrón ya
        # establecido por `test_streaming.py`/`test_resume.py`, ahora sobre un socket
        # real en vez de `TestClient`).
        reconnect_result: dict[str, Any] = {}

        def _reconnect() -> None:
            with client.stream(
                "GET",
                f"/api/turns/{turn_id}/stream",
                headers={"Last-Event-ID": "1"},
            ) as reconnect_response:
                reconnect_result["status_code"] = reconnect_response.status_code
                reconnect_result["headers"] = reconnect_response.headers
                reconnect_result["events"] = list(_iter_sse_frames(reconnect_response.iter_lines()))

        reconnect_thread = threading.Thread(target=_reconnect)
        reconnect_thread.start()

        time.sleep(0.2)
        pausable_generator.resume.set()

        reconnect_thread.join(timeout=10.0)
        assert not reconnect_thread.is_alive()

        assert reconnect_result["status_code"] == 200
        assert reconnect_result["headers"]["content-type"].startswith("text/event-stream")
        assert reconnect_result["headers"]["x-turn-id"] == turn_id

        events = reconnect_result["events"]
        ids = [int(e["id"]) for e in events]
        assert ids == list(range(2, 2 + len(ids))), "debe continuar en 2, sin duplicar ni saltar"
        assert events[-1]["event"] == "done"

        reconnect_fragment_text = "".join(
            json.loads(e["data"])["text"] for e in events if e["event"] == "fragment"
        )
        assert reconnect_fragment_text == ", mundo!"

        first_fragment_text = json.loads(first_connection_events[0]["data"])["text"]
        assert first_fragment_text + reconnect_fragment_text == "Hola, mundo!"

        done_data = json.loads(events[-1]["data"])
        assert done_data["turn_id"] == turn_id
        assert done_data["stopped"] is False
        assert done_data["user_message_id"] == user_message_id

        with get_db_session() as db:
            assistant = db.get(Message, uuid.UUID(done_data["assistant_message_id"]))
            assert assistant is not None
            assert assistant.content == "Hola, mundo!"
            assert assistant.status == "complete"

    assert pausable_generator.calls == 1, (
        "el corte físico y la reconexión no deben reinvocar al generador "
        "(equivalente de este contrato al LLMPort)"
    )


def test_physical_disconnect_then_late_reconnect_after_server_side_close_replays_once(
    streaming_generator: _StreamingDoubleGenerator,
    registries: Registries,
    turn_registry: TurnStreamRegistry,
    live_server_factory: Callable[[FastAPI], _LiveServer],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Corte físico ANTES de que el turno termine, pero la reconexión llega recién
    DESPUÉS de que el turno ya cerró en el server ("consumir tarde"): el productor,
    independiente del socket cortado, completó igual la generación y la persistencia
    sin ningún cliente conectado -- la reconexión reproduce exactamente lo que falta y
    cierra de inmediato, sin reinvocar al generador.
    """
    monkeypatch.setenv("RESULTARAI_SSE_HEARTBEAT_INTERVAL_SECONDS", "0.05")
    streaming_generator.chunks = ["Hola", ", mundo", "!"]
    streaming_generator.delay_seconds = 0.05

    app = _build_live_app(streaming_generator, registries, turn_registry)
    server = live_server_factory(app)

    with httpx.Client(base_url=server.base_url, timeout=15.0) as client:
        _create_user_and_login_live(client, "sse-uvicorn-late-reconnect")
        session_id = _create_session_live(client)

        csrf_token = client.cookies.get("resultarai_csrf")
        headers = {"X-CSRF-Token": csrf_token} if csrf_token else {}

        first_connection_events: list[dict[str, str]] = []
        with client.stream(
            "POST",
            f"/api/sessions/{session_id}/messages/stream",
            json={"text": "hola"},
            headers=headers,
        ) as response:
            assert response.status_code == 200
            turn_id = response.headers["X-Turn-Id"]
            user_message_id = response.headers["X-User-Message-Id"]

            for frame in _iter_sse_frames(response.iter_lines()):
                first_connection_events.append(frame)
                break  # corte físico tras confirmar solo el primer fragmento

        assert first_connection_events == [
            {"id": "1", "event": "fragment", "data": json.dumps({"text": "Hola"})}
        ]

        # "Consumir tarde": se espera a que el turno YA HAYA CERRADO server-side --
        # el productor, independiente del socket ya cortado, sigue generando y
        # persistiendo sin ningún cliente conectado -- antes de reconectar.
        assert _wait_until(
            lambda: (buf := turn_registry.get(turn_id)) is not None and buf.closed,
            timeout=10.0,
        ), "el turno nunca cerró server-side tras el corte físico"

        reconnect_response = client.get(
            f"/api/turns/{turn_id}/stream", headers={"Last-Event-ID": "1"}
        )
        assert reconnect_response.status_code == 200
        assert reconnect_response.headers["content-type"].startswith("text/event-stream")
        assert reconnect_response.headers["X-Turn-Id"] == turn_id

        events = list(_iter_sse_frames(iter(reconnect_response.text.split("\n"))))
        ids = [int(e["id"]) for e in events]
        assert ids == list(range(2, 2 + len(ids)))
        assert events[-1]["event"] == "done"

        reconnect_fragment_text = "".join(
            json.loads(e["data"])["text"] for e in events if e["event"] == "fragment"
        )
        assert reconnect_fragment_text == ", mundo!"

        first_fragment_text = json.loads(first_connection_events[0]["data"])["text"]
        assert first_fragment_text + reconnect_fragment_text == "Hola, mundo!"

        done_data = json.loads(events[-1]["data"])
        assert done_data["turn_id"] == turn_id
        assert done_data["stopped"] is False
        assert done_data["user_message_id"] == user_message_id

        with get_db_session() as db:
            assistant = db.get(Message, uuid.UUID(done_data["assistant_message_id"]))
            assert assistant is not None
            assert assistant.content == "Hola, mundo!"
            assert assistant.status == "complete"

    assert streaming_generator.calls == 1, (
        "el corte físico y la reconexión tardía no deben reinvocar al generador"
    )
