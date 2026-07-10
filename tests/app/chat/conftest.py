"""Fixtures compartidas de los tests de chat (d13-chat-conversacion, tarea 1.1).

Sigue el patron de ``tests/app/identity/conftest.py``: Postgres real (contenedor
``resultarai_postgres``) via ``get_db_session``, con una fixture ``autouse`` que
vacia las tablas de conversacion antes y despues de cada test para aislarlos.
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from sqlalchemy import text

from resultarai.adapters.persistence_postgres.connection import get_db_session

_CHAT_TABLES = ("sessions", "messages")


@pytest.fixture(autouse=True)
def cleanup_chat() -> Generator[None, None, None]:
    """Vacia `sessions` y `messages` antes y despues de cada test."""
    statement = text("TRUNCATE TABLE " + ", ".join(_CHAT_TABLES) + " CASCADE")
    with get_db_session() as session:
        session.execute(statement)
        session.commit()

    yield

    with get_db_session() as session:
        session.execute(statement)
        session.commit()
