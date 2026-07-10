# ruff: noqa: E402
"""Integration tests for POST /sessions/{id}/messages/stream (SSE) y su reconexión y
cancelación.

d13-chat-conversacion, tareas 1.4 (traducción del marcador de escalación), 1.5
(streaming SSE del turno), 1.6 (reconexión por `Last-Event-ID`) y 1.7 (cancelación).
Ningún test llama a un LLM real: `_StreamingDoubleGenerator`/
`_PausableStreamingDoubleGenerator` son los únicos generadores inyectados.
"""

from __future__ import annotations

import datetime
import json
import os
import threading
import time
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet

# Fijar una clave estable en el entorno antes de importar nada que inicialice TotpConfig
# (mismo patrón que tests/app/chat/test_turns.py).
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
from resultarai.app.api.chat_stream import (
    get_streaming_response_generator,
    get_turn_stream_registry,
)
from resultarai.app.identity import (
    SessionConfig,
    get_db,
    get_session_config,
    hash_password,
)
from resultarai.app.startup import bootstrap
from resultarai.app.use_cases.chat import TurnCompletion, TurnFragment
from resultarai.app.use_cases.chat.stream_registry import TurnStreamBuffer, TurnStreamRegistry
from resultarai.core.registries import Registries
from tests.app.identity.conftest import make_user

_CONFIG = SessionConfig(
    signing_key="test-chat-key-for-streaming",
    idle_timeout=datetime.timedelta(minutes=30),
    absolute_lifetime=datetime.timedelta(hours=8),
    cookie_secure=False,  # deshabilitado Secure para extraer la cookie en el test client
)


class _StreamingDoubleGenerator:
    """Doble de `StreamingResponseGenerator`: produce fragmentos fijos configurables.

    `delay_seconds`, si es mayor que cero, duerme antes de cada fragmento -- lo usa el
    test de heartbeat para forzar que el productor tarde más que el intervalo de
    heartbeat configurado.
    """

    def __init__(
        self,
        chunks: list[str],
        *,
        delay_seconds: float = 0.0,
        needs_pro: bool = False,
    ) -> None:
        self.chunks = chunks
        self.delay_seconds = delay_seconds
        self.needs_pro = needs_pro
        self.calls = 0

    def __call__(self, *, session: Any, history: Any) -> Iterator[TurnFragment | TurnCompletion]:
        self.calls += 1

        def _generate() -> Iterator[TurnFragment | TurnCompletion]:
            for chunk in self.chunks:
                if self.delay_seconds:
                    time.sleep(self.delay_seconds)
                yield TurnFragment(chunk)
            yield TurnCompletion(
                model_profile_id=session.model_profile,
                is_alternate_model=False,
                needs_pro=self.needs_pro,
            )

        return _generate()


@pytest.fixture
def streaming_generator() -> _StreamingDoubleGenerator:
    return _StreamingDoubleGenerator(["hola ", "mundo"])


class _PausableStreamingDoubleGenerator:
    """Doble de `StreamingResponseGenerator` con una pausa controlable a mitad del
    stream (tareas 1.6 y 1.7): permite simular "el turno sigue en curso" mientras un
    test corta la conexión original, reconecta, o cancela desde otro hilo.

    Antes de producir el fragmento en índice `pause_before_index`, señala
    `reached_pause` (para que el test sepa que la producción ya está bloqueada, sin
    tener que sondear) y se bloquea esperando `resume`, que el test setea cuando
    quiere dejarla continuar. `calls` cuenta invocaciones reales -- los tests de
    reconexión verifican que sigue en `1` después de reconectar (nunca se reinvoca al
    generador).
    """

    def __init__(self, chunks: list[str], *, pause_before_index: int) -> None:
        self.chunks = chunks
        self.pause_before_index = pause_before_index
        self.reached_pause = threading.Event()
        self.resume = threading.Event()
        self.calls = 0

    def __call__(self, *, session: Any, history: Any) -> Iterator[TurnFragment | TurnCompletion]:
        self.calls += 1

        def _generate() -> Iterator[TurnFragment | TurnCompletion]:
            for index, chunk in enumerate(self.chunks):
                if index == self.pause_before_index:
                    self.reached_pause.set()
                    self.resume.wait()
                yield TurnFragment(chunk)
            yield TurnCompletion(model_profile_id=session.model_profile, is_alternate_model=False)

        return _generate()


@pytest.fixture
def pausable_generator() -> _PausableStreamingDoubleGenerator:
    """Instancia vacía: cada test que la usa fija `chunks`/`pause_before_index` antes
    de disparar el turno (mismo patrón que `streaming_generator`, que también se
    reconfigura por test).
    """
    return _PausableStreamingDoubleGenerator([], pause_before_index=0)


class _SyncEchoResponseGenerator:
    """Doble mínimo de `ResponseGenerator` (síncrono, tarea 1.2/1.3) para que los tests
    de cancelación (tarea 1.7) puedan ejercer `POST /messages/{id}/regenerate` sobre el
    mensaje `stopped` resultante, sin depender de `tests/app/chat/test_turns.py`.
    """

    def __call__(self, *, session: Any, history: Any) -> str:
        return "respuesta regenerada"


@pytest.fixture
def sync_response_generator() -> _SyncEchoResponseGenerator:
    return _SyncEchoResponseGenerator()


@pytest.fixture
def registries() -> Registries:
    """Registries reales de `manifests/`, en una fixture propia (en vez de resolverlos
    dentro de `client`) para que un test pueda mutar el Agent Manifest en memoria
    (p. ej. `escalation.enabled`) *antes* de que el override del endpoint lo lea --
    `client` captura esta misma instancia por referencia, no una copia.
    """
    return bootstrap(Path("manifests"))


@pytest.fixture
def turn_registry() -> TurnStreamRegistry:
    """Registro de buffers propio del test (tareas 1.6/1.7): se inyecta en la app (en
    vez de dejar la instancia interna de `create_app()`) para que el test pueda observar
    el estado real del turno en curso -- localizar el buffer por `user_message_id`,
    esperar `cancel_requested` de forma determinista -- sin depender de sleeps ciegos.
    """
    return TurnStreamRegistry()


def _build_test_client(
    streaming_response_generator: Any,
    sync_response_generator_double: Any,
    registries_instance: Registries,
    turn_registry_instance: TurnStreamRegistry,
) -> Iterator[TestClient]:
    """Construye un `TestClient` con los overrides comunes de DB/config/Registries, más
    ambos generadores de respuesta (streaming y síncrono) y el registro de buffers de
    turnos. Compartido por `client` (tareas 1.4/1.5) y `pausable_client` (tareas
    1.6/1.7, que necesita un doble con pausa controlable en vez del de fragmentos
    fijos).
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
    app.dependency_overrides[get_response_generator] = lambda: sync_response_generator_double
    app.dependency_overrides[get_turn_stream_registry] = lambda: turn_registry_instance

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def client(
    streaming_generator: _StreamingDoubleGenerator,
    sync_response_generator: _SyncEchoResponseGenerator,
    registries: Registries,
    turn_registry: TurnStreamRegistry,
) -> Iterator[TestClient]:
    """TestClient con overrides de DB, config de sesión, Registries reales y el doble
    de generación de respuesta en streaming (`get_streaming_response_generator`).
    """
    yield from _build_test_client(
        streaming_generator, sync_response_generator, registries, turn_registry
    )


@pytest.fixture
def pausable_client(
    pausable_generator: _PausableStreamingDoubleGenerator,
    sync_response_generator: _SyncEchoResponseGenerator,
    registries: Registries,
    turn_registry: TurnStreamRegistry,
) -> Iterator[TestClient]:
    """TestClient equivalente a `client`, pero con `_PausableStreamingDoubleGenerator`
    inyectado (tareas 1.6/1.7: necesitan pausar la generación a mitad de turno de forma
    controlada desde el test).
    """
    yield from _build_test_client(
        pausable_generator, sync_response_generator, registries, turn_registry
    )


def _unique_username(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12]}"


def login(client: TestClient, username: str, pwd: str) -> None:
    r = client.post("/api/auth/login", json={"username": username, "password": pwd})
    assert r.status_code == 200
    assert r.json() == {"status": "success"}


def post_csrf(client: TestClient, url: str, json: dict[str, Any] | None = None) -> Any:
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


def _parse_sse(raw_text: str) -> tuple[list[dict[str, str]], int]:
    """Parsea el texto crudo SSE en `(eventos, cantidad_de_heartbeats)`.

    Cada evento es un dict con las claves `id`/`event`/`data` (strings, tal como
    llegaron en el frame). Los comentarios `: heartbeat` no producen un evento; solo
    incrementan el contador.
    """
    events: list[dict[str, str]] = []
    heartbeats = 0
    current: dict[str, str] = {}
    for line in raw_text.split("\n"):
        if line == "":
            if current:
                events.append(current)
                current = {}
            continue
        if line.startswith(":"):
            heartbeats += 1
            continue
        if line.startswith("id:"):
            current["id"] = line[len("id:") :].strip()
        elif line.startswith("event:"):
            current["event"] = line[len("event:") :].strip()
        elif line.startswith("data:"):
            current["data"] = line[len("data:") :].strip()
    if current:
        events.append(current)
    return events, heartbeats


def _stream_turn(client: TestClient, session_id: str, text: str) -> str:
    """Envía un turno al endpoint de streaming y devuelve el texto crudo del stream."""
    csrf_token = client.cookies.get("resultarai_csrf")
    headers = {"X-CSRF-Token": csrf_token} if csrf_token else {}
    with client.stream(
        "POST",
        f"/api/sessions/{session_id}/messages/stream",
        json={"text": text},
        headers=headers,
    ) as response:
        assert response.status_code == 200
        assert response.headers["content-type"].startswith("text/event-stream")
        raw = "".join(response.iter_text())
    return raw


# --- Tarea 1.4: el marcador de escalación nunca viaja crudo ------------------------


def test_escalation_marker_split_across_fragments_never_leaks(
    client: TestClient, streaming_generator: _StreamingDoubleGenerator
) -> None:
    """El marcador partido entre dos fragmentos consecutivos nunca llega al cliente;
    se traduce a exactamente un evento `escalation` con `reason` y `target_profile`.
    """
    _create_user_and_login(client, "stream-escalation")
    session_id = _create_session(client)

    streaming_generator.chunks = ["Esta consulta requiere más capacidad. <<<NEEDS_", "PRO>>>"]

    raw = _stream_turn(client, session_id, "necesito ayuda avanzada")

    assert "<<<NEEDS_PRO>>>" not in raw
    assert "NEEDS_PRO" not in raw

    events, _ = _parse_sse(raw)
    kinds = [e["event"] for e in events]

    for event in events:
        if event["event"] == "fragment":
            assert "<<<NEEDS_PRO>>>" not in json.loads(event["data"])["text"]

    assert kinds.count("escalation") == 1
    assert kinds[-1] == "done"
    escalation_index = kinds.index("escalation")
    assert all(k == "fragment" for k in kinds[:escalation_index])

    escalation_data = json.loads(events[escalation_index]["data"])
    assert escalation_data["reason"]
    assert escalation_data["target_profile"] == "openai_gpt_4o_pro"

    done_data = json.loads(events[-1]["data"])
    assert done_data["escalation"] == escalation_data

    with get_db_session() as db:
        assistant = db.get(Message, uuid.UUID(done_data["assistant_message_id"]))
        assert assistant is not None
        assert "<<<NEEDS_PRO>>>" not in assistant.content
        assert assistant.turn_metadata is not None
        assert assistant.turn_metadata["escalation"] == escalation_data


def test_escalation_disabled_suppresses_both_marker_and_event(
    client: TestClient,
    registries: Registries,
    streaming_generator: _StreamingDoubleGenerator,
) -> None:
    """Con `escalation.enabled: false` en el Agent Manifest: ni el evento de dominio ni
    el marcador crudo aparecen -- ambos se suprimen (defensa incondicional del texto
    entregado, independiente de si la escalación está habilitada).
    """
    agent = registries.agents.get_invocable("default_chat")
    assert agent is not None
    agent.escalation.enabled = False

    _create_user_and_login(client, "stream-no-escalation")
    session_id = _create_session(client)

    streaming_generator.chunks = ["respuesta sin escalar <<<NEEDS_PRO>>> texto final"]

    raw = _stream_turn(client, session_id, "consulta cualquiera")

    assert "<<<NEEDS_PRO>>>" not in raw

    events, _ = _parse_sse(raw)
    kinds = [e["event"] for e in events]
    assert "escalation" not in kinds
    assert kinds.count("done") == 1

    done_data = json.loads(events[-1]["data"])
    assert done_data["escalation"] is None


# --- Tarea 1.5: streaming SSE con orden, heartbeat y cierre ------------------------


def test_stream_turn_ordering_heartbeat_and_close_metadata(
    client: TestClient,
    streaming_generator: _StreamingDoubleGenerator,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fragmentos en orden, al menos un heartbeat, e `id` incremental terminando en
    `done` con los metadatos completos del turno.

    Usa el rol `tecnico` (tarea 4.1: la capa `telemetry` del `done` solo viaja para
    Técnico/Admin, ver `test_telemetry.py` para la cobertura de la ausencia total en
    Funcional) para poder seguir aserting sobre `model_profile_id`/`cache_hit_tokens`/
    `cost_usd`, ahora anidados bajo `telemetry`.
    """
    monkeypatch.setenv("RESULTARAI_SSE_HEARTBEAT_INTERVAL_SECONDS", "0.05")
    streaming_generator.chunks = ["Hola", ", ", "¿cómo estás?"]
    streaming_generator.delay_seconds = 0.12

    _create_user_and_login(client, "stream-full", role="tecnico")
    session_id = _create_session(client)

    raw = _stream_turn(client, session_id, "hola, turno completo")
    events, heartbeats = _parse_sse(raw)

    assert heartbeats >= 1, "se esperaba al menos un comentario `: heartbeat`"

    kinds = [e["event"] for e in events]
    assert kinds.count("done") == 1
    assert kinds[-1] == "done"
    assert all(k == "fragment" for k in kinds[:-1])  # sin escalación en este doble

    ids = [int(e["id"]) for e in events]
    assert ids == list(range(1, len(ids) + 1))

    fragments_text = "".join(
        json.loads(e["data"])["text"] for e in events if e["event"] == "fragment"
    )
    assert fragments_text == "Hola, ¿cómo estás?"

    done_data = json.loads(events[-1]["data"])
    assert done_data["turn_id"].startswith("turn_")
    assert uuid.UUID(done_data["user_message_id"])
    assert uuid.UUID(done_data["assistant_message_id"])
    assert done_data["is_alternate_model"] is False
    assert done_data["compacted"] is False
    assert done_data["escalation"] is None
    assert done_data["reprocessed_count"] == 0

    # Tarea 4.1: rol tecnico -> capa `telemetry` presente, con `trace_id` AUSENTE
    # (solo Admin lo ve).
    telemetry = done_data["telemetry"]
    assert telemetry["model_profile_id"]
    assert "cache_hit_tokens" in telemetry
    assert "cost_usd" in telemetry
    assert isinstance(telemetry["latency_ms"], int)
    assert telemetry["latency_ms"] >= 0
    assert "trace_id" not in telemetry

    with get_db_session() as db:
        assistant = db.get(Message, uuid.UUID(done_data["assistant_message_id"]))
        assert assistant is not None
        assert assistant.content == "Hola, ¿cómo estás?"
        assert assistant.status == "complete"
        assert assistant.turn_metadata is not None
        assert assistant.turn_metadata["model_profile_id"] == telemetry["model_profile_id"]

        user_message = db.get(Message, uuid.UUID(done_data["user_message_id"]))
        assert user_message is not None
        assert user_message.content == "hola, turno completo"


def test_stream_to_foreign_session_returns_404(client: TestClient) -> None:
    """Enviar un turno en streaming a una sesión ajena responde 404 sin crear mensajes."""
    _create_user_and_login(client, "stream-owner")
    owner_session_id = _create_session(client)

    _create_user_and_login(client, "stream-intruder")
    csrf_token = client.cookies.get("resultarai_csrf")
    headers = {"X-CSRF-Token": csrf_token} if csrf_token else {}
    response = client.post(
        f"/api/sessions/{owner_session_id}/messages/stream",
        json={"text": "intento ajeno"},
        headers=headers,
    )
    assert response.status_code == 404

    with get_db_session() as db:
        messages = (
            db.execute(select(Message).where(Message.session_id == owner_session_id))
            .scalars()
            .all()
        )
        assert len(messages) == 0


# --- Tareas 1.6/1.7: helpers de turnos en curso -------------------------------------
#
# Nota sobre el "corte de conexión": el `TestClient` de Starlette NO hace streaming
# real -- ejecuta la app ASGI hasta completar y bufferiza todo el body antes de devolver
# la respuesta (`testclient.py`, `TestClientTransport.handle_request`), así que no es
# posible cortar físicamente la conexión a mitad de un stream desde el test. El corte se
# simula a nivel del CONTRATO, que es lo que la tarea verifica: el turno queda pausado en
# curso (doble pausable), el "cliente cortado" solo confirmó hasta el evento `N`, y la
# reconexión llega con `Last-Event-ID: N` mientras el turno sigue vivo -- exactamente el
# estado en que queda un `EventSource` real tras un corte. La petición original corre en
# un hilo aparte (quedaría bloqueada hasta el cierre del turno) y sus bytes completos se
# validan al final como el "primer cliente".


def _start_stream_in_thread(
    client: TestClient, session_id: str, text: str
) -> tuple[threading.Thread, dict[str, Any]]:
    """Dispara `POST /sessions/{id}/messages/stream` en un hilo y devuelve
    `(hilo, resultado)`; `resultado["response"]` aparece cuando el turno cierra.
    """
    csrf_token = client.cookies.get("resultarai_csrf")
    headers = {"X-CSRF-Token": csrf_token} if csrf_token else {}
    result: dict[str, Any] = {}

    def _post() -> None:
        result["response"] = client.post(
            f"/api/sessions/{session_id}/messages/stream",
            json={"text": text},
            headers=headers,
        )

    thread = threading.Thread(target=_post)
    thread.start()
    return thread, result


def _find_live_buffer(turn_registry: TurnStreamRegistry, session_id: str) -> TurnStreamBuffer:
    """Localiza el buffer del turno en curso de `session_id` vía su mensaje de usuario
    (ya persistido y commiteado por `start_turn_stream` antes de invocar al generador).
    """
    with get_db_session() as db:
        user_message = (
            db.execute(
                select(Message).where(Message.session_id == session_id, Message.role == "user")
            )
            .scalars()
            .one()
        )
        user_message_id = user_message.id
    buffer = turn_registry.get_by_user_message_id(user_message_id)
    assert buffer is not None, "el turno en curso debe estar registrado por user_message_id"
    return buffer


def _wait_until(predicate: Any, timeout: float = 5.0) -> bool:
    """Espera (polling corto) hasta que `predicate()` sea verdadero o venza `timeout`."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return True
        time.sleep(0.01)
    return bool(predicate())


# --- Tarea 1.6: reconexión por Last-Event-ID -----------------------------------------


def test_reconnect_replays_without_duplicates_and_without_reinvoking_generator(
    pausable_client: TestClient,
    pausable_generator: _PausableStreamingDoubleGenerator,
    turn_registry: TurnStreamRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reconectar con `Last-Event-ID` a un turno en curso (cliente original "cortado"
    tras confirmar solo el evento 1) retoma exactamente en el id siguiente, sin duplicar
    fragmentos ni dejar huecos (la concatenación reconstruye el texto completo), y el
    `StreamingResponseGenerator` inyectado se invoca UNA sola vez en total.
    """
    monkeypatch.setenv("RESULTARAI_SSE_HEARTBEAT_INTERVAL_SECONDS", "0.05")
    pausable_generator.chunks = ["Hola", ", mundo", "!"]
    pausable_generator.pause_before_index = 1  # pausa justo antes de ", mundo"

    _create_user_and_login(pausable_client, "reconnect-owner")
    session_id = _create_session(pausable_client)

    post_thread, post_result = _start_stream_in_thread(pausable_client, session_id, "hola")

    assert pausable_generator.reached_pause.wait(timeout=10.0), "el doble nunca se pausó"

    buffer = _find_live_buffer(turn_registry, session_id)
    turn_id = buffer.turn_id
    assert turn_id.startswith("turn_")

    # El "cliente cortado" alcanzó a confirmar el evento 1 (el primer fragmento ya está
    # bufferizado; el turno sigue en curso, pausado antes del segundo).
    assert _wait_until(lambda: len(buffer.events_after(0)) >= 1)
    assert not buffer.closed
    first_event = buffer.events_after(0)[0]
    assert first_event.id == 1
    assert first_event.event == "fragment"

    # Reconexión mientras el turno sigue vivo: corre en otro hilo (también queda
    # bloqueada hasta el `done`, TestClient bufferiza) y arranca ANTES de liberar la
    # pausa, para ejercer el camino "seguir en vivo", no solo el replay.
    reconnect_result: dict[str, Any] = {}

    def _reconnect() -> None:
        reconnect_result["response"] = pausable_client.get(
            f"/api/turns/{turn_id}/stream", headers={"Last-Event-ID": "1"}
        )

    reconnect_thread = threading.Thread(target=_reconnect)
    reconnect_thread.start()

    time.sleep(0.2)
    pausable_generator.resume.set()

    reconnect_thread.join(timeout=10.0)
    post_thread.join(timeout=10.0)
    assert not reconnect_thread.is_alive()
    assert not post_thread.is_alive()

    # Reconexión: retoma exactamente en id 2, contigua y sin duplicados, hasta `done`.
    reconnect_response = reconnect_result["response"]
    assert reconnect_response.status_code == 200
    assert reconnect_response.headers["content-type"].startswith("text/event-stream")
    assert reconnect_response.headers["X-Turn-Id"] == turn_id
    events, _ = _parse_sse(reconnect_response.text)
    ids = [int(e["id"]) for e in events]
    assert ids == list(range(2, 2 + len(ids))), "debe continuar en 2, sin duplicar ni saltar"
    assert events[-1]["event"] == "done"

    reconnect_fragment_text = "".join(
        json.loads(e["data"])["text"] for e in events if e["event"] == "fragment"
    )
    assert reconnect_fragment_text == ", mundo!"

    done_data = json.loads(events[-1]["data"])
    assert done_data["stopped"] is False
    assert done_data["turn_id"] == turn_id

    # Cliente original: recibió el turno completo desde el id 1 (headers de
    # descubrimiento incluidos); la unión "lo confirmado antes del corte" + "lo
    # reproducido en la reconexión" reconstruye el texto exacto sin huecos.
    original_response = post_result["response"]
    assert original_response.status_code == 200
    assert original_response.headers["X-Turn-Id"] == turn_id
    assert original_response.headers["X-User-Message-Id"] == str(buffer.user_message_id)
    original_events, _ = _parse_sse(original_response.text)
    assert [int(e["id"]) for e in original_events] == list(range(1, len(original_events) + 1))
    first_fragment_text = json.loads(original_events[0]["data"])["text"]
    assert first_fragment_text + reconnect_fragment_text == "Hola, mundo!"

    with get_db_session() as db:
        assistant = db.get(Message, uuid.UUID(done_data["assistant_message_id"]))
        assert assistant is not None
        assert assistant.content == "Hola, mundo!"
        assert assistant.status == "complete"

    assert pausable_generator.calls == 1, "la reconexión no debe reinvocar al generador"


def test_reconnect_after_turn_closed_replays_remaining_and_closes(
    client: TestClient, streaming_generator: _StreamingDoubleGenerator
) -> None:
    """Reconectar a un turno que ya terminó reproduce solo lo que falte (según
    `Last-Event-ID`, aceptado también como query param) y cierra de inmediato.
    """
    streaming_generator.chunks = ["Hola", ", mundo"]

    _create_user_and_login(client, "reconnect-closed")
    session_id = _create_session(client)

    response = post_csrf(
        client, f"/api/sessions/{session_id}/messages/stream", json={"text": "hola"}
    )
    assert response.status_code == 200
    turn_id = response.headers["X-Turn-Id"]
    original_events, _ = _parse_sse(response.text)
    last_id_before_done = int(original_events[-2]["id"])  # último fragmento antes de `done`

    # Variante header.
    response = client.get(
        f"/api/turns/{turn_id}/stream",
        headers={"Last-Event-ID": str(last_id_before_done)},
    )
    assert response.status_code == 200
    events, _ = _parse_sse(response.text)
    assert [e["event"] for e in events] == ["done"]
    assert json.loads(events[0]["data"])["turn_id"] == turn_id

    # Variante query param (mismo replay, para clientes sin `EventSource` nativo).
    response = client.get(f"/api/turns/{turn_id}/stream?last_event_id={last_id_before_done}")
    assert response.status_code == 200
    events_qp, _ = _parse_sse(response.text)
    assert [e["event"] for e in events_qp] == ["done"]

    assert streaming_generator.calls == 1


def test_reconnect_unknown_or_foreign_turn_returns_404(
    client: TestClient, streaming_generator: _StreamingDoubleGenerator
) -> None:
    """Reconectar a un `turn_id` inexistente, o a uno de otro usuario, responde 404."""
    _create_user_and_login(client, "reconnect-404-a")
    response = client.get("/api/turns/turn_does-not-exist/stream")
    assert response.status_code == 404

    session_id = _create_session(client)
    response = post_csrf(
        client, f"/api/sessions/{session_id}/messages/stream", json={"text": "hola"}
    )
    assert response.status_code == 200
    owner_turn_id = response.headers["X-Turn-Id"]

    _create_user_and_login(client, "reconnect-404-b")
    response = client.get(f"/api/turns/{owner_turn_id}/stream")
    assert response.status_code == 404


def test_reconnect_invalid_last_event_id_returns_400(
    client: TestClient, streaming_generator: _StreamingDoubleGenerator
) -> None:
    """Un `Last-Event-ID` no numérico responde 400 en vez de reproducir todo el turno."""
    _create_user_and_login(client, "reconnect-badid")
    session_id = _create_session(client)
    response = post_csrf(
        client, f"/api/sessions/{session_id}/messages/stream", json={"text": "hola"}
    )
    assert response.status_code == 200
    turn_id = response.headers["X-Turn-Id"]

    response = client.get(
        f"/api/turns/{turn_id}/stream", headers={"Last-Event-ID": "no-es-un-numero"}
    )
    assert response.status_code == 400


# --- Tarea 1.7: cancelación de un turno en curso -------------------------------------


def test_cancel_by_message_id_persists_stopped_message_and_allows_regenerate(
    pausable_client: TestClient,
    pausable_generator: _PausableStreamingDoubleGenerator,
    turn_registry: TurnStreamRegistry,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cancelar un turno pausado a mitad de generación (vía `POST /messages/{id}/cancel`
    con el id del mensaje de USUARIO): el stream cierra con `done`/`stopped: true` sin
    error de protocolo, la DB persiste el mensaje de agente con `status="stopped"` y el
    texto parcial, y ese mensaje queda disponible para regenerar (crea una versión
    hermana).
    """
    monkeypatch.setenv("RESULTARAI_SSE_HEARTBEAT_INTERVAL_SECONDS", "0.05")
    pausable_generator.chunks = [
        "Respuesta parcial antes de cancelar ",
        "resto que nunca debe llegar",
    ]
    pausable_generator.pause_before_index = 1

    _create_user_and_login(pausable_client, "cancel-owner")
    session_id = _create_session(pausable_client)

    post_thread, post_result = _start_stream_in_thread(
        pausable_client, session_id, "turno que se cancela"
    )

    assert pausable_generator.reached_pause.wait(timeout=10.0), "el doble nunca se pausó"

    buffer = _find_live_buffer(turn_registry, session_id)
    user_message_id = str(buffer.user_message_id)

    cancel_result: dict[str, Any] = {}

    def _call_cancel() -> None:
        cancel_result["response"] = post_csrf(
            pausable_client, f"/api/messages/{user_message_id}/cancel"
        )

    cancel_thread = threading.Thread(target=_call_cancel)
    cancel_thread.start()

    # Determinista, sin sleeps ciegos: recién cuando el endpoint de cancel ya señaló la
    # cancelación se libera la pausa del doble, para que la producción la note en su
    # próximo punto de control (entre fragmento y fragmento) y cierre el turno.
    assert _wait_until(lambda: buffer.cancel_requested), "cancel nunca señaló el buffer"
    pausable_generator.resume.set()

    cancel_thread.join(timeout=10.0)
    post_thread.join(timeout=10.0)
    assert not cancel_thread.is_alive()
    assert not post_thread.is_alive()

    cancel_response = cancel_result["response"]
    assert cancel_response.status_code == 200
    cancel_data = cancel_response.json()
    assert cancel_data["status"] == "stopped"
    assert cancel_data["turn_id"] == buffer.turn_id
    assert cancel_data["user_message_id"] == user_message_id
    assistant_message_id = cancel_data["assistant_message_id"]
    assert assistant_message_id

    # El stream original cerró sin error de protocolo: 200, eventos bien formados y un
    # único `done` final con `stopped: true`; el fragmento posterior a la cancelación
    # nunca viajó.
    original_response = post_result["response"]
    assert original_response.status_code == 200
    assert original_response.headers["X-User-Message-Id"] == user_message_id
    events, _ = _parse_sse(original_response.text)
    kinds = [e["event"] for e in events]
    assert kinds.count("done") == 1
    assert kinds[-1] == "done"
    done_data = json.loads(events[-1]["data"])
    assert done_data["stopped"] is True
    assert done_data["assistant_message_id"] == assistant_message_id

    fragment_text = "".join(
        json.loads(e["data"])["text"] for e in events if e["event"] == "fragment"
    )
    assert fragment_text == "Respuesta parcial antes de cancelar "
    assert "resto que nunca debe llegar" not in original_response.text
    assert pausable_generator.calls == 1

    with get_db_session() as db:
        assistant = db.get(Message, uuid.UUID(assistant_message_id))
        assert assistant is not None
        assert assistant.status == "stopped"
        assert assistant.content == "Respuesta parcial antes de cancelar "

    # Regenerable: crea una versión hermana bajo el mismo mensaje de usuario.
    regen_response = post_csrf(pausable_client, f"/api/messages/{assistant_message_id}/regenerate")
    assert regen_response.status_code == 201
    regen_data = regen_response.json()
    assert regen_data["version"] == 2
    assert regen_data["version_count"] == 2
    assert regen_data["message"]["parent_id"] == user_message_id


def test_cancel_unknown_or_foreign_turn_returns_404(
    client: TestClient, streaming_generator: _StreamingDoubleGenerator
) -> None:
    """Cancelar un `turn_id`/mensaje inexistente, o de otro usuario, responde 404."""
    _create_user_and_login(client, "cancel-404-a")
    response = post_csrf(client, "/api/turns/turn_does-not-exist/cancel")
    assert response.status_code == 404
    response = post_csrf(client, f"/api/messages/{uuid.uuid4()}/cancel")
    assert response.status_code == 404

    session_id = _create_session(client)
    response = post_csrf(
        client, f"/api/sessions/{session_id}/messages/stream", json={"text": "hola"}
    )
    assert response.status_code == 200
    owner_turn_id = response.headers["X-Turn-Id"]
    owner_user_message_id = response.headers["X-User-Message-Id"]

    _create_user_and_login(client, "cancel-404-b")
    response = post_csrf(client, f"/api/turns/{owner_turn_id}/cancel")
    assert response.status_code == 404
    response = post_csrf(client, f"/api/messages/{owner_user_message_id}/cancel")
    assert response.status_code == 404


def test_cancel_already_closed_turn_returns_409(
    client: TestClient, streaming_generator: _StreamingDoubleGenerator
) -> None:
    """Cancelar un turno que ya terminó normalmente responde 409 (comportamiento
    documentado en el docstring de la API: cancelar no es idempotente, solo tiene
    sentido sobre un turno todavía en curso). Ambas rutas responden igual.
    """
    _create_user_and_login(client, "cancel-closed")
    session_id = _create_session(client)
    response = post_csrf(
        client, f"/api/sessions/{session_id}/messages/stream", json={"text": "hola"}
    )
    assert response.status_code == 200
    turn_id = response.headers["X-Turn-Id"]
    user_message_id = response.headers["X-User-Message-Id"]

    response = post_csrf(client, f"/api/turns/{turn_id}/cancel")
    assert response.status_code == 409
    response = post_csrf(client, f"/api/messages/{user_message_id}/cancel")
    assert response.status_code == 409
