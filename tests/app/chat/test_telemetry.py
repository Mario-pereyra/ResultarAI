# ruff: noqa: E402
"""Tests de la capa de telemetría por turno filtrada por rol.

d13-chat-conversacion, tarea 4.1: unit del filtrado puro (`telemetry.py`) + tests de
contrato sobre los TRES puntos de salida del turno -- el evento `done` del SSE
(`streaming.py`), la respuesta de `POST /sessions/{id}/messages` y
`/messages/{id}/regenerate` (`turns.py`), y `GET /sessions/{id}` (`history.py`) --
verificando que la clave `telemetry` está TOTALMENTE AUSENTE (no `null`, no `{}`) del
JSON entregado a una sesión Funcional, y presente (con o sin `trace_id`) para
Técnico/Admin -- decisión 7 de `design.md` y riesgo 4: el backend no confía en el
frontend, es la AUSENCIA de la clave lo que decide.
"""

from __future__ import annotations

import datetime
import json
import os
import uuid
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from cryptography.fernet import Fernet

# Fijar una clave estable en el entorno antes de importar nada que inicialice TotpConfig
# (mismo patrón que tests/app/chat/test_streaming.py).
_STABLE_KEY = Fernet.generate_key().decode("utf-8")
os.environ.setdefault("IDENTITY_TOTP_ENCRYPTION_KEY", _STABLE_KEY)

import pyotp
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as DbSession

from resultarai.adapters.persistence_postgres.connection import SessionLocal, get_db_session
from resultarai.adapters.persistence_postgres.models import TotpSecret
from resultarai.app.api import create_app
from resultarai.app.api.chat import get_registries, get_response_generator
from resultarai.app.api.chat_stream import (
    get_streaming_response_generator,
    get_turn_stream_registry,
)
from resultarai.app.identity import (
    SessionConfig,
    TotpConfig,
    get_db,
    get_session_config,
    hash_password,
)
from resultarai.app.startup import bootstrap
from resultarai.app.use_cases.chat import TurnCompletion, TurnFragment
from resultarai.app.use_cases.chat.stream_registry import TurnStreamRegistry
from resultarai.app.use_cases.chat.telemetry import (
    RawTurnMetadata,
    build_raw_turn_metadata,
    layer_turn_metadata,
)
from tests.app.identity.conftest import make_user

_CONFIG = SessionConfig(
    signing_key="test-chat-key-for-telemetry",
    idle_timeout=datetime.timedelta(minutes=30),
    absolute_lifetime=datetime.timedelta(hours=8),
    cookie_secure=False,  # deshabilitado Secure para extraer la cookie en el test client
)


class _StreamingDoubleGenerator:
    """Doble mínimo de `StreamingResponseGenerator`: un fragmento fijo + cierre con
    datos de telemetría no triviales (para distinguirlos de los defaults en los
    asserts).
    """

    def __init__(self, chunks: list[str]) -> None:
        self.chunks = chunks

    def __call__(self, *, session: Any, history: Any) -> Iterator[TurnFragment | TurnCompletion]:
        def _generate() -> Iterator[TurnFragment | TurnCompletion]:
            for chunk in self.chunks:
                yield TurnFragment(chunk)
            yield TurnCompletion(
                model_profile_id=session.model_profile,
                is_alternate_model=False,
                cache_hit_tokens=12,
                cache_miss_tokens=3,
                cost_usd=0.0042,
            )

        return _generate()


@pytest.fixture
def streaming_generator() -> _StreamingDoubleGenerator:
    return _StreamingDoubleGenerator(["hola"])


class _SyncResponseGenerator:
    """Doble mínimo de `ResponseGenerator` (síncrono): texto fijo."""

    def __call__(self, *, session: Any, history: Any) -> str:
        return "respuesta síncrona"


@pytest.fixture
def sync_response_generator() -> _SyncResponseGenerator:
    return _SyncResponseGenerator()


@pytest.fixture
def client(
    streaming_generator: _StreamingDoubleGenerator,
    sync_response_generator: _SyncResponseGenerator,
) -> Iterator[TestClient]:
    """TestClient con ambos generadores (síncrono y streaming) inyectados, para
    ejercer los tres puntos de salida del turno desde un único cliente por test.
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
    app.dependency_overrides[get_streaming_response_generator] = lambda: streaming_generator
    app.dependency_overrides[get_response_generator] = lambda: sync_response_generator
    app.dependency_overrides[get_turn_stream_registry] = lambda: TurnStreamRegistry()

    with TestClient(app) as test_client:
        yield test_client


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


def _create_user_and_login(client: TestClient, prefix: str, role: str) -> None:
    """Crea un usuario del rol dado y completa su login.

    El rol Admin exige TOTP obligatorio (`get_wizard_status`: `role == "admin"`
    fuerza `totp_required`), así que sin un `TotpSecret` pre-enrolado el
    `wizard_guard` global bloquearía CUALQUIER ruta con 403 -- se enrola uno de
    prueba y se completa el login en dos pasos (mismo patrón que
    `tests/app/identity/test_endpoints.py::make_completed_admin`/`login_admin`).
    Funcional/Técnico no tienen ese paso pendiente: login de un solo paso.
    """
    pwd = "ValidPassword123!"
    username = _unique_username(prefix)

    if role == "admin":
        user_id = make_user(username, role=role, password_hash=hash_password(pwd))
        secret_base32 = pyotp.random_base32()
        totp_config = TotpConfig.from_env()
        fernet = Fernet(totp_config.encryption_key)
        encrypted_secret = fernet.encrypt(secret_base32.encode("utf-8"))
        with get_db_session() as db:
            db.add(TotpSecret(user_id=user_id, encrypted_secret=encrypted_secret))
            db.commit()

        r_login = client.post("/api/auth/login", json={"username": username, "password": pwd})
        assert r_login.status_code == 200
        pending_token = r_login.json()["pending_token"]
        code = pyotp.TOTP(secret_base32).now()
        r_verify = client.post(
            "/api/auth/totp/verify", json={"pending_token": pending_token, "code": code}
        )
        assert r_verify.status_code == 200
        return

    make_user(username, role=role, password_hash=hash_password(pwd))
    login(client, username, pwd)


def _create_session(client: TestClient) -> str:
    response = post_csrf(client, "/api/sessions", json={"agent_id": "default_chat"})
    assert response.status_code == 201
    session_id: str = response.json()["id"]
    return session_id


def _parse_sse(raw_text: str) -> list[dict[str, str]]:
    """Parsea el texto crudo SSE en una lista de eventos `id`/`event`/`data`."""
    events: list[dict[str, str]] = []
    current: dict[str, str] = {}
    for line in raw_text.split("\n"):
        if line == "":
            if current:
                events.append(current)
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
        events.append(current)
    return events


def _stream_turn(client: TestClient, session_id: str, text: str) -> dict[str, Any]:
    """Envía un turno en streaming y devuelve el payload (ya parseado) del `done`."""
    csrf_token = client.cookies.get("resultarai_csrf")
    headers = {"X-CSRF-Token": csrf_token} if csrf_token else {}
    with client.stream(
        "POST",
        f"/api/sessions/{session_id}/messages/stream",
        json={"text": text},
        headers=headers,
    ) as response:
        assert response.status_code == 200
        raw = "".join(response.iter_text())
    events = _parse_sse(raw)
    done_event = next(e for e in events if e["event"] == "done")
    payload: dict[str, Any] = json.loads(done_event["data"])
    return payload


# --- Unit: `layer_turn_metadata` / `build_raw_turn_metadata` (función pura) --------


def _sample_raw() -> RawTurnMetadata:
    return build_raw_turn_metadata(
        model_profile_id="openai_gpt_4o",
        is_alternate_model=True,
        primary_model_profile_id="anthropic_claude_haiku",
        fallback_reason="fallback por error del proveedor primario",
        cache_hit_tokens=10,
        cache_miss_tokens=5,
        cost_usd=0.01,
        latency_ms=1234,
        compacted=True,
        escalation={
            "reason": "necesita más razonamiento",
            "target_profile": "deepseek_v4_pro",
        },
    )


def test_layer_turn_metadata_funcional_never_sees_telemetry_key() -> None:
    """Funcional: `telemetry` está AUSENTE del dict devuelto (ni `None` ni `{}`); los
    campos visibles para todos los roles (tarea 5.1, indicador de compaction, evento
    de escalación) siguen presentes.
    """
    view = layer_turn_metadata(_sample_raw(), role="funcional", fallback_trace_id="msg-1")

    assert "telemetry" not in view
    assert view["is_alternate_model"] is True
    assert view["compacted"] is True
    assert view["escalation"] == {
        "reason": "necesita más razonamiento",
        "target_profile": "deepseek_v4_pro",
    }


def test_layer_turn_metadata_tecnico_sees_telemetry_without_trace_id() -> None:
    """Técnico: `telemetry` presente con costo/perfil/cache, SIN `trace_id`."""
    view = layer_turn_metadata(_sample_raw(), role="tecnico", fallback_trace_id="msg-1")

    telemetry = view["telemetry"]
    assert telemetry["cost_usd"] == 0.01
    assert telemetry["model_profile_id"] == "openai_gpt_4o"
    assert telemetry["primary_model_profile_id"] == "anthropic_claude_haiku"
    assert telemetry["fallback_reason"] == "fallback por error del proveedor primario"
    assert telemetry["latency_ms"] == 1234
    assert telemetry["cache_hit_tokens"] == 10
    assert telemetry["cache_miss_tokens"] == 5
    assert telemetry["cache_write_tokens"] is None
    assert "trace_id" not in telemetry


def test_layer_turn_metadata_admin_falls_back_trace_id_to_message_id() -> None:
    """Admin: `telemetry.trace_id` cae al `fallback_trace_id` (id del mensaje) cuando
    el dict crudo no trae un `trace_id` real de Langfuse -- mismo criterio que
    `feedback._resolve_trace_id`.
    """
    view = layer_turn_metadata(_sample_raw(), role="admin", fallback_trace_id="msg-1")
    assert view["telemetry"]["trace_id"] == "msg-1"


def test_layer_turn_metadata_admin_prefers_real_trace_id_when_present() -> None:
    """Admin: si el dict crudo ya trae un `trace_id` real, se usa ese, no el fallback."""
    raw: dict[str, Any] = dict(_sample_raw())
    raw["trace_id"] = "langfuse-trace-123"

    view = layer_turn_metadata(raw, role="admin", fallback_trace_id="msg-1")
    assert view["telemetry"]["trace_id"] == "langfuse-trace-123"


def test_layer_turn_metadata_handles_missing_raw_metadata() -> None:
    """`raw=None` (turno sin metadatos crudos) se trata como un dict vacío."""
    view = layer_turn_metadata(None, role="admin", fallback_trace_id="msg-1")

    assert view["is_alternate_model"] is False
    assert view["compacted"] is False
    assert view["escalation"] is None
    assert view["telemetry"]["cost_usd"] is None
    assert view["telemetry"]["trace_id"] == "msg-1"


def test_build_raw_turn_metadata_cache_write_tokens_always_none() -> None:
    """`cache_write_tokens` no es un parámetro del builder: siempre viaja en `None`
    (hueco de `LLMResponse` de `b05-gateway-modelos`, ver
    `openspec/BACKLOG-DESCUBRIMIENTOS.md`).
    """
    raw = build_raw_turn_metadata(model_profile_id="openai_gpt_4o")
    assert raw["cache_write_tokens"] is None


# --- Contrato: evento `done` del streaming (tarea 1.5 + 4.1) -----------------------


def test_stream_done_event_omits_telemetry_key_for_funcional(
    client: TestClient, streaming_generator: _StreamingDoubleGenerator
) -> None:
    """Sesión Funcional: el evento `done` NO contiene la clave `telemetry` en
    absoluto (criterio de la tarea 4.1: `not in`), pero sí `is_alternate_model`.
    """
    _create_user_and_login(client, "telemetry-stream-func", role="funcional")
    session_id = _create_session(client)

    done_data = _stream_turn(client, session_id, "hola")

    assert "telemetry" not in done_data
    assert "is_alternate_model" in done_data
    assert done_data["is_alternate_model"] is False
    assert "compacted" in done_data
    assert "escalation" in done_data


def test_stream_done_event_includes_telemetry_for_tecnico_without_trace_id(
    client: TestClient, streaming_generator: _StreamingDoubleGenerator
) -> None:
    """Sesión Técnico: `telemetry` presente con datos numéricos, sin `trace_id`."""
    _create_user_and_login(client, "telemetry-stream-tec", role="tecnico")
    session_id = _create_session(client)

    done_data = _stream_turn(client, session_id, "hola")

    telemetry = done_data["telemetry"]
    assert isinstance(telemetry["cost_usd"], float)
    assert isinstance(telemetry["model_profile_id"], str)
    assert isinstance(telemetry["latency_ms"], int)
    assert telemetry["latency_ms"] >= 0
    assert telemetry["cache_hit_tokens"] == 12
    assert telemetry["cache_miss_tokens"] == 3
    assert "trace_id" not in telemetry


def test_stream_done_event_includes_trace_id_for_admin(
    client: TestClient, streaming_generator: _StreamingDoubleGenerator
) -> None:
    """Sesión Admin: `telemetry` presente, además con `trace_id`."""
    _create_user_and_login(client, "telemetry-stream-admin", role="admin")
    session_id = _create_session(client)

    done_data = _stream_turn(client, session_id, "hola")

    telemetry = done_data["telemetry"]
    assert isinstance(telemetry["cost_usd"], float)
    assert telemetry["trace_id"]


# --- Contrato: POST /sessions/{id}/messages y /messages/{id}/regenerate (síncrono) -


def test_send_turn_response_omits_telemetry_key_for_funcional(client: TestClient) -> None:
    """Sesión Funcional: `assistant_message.turn_metadata` no trae `telemetry` (test
    de contrato de la tarea 4.1), pero sí `is_alternate_model` (tarea 5.1). El mensaje
    de usuario del mismo turno no lleva `turn_metadata` (no hay telemetría que
    reportar sobre un mensaje de usuario).
    """
    _create_user_and_login(client, "telemetry-turn-func", role="funcional")
    session_id = _create_session(client)

    response = post_csrf(client, f"/api/sessions/{session_id}/messages", json={"text": "hola"})
    assert response.status_code == 201
    data = response.json()

    assistant_metadata = data["assistant_message"]["turn_metadata"]
    assert "telemetry" not in assistant_metadata
    assert assistant_metadata["is_alternate_model"] is False
    assert data["user_message"]["turn_metadata"] is None


def test_send_turn_response_includes_telemetry_for_tecnico_without_trace_id(
    client: TestClient,
) -> None:
    """Sesión Técnico: `telemetry` presente con `cost_usd`/`model_profile_id`/
    `latency_ms` numéricos, sin `trace_id`.
    """
    _create_user_and_login(client, "telemetry-turn-tec", role="tecnico")
    session_id = _create_session(client)

    response = post_csrf(client, f"/api/sessions/{session_id}/messages", json={"text": "hola"})
    assert response.status_code == 201
    telemetry = response.json()["assistant_message"]["turn_metadata"]["telemetry"]

    assert telemetry["model_profile_id"]
    assert isinstance(telemetry["latency_ms"], int)
    assert telemetry["latency_ms"] >= 0
    assert "cost_usd" in telemetry  # el generador síncrono no expone costo: None
    assert "trace_id" not in telemetry


def test_send_turn_response_includes_trace_id_for_admin(client: TestClient) -> None:
    """Sesión Admin: `telemetry.trace_id` presente."""
    _create_user_and_login(client, "telemetry-turn-admin", role="admin")
    session_id = _create_session(client)

    response = post_csrf(client, f"/api/sessions/{session_id}/messages", json={"text": "hola"})
    assert response.status_code == 201
    telemetry = response.json()["assistant_message"]["turn_metadata"]["telemetry"]
    assert telemetry["trace_id"]


def test_regenerate_response_respects_role_layering(client: TestClient) -> None:
    """`POST /messages/{id}/regenerate` aplica el mismo filtrado por rol que el turno
    normal: ausencia total de `telemetry` para Funcional.
    """
    _create_user_and_login(client, "telemetry-regen-func", role="funcional")
    session_id = _create_session(client)
    turn = post_csrf(client, f"/api/sessions/{session_id}/messages", json={"text": "hola"})
    assert turn.status_code == 201
    assistant_id = turn.json()["assistant_message"]["id"]

    regen = post_csrf(client, f"/api/messages/{assistant_id}/regenerate")
    assert regen.status_code == 201
    metadata = regen.json()["message"]["turn_metadata"]
    assert "telemetry" not in metadata
    assert metadata["is_alternate_model"] is False


# --- Contrato: GET /sessions/{id} (detalle, tarea 2.3 + 4.1) -----------------------


def test_session_detail_omits_telemetry_for_funcional_assistant_messages(
    client: TestClient,
) -> None:
    """El árbol de la sesión, para un usuario Funcional, no expone `telemetry` en
    NINGÚN mensaje `assistant` -- ni el del turno síncrono ni el del turno en
    streaming.
    """
    _create_user_and_login(client, "telemetry-detail-func", role="funcional")
    session_id = _create_session(client)
    sync_response = post_csrf(
        client, f"/api/sessions/{session_id}/messages", json={"text": "turno sincrono"}
    )
    assert sync_response.status_code == 201
    _stream_turn(client, session_id, "turno en streaming")

    response = client.get(f"/api/sessions/{session_id}")
    assert response.status_code == 200
    messages = response.json()["messages"]

    assistant_messages = [m for m in messages if m["role"] == "assistant"]
    assert len(assistant_messages) == 2
    for message in assistant_messages:
        assert "telemetry" not in message["turn_metadata"]
        assert message["turn_metadata"]["is_alternate_model"] is False


def test_session_detail_includes_telemetry_for_admin_assistant_message(
    client: TestClient,
) -> None:
    """Para Admin, el mismo árbol expone `telemetry` (con `trace_id`) en un mensaje
    `assistant`.
    """
    _create_user_and_login(client, "telemetry-detail-admin", role="admin")
    session_id = _create_session(client)
    response = post_csrf(
        client, f"/api/sessions/{session_id}/messages", json={"text": "turno sincrono"}
    )
    assert response.status_code == 201

    detail = client.get(f"/api/sessions/{session_id}")
    assert detail.status_code == 200
    messages = detail.json()["messages"]

    assistant_message = next(m for m in messages if m["role"] == "assistant")
    telemetry = assistant_message["turn_metadata"]["telemetry"]
    assert telemetry["trace_id"]


def test_session_detail_leaves_user_message_turn_metadata_unfiltered(
    client: TestClient,
) -> None:
    """Un mensaje `user` no pasa por el filtrado por rol: su `turn_metadata` (hoy
    siempre `None` en el camino de turno normal, ver `turns.py`) viaja tal cual.
    """
    _create_user_and_login(client, "telemetry-detail-user-msg", role="funcional")
    session_id = _create_session(client)
    response = post_csrf(client, f"/api/sessions/{session_id}/messages", json={"text": "hola"})
    assert response.status_code == 201

    detail = client.get(f"/api/sessions/{session_id}")
    assert detail.status_code == 200
    messages = detail.json()["messages"]

    user_message = next(m for m in messages if m["role"] == "user")
    assert user_message["turn_metadata"] is None
