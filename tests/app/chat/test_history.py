# ruff: noqa: E402
"""Integration tests para GET /sessions, GET /sessions/{id} y GET /sessions/search.

d13-chat-conversacion, tareas 2.1 (listado), 2.3 (detalle con árbol de ramas) y 2.4
(búsqueda server-side).
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
from tests.app.identity.conftest import make_user

_CONFIG = SessionConfig(
    signing_key="test-chat-key-for-history",
    idle_timeout=datetime.timedelta(minutes=30),
    absolute_lifetime=datetime.timedelta(hours=8),
    cookie_secure=False,  # deshabilitado Secure para extraer la cookie en el test client
)


class _EchoResponseGenerator:
    """Doble mínimo de `ResponseGenerator`: texto fijo, no depende de ningún LLM.

    El contenido de los mensajes de usuario (controlado por cada test) es lo que
    importa para la búsqueda (tarea 2.4); el texto de la respuesta del agente es
    irrelevante siempre que sea estable y no colisione con los términos buscados.
    """

    def __call__(self, *, session: Any, history: Any) -> str:
        return "respuesta del agente"


@pytest.fixture
def response_generator() -> _EchoResponseGenerator:
    return _EchoResponseGenerator()


@pytest.fixture
def client(response_generator: _EchoResponseGenerator) -> Iterator[TestClient]:
    """TestClient con overrides de DB, config de sesión, Registries reales y el doble
    de generación de respuesta síncrona.
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


def _create_user_and_login(client: TestClient, prefix: str, role: str = "funcional") -> str:
    pwd = "ValidPassword123!"
    username = _unique_username(prefix)
    make_user(username, role=role, password_hash=hash_password(pwd))
    login(client, username, pwd)
    return username


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
    response = post_csrf(client, f"/api/sessions/{session_id}/messages", json=payload)
    assert response.status_code == 201
    return response.json()


# --- Tarea 2.1: GET /sessions (listado propio) -------------------------------------


def test_list_sessions_message_and_branch_counts(client: TestClient) -> None:
    """`message_count`/`branch_count`: una sesión lineal tiene `branch_count == 0`;
    una sesión con una edición (bifurcación) tiene `branch_count >= 1`.
    """
    _create_user_and_login(client, "hist-counts-user")

    linear_session = _create_session(client)
    _send_message(client, linear_session, "único turno, sin ediciones")

    branched_session = _create_session(client)
    turn1 = _send_message(client, branched_session, "primer mensaje original")
    _send_message(client, branched_session, "segundo mensaje")
    # Editar el primer mensaje de usuario crea una rama hermana (punto de bifurcación).
    _send_message(
        client,
        branched_session,
        "primer mensaje EDITADO",
        edits_message_id=turn1["user_message"]["id"],
    )

    response = client.get("/api/sessions")
    assert response.status_code == 200
    items = {item["id"]: item for item in response.json()["items"]}

    assert items[linear_session]["message_count"] == 2
    assert items[linear_session]["branch_count"] == 0

    # 2 turnos (4 mensajes) + edición (2 mensajes más: usuario editado + su respuesta).
    assert items[branched_session]["message_count"] == 6
    assert items[branched_session]["branch_count"] == 1


def test_list_sessions_never_leaks_across_users() -> None:
    """El listado de un usuario nunca incluye sesiones de otro (dos usuarios, dos
    clientes independientes para no depender del orden de login/logout en un mismo
    client).
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
    app.dependency_overrides[get_response_generator] = lambda: _EchoResponseGenerator()

    with TestClient(app) as client_a, TestClient(app) as client_b:
        _create_user_and_login(client_a, "hist-leak-a")
        session_a1 = _create_session(client_a)
        session_a2 = _create_session(client_a)
        # Reactivar session_a1 después de crear session_a2 para ejercer el orden
        # por última actividad (no por creación).
        _send_message(client_a, session_a1, "reactivo la primera sesión")

        _create_user_and_login(client_b, "hist-leak-b")
        session_b1 = _create_session(client_b)

        response_a = client_a.get("/api/sessions")
        assert response_a.status_code == 200
        ids_a = [item["id"] for item in response_a.json()["items"]]
        assert set(ids_a) == {session_a1, session_a2}
        assert session_b1 not in ids_a
        # Orden por última actividad descendente: session_a1 (reactivada) primero.
        assert ids_a == [session_a1, session_a2]

        response_b = client_b.get("/api/sessions")
        assert response_b.status_code == 200
        ids_b = [item["id"] for item in response_b.json()["items"]]
        assert ids_b == [session_b1]
        assert session_a1 not in ids_b
        assert session_a2 not in ids_b


def test_list_sessions_requires_authentication(client: TestClient) -> None:
    """Sin cookie de sesión válida, listar sesiones responde 401."""
    response = client.get("/api/sessions")
    assert response.status_code == 401


# --- Tarea 2.3: GET /sessions/{id} (árbol completo) ---------------------------------


def test_session_detail_includes_both_branches_with_active_leaf(client: TestClient) -> None:
    """El árbol retornado contiene TODOS los mensajes de ambas ramas, con su
    `parent_id`, y `active_leaf_id` apunta a la rama más reciente.
    """
    _create_user_and_login(client, "hist-detail-user")
    session_id = _create_session(client)

    turn1 = _send_message(client, session_id, "primer mensaje original")
    u1_id = turn1["user_message"]["id"]
    a1_id = turn1["assistant_message"]["id"]

    turn2 = _send_message(client, session_id, "segundo mensaje")
    u2_id = turn2["user_message"]["id"]
    a2_id = turn2["assistant_message"]["id"]

    edit = _send_message(client, session_id, "primer mensaje EDITADO", edits_message_id=u1_id)
    u1_edit_id = edit["user_message"]["id"]
    a1_edit_id = edit["assistant_message"]["id"]

    response = client.get(f"/api/sessions/{session_id}")
    assert response.status_code == 200
    data = response.json()

    assert data["id"] == session_id
    assert data["agent_id"] == "default_chat"

    messages_by_id = {m["id"]: m for m in data["messages"]}
    expected_ids = {u1_id, a1_id, u2_id, a2_id, u1_edit_id, a1_edit_id}
    assert set(messages_by_id.keys()) == expected_ids

    # Rama original: u1 (raíz) -> a1 -> u2 -> a2.
    assert messages_by_id[u1_id]["parent_id"] is None
    assert messages_by_id[a1_id]["parent_id"] == u1_id
    assert messages_by_id[u2_id]["parent_id"] == a1_id
    assert messages_by_id[a2_id]["parent_id"] == u2_id

    # Rama descartada por la edición: mismo parent_id que u1 (raíz), navegable aparte.
    assert messages_by_id[u1_edit_id]["parent_id"] is None
    assert messages_by_id[a1_edit_id]["parent_id"] == u1_edit_id

    # La rama activa es la más reciente: la creada por la edición.
    assert data["active_leaf_id"] == a1_edit_id


def test_session_detail_of_foreign_session_returns_404(client: TestClient) -> None:
    """El detalle de una sesión ajena responde 404 sin filtrar su existencia."""
    _create_user_and_login(client, "hist-detail-owner")
    owner_session_id = _create_session(client)

    _create_user_and_login(client, "hist-detail-intruder")
    response = client.get(f"/api/sessions/{owner_session_id}")
    assert response.status_code == 404


def test_session_detail_exposes_escalation_linkage(client: TestClient) -> None:
    """El detalle expone `forked_from_id` (destino) y `escalated_session_ids` (origen)
    para la nota-enlace bidireccional de la vista 08.
    """
    _create_user_and_login(client, "hist-escalation-user")
    origin_session_id = _create_session(client)
    _send_message(client, origin_session_id, "necesito escalar esto")

    escalate_response = post_csrf(client, f"/api/sessions/{origin_session_id}/escalate", json={})
    assert escalate_response.status_code == 201
    escalated_session_id = escalate_response.json()["escalated_session_id"]

    origin_detail = client.get(f"/api/sessions/{origin_session_id}").json()
    assert origin_detail["forked_from_id"] is None
    assert origin_detail["escalated_session_ids"] == [escalated_session_id]

    escalated_detail = client.get(f"/api/sessions/{escalated_session_id}").json()
    assert escalated_detail["forked_from_id"] == origin_session_id
    assert escalated_detail["escalated_session_ids"] == []


# --- Tarea 2.4: GET /sessions/search (búsqueda server-side) -------------------------


def test_search_sessions_finds_term_in_message_content(client: TestClient) -> None:
    """Un término presente en el contenido de un mensaje retorna la sesión, con el
    término identificable (`snippet` + offsets) en el resultado.
    """
    from resultarai.adapters.persistence_postgres.models import Session as SessionModel

    _create_user_and_login(client, "hist-search-msg-user")
    session_id = _create_session(client)
    term = f"zanahoria{uuid.uuid4().hex[:8]}"
    _send_message(client, session_id, f"necesito ayuda con la {term} urgente")

    # Edita el título de la sesión para que NO contenga el término, así la búsqueda
    # encuentra el término en el mensaje, no en el título (tarea 2.2).
    with get_db_session() as db:
        session_row = db.get(SessionModel, session_id)
        assert session_row is not None
        session_row.title = "Mi sesión de consulta"
        db.commit()

    response = client.get("/api/sessions/search", params={"q": term})
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    hit = items[0]
    assert hit["session_id"] == session_id
    assert hit["match_type"] == "message"
    assert hit["message_id"] is not None
    snippet = hit["snippet"]
    matched_fragment = snippet[hit["match_start"] : hit["match_end"]]
    assert matched_fragment.lower() == term.lower()


def test_search_sessions_finds_term_in_title_only(client: TestClient) -> None:
    """Un término presente solo en el título (sin aparecer en ningún mensaje)
    también retorna la sesión.
    """
    _create_user_and_login(client, "hist-search-title-user")
    session_id = _create_session(client)
    _send_message(client, session_id, "contenido sin relación con el término buscado")

    title_term = f"Parametrizacion{uuid.uuid4().hex[:8]}"
    with get_db_session() as db:
        session_row = db.get(SessionModel, session_id)
        assert session_row is not None
        session_row.title = f"{title_term} de sucursal"
        db.commit()

    response = client.get("/api/sessions/search", params={"q": title_term})
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) == 1
    assert items[0]["session_id"] == session_id
    assert items[0]["match_type"] == "title"
    assert items[0]["message_id"] is None


def test_search_sessions_absent_term_returns_empty_list_without_error(
    client: TestClient,
) -> None:
    """Un término ausente en título y mensajes retorna una lista vacía, sin error."""
    _create_user_and_login(client, "hist-search-absent-user")
    session_id = _create_session(client)
    _send_message(client, session_id, "contenido que no incluye el término")

    response = client.get(
        "/api/sessions/search", params={"q": f"terminoinexistente{uuid.uuid4().hex}"}
    )
    assert response.status_code == 200
    assert response.json()["items"] == []


def test_search_sessions_never_returns_other_users_sessions() -> None:
    """La búsqueda de un usuario nunca retorna sesiones de otro, aunque el término
    exista en el contenido de una sesión ajena.
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
    app.dependency_overrides[get_response_generator] = lambda: _EchoResponseGenerator()

    with TestClient(app) as client_a, TestClient(app) as client_b:
        _create_user_and_login(client_a, "hist-search-leak-a")
        term = f"manzana{uuid.uuid4().hex[:8]}"
        session_a = _create_session(client_a)
        _send_message(client_a, session_a, f"la {term} está en la sesión de A")

        _create_user_and_login(client_b, "hist-search-leak-b")

        response_b = client_b.get("/api/sessions/search", params={"q": term})
        assert response_b.status_code == 200
        assert response_b.json()["items"] == []

        response_a = client_a.get("/api/sessions/search", params={"q": term})
        assert response_a.status_code == 200
        assert [item["session_id"] for item in response_a.json()["items"]] == [session_a]


def test_search_sessions_term_with_percent_does_not_break_and_matches_literally(
    client: TestClient,
) -> None:
    """Un término con `%` no rompe la búsqueda y matchea el caracter literal, no
    como comodín de SQL sin escapar.
    """
    _create_user_and_login(client, "hist-search-percent-user")
    unique = uuid.uuid4().hex[:8]
    term = f"100%{unique}"

    session_with_percent = _create_session(client)
    _send_message(client, session_with_percent, f"descuento de {term} aplicado hoy")

    session_without_percent = _create_session(client)
    # Contiene el prefijo "100" + el sufijo unico pero SIN el caracter '%' literal:
    # si el termino no se escapara, el '%' se interpretaria como comodin de SQL y
    # esta sesion tambien matchearia incorrectamente.
    _send_message(client, session_without_percent, f"descuento de 100 {unique} aplicado hoy")

    response = client.get("/api/sessions/search", params={"q": term})
    assert response.status_code == 200
    items = response.json()["items"]
    assert [item["session_id"] for item in items] == [session_with_percent]
