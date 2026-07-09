"""Tests de protección CSRF por doble envío (d11, tarea 2.6)."""

from __future__ import annotations

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from resultarai.app.identity.csrf import (
    CSRF_COOKIE,
    CSRF_HEADER,
    issue_csrf_token,
    require_csrf,
    verify_csrf,
)


def test_issue_csrf_token_is_random() -> None:
    """Dos emisiones producen tokens distintos y no vacíos."""
    a = issue_csrf_token()
    b = issue_csrf_token()
    assert a
    assert b
    assert a != b


def test_verify_csrf_matches_and_rejects() -> None:
    """``verify_csrf`` acepta iguales y rechaza distintos o ausentes."""
    token = issue_csrf_token()
    assert verify_csrf(token, token) is True
    assert verify_csrf(token, "otro") is False
    assert verify_csrf(None, token) is False
    assert verify_csrf(token, None) is False


def _csrf_app() -> FastAPI:
    app = FastAPI()

    @app.post("/mutate", dependencies=[Depends(require_csrf)])
    def mutate() -> dict[str, bool]:
        return {"ok": True}

    return app


def test_mutation_without_header_is_forbidden() -> None:
    """Una mutación sin header CSRF responde 403 aunque tenga la cookie."""
    client = TestClient(_csrf_app())
    client.cookies.set(CSRF_COOKIE, "un-token")
    response = client.post("/mutate")
    assert response.status_code == 403


def test_mutation_with_valid_header_passes() -> None:
    """Con header y cookie coincidentes, la mutación pasa."""
    token = issue_csrf_token()
    client = TestClient(_csrf_app())
    client.cookies.set(CSRF_COOKIE, token)
    response = client.post("/mutate", headers={CSRF_HEADER: token})
    assert response.status_code == 200
    assert response.json() == {"ok": True}


def test_mutation_with_mismatched_header_is_forbidden() -> None:
    """Con header que no coincide con la cookie, responde 403."""
    client = TestClient(_csrf_app())
    client.cookies.set(CSRF_COOKIE, issue_csrf_token())
    response = client.post("/mutate", headers={CSRF_HEADER: issue_csrf_token()})
    assert response.status_code == 403
