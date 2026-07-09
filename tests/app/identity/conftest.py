"""Fixtures y helpers compartidos de los tests de identidad (d11, sección 2).

Los tests que tocan tablas usan el Postgres real (contenedor ``resultarai_postgres``)
a través de ``get_db_session``, siguiendo el patrón de
``tests/contracts/test_identity_schema.py``. La fixture ``cleanup_identity`` vacía
las tablas de identidad antes y después de cada test para aislarlos.
"""

from __future__ import annotations

import uuid
from collections.abc import Generator

import pytest
from sqlalchemy import text

from resultarai.adapters.persistence_postgres.connection import get_db_session
from resultarai.adapters.persistence_postgres.models import User

_IDENTITY_TABLES = (
    "users",
    "auth_sessions",
    "totp_secrets",
    "totp_backup_codes",
    "login_attempts",
    "groups",
    "group_members",
    "usage_agreement_versions",
    "usage_agreement_acceptances",
    "identity_audit_events",
)


@pytest.fixture(autouse=True)
def cleanup_identity() -> Generator[None, None, None]:
    """Vacía las tablas de identidad antes y después de cada test."""
    statement = text("TRUNCATE TABLE " + ", ".join(_IDENTITY_TABLES) + " CASCADE")
    with get_db_session() as session:
        session.execute(statement)
        session.commit()

    yield

    with get_db_session() as session:
        session.execute(statement)
        session.commit()


def make_user(
    username: str,
    *,
    role: str = "funcional",
    status: str = "active",
    password_hash: str = "$argon2id$fake-hash-for-tests",
) -> uuid.UUID:
    """Crea un usuario mínimo válido y devuelve su id."""
    with get_db_session() as session:
        user = User(
            username=username,
            display_name=username.title(),
            role=role,
            password_hash=password_hash,
            status=status,
        )
        session.add(user)
        session.flush()
        return user.id
