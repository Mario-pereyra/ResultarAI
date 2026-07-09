"""Tests de los dependencies de identidad (d11, tarea 2.3).

Property de seguridad central: el usuario se resuelve solo de la cookie de sesión;
cualquier ``userId`` en el body se ignora por construcción.
"""

from __future__ import annotations

import uuid
from collections.abc import Iterator
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session as DbSession

from resultarai.adapters.persistence_postgres.connection import SessionLocal, get_db_session
from resultarai.adapters.persistence_postgres.models import User
from resultarai.app.identity.dependency import (
    get_current_user,
    get_db,
    get_session_config,
    require_admin,
)
from resultarai.app.identity.sessions import (
    SESSION_COOKIE,
    SessionConfig,
    create_session,
)
from tests.app.identity.conftest import make_user

_CONFIG = SessionConfig(signing_key="dependency-test-signing-key")


def _override_db() -> Iterator[DbSession]:
    """Proveedor de sesión de base para el test (sobreescribe get_db)."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    finally:
        session.close()


def _build_app() -> FastAPI:
    app = FastAPI()

    @app.post("/me")
    def whoami(user: Annotated[User, Depends(get_current_user)]) -> dict[str, str]:
        return {"user_id": str(user.id)}

    @app.get("/admin-only")
    def admin_only(user: Annotated[User, Depends(require_admin)]) -> dict[str, str]:
        return {"user_id": str(user.id)}

    app.dependency_overrides[get_db] = _override_db
    app.dependency_overrides[get_session_config] = lambda: _CONFIG
    return app


def _issue_cookie(user_id: uuid.UUID) -> str:
    with get_db_session() as db:
        created = create_session(db, user_id, _CONFIG)
    return created.cookie_value


def test_body_user_id_is_ignored() -> None:
    """Autenticado como A con body {"userId": B}, la operación ejecuta como A."""
    user_a = make_user("dep-a")
    user_b = make_user("dep-b")
    client = TestClient(_build_app())
    client.cookies.set(SESSION_COOKIE, _issue_cookie(user_a))

    response = client.post("/me", json={"userId": str(user_b)})
    assert response.status_code == 200
    assert response.json() == {"user_id": str(user_a)}


def test_missing_cookie_returns_401() -> None:
    """Sin cookie de sesión, el endpoint responde 401."""
    make_user("dep-nocookie")
    client = TestClient(_build_app())
    response = client.post("/me", json={})
    assert response.status_code == 401


def test_require_admin_forbids_non_admin() -> None:
    """Un rol no-admin recibe 403 en una ruta protegida por require_admin."""
    user_id = make_user("dep-funcional", role="funcional")
    client = TestClient(_build_app())
    client.cookies.set(SESSION_COOKIE, _issue_cookie(user_id))

    response = client.get("/admin-only")
    assert response.status_code == 403


def test_require_admin_allows_admin() -> None:
    """Un rol admin accede a la ruta protegida por require_admin."""
    user_id = make_user("dep-admin", role="admin")
    client = TestClient(_build_app())
    client.cookies.set(SESSION_COOKIE, _issue_cookie(user_id))

    response = client.get("/admin-only")
    assert response.status_code == 200
    assert response.json() == {"user_id": str(user_id)}
