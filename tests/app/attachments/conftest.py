"""Fixtures compartidas de los tests de adjuntos (d14, tareas 2.1-2.3).

Sigue el patron de ``tests/app/chat/conftest.py``: Postgres real (contenedor
``resultarai_postgres``) via ``get_db_session``, con una fixture ``autouse`` que vacia
las tablas de adjuntos y conversacion antes y despues de cada test para aislarlos. No
trunca ``users`` (los tests usan usernames unicos, igual que la suite de chat).
"""

from __future__ import annotations

from collections.abc import Generator

import pytest
from sqlalchemy import text

from resultarai.adapters.persistence_postgres.connection import get_db_session

_ATTACHMENT_TABLES = (
    "message_attachments",
    "attachments",
    "extractions",
    "sessions",
    "messages",
)


@pytest.fixture(autouse=True)
def cleanup_attachments() -> Generator[None, None, None]:
    """Vacia las tablas de adjuntos y conversacion antes y despues de cada test."""
    statement = text("TRUNCATE TABLE " + ", ".join(_ATTACHMENT_TABLES) + " CASCADE")
    with get_db_session() as session:
        session.execute(statement)
        session.commit()

    yield

    with get_db_session() as session:
        session.execute(statement)
        session.commit()
