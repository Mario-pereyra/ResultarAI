"""Helpers de bookkeeping de ramas compartidos por `turns.py` y `streaming.py`.

Modulo interno (prefijo `_`, no exportado en `__init__.py`): existia como funciones
privadas de `turns.py` (tareas 1.2/1.3); se extraen aqui sin cambiar su
comportamiento para que la tarea 1.5 (streaming) las reutilice sin duplicar la
logica de "rama activa" (ver docstring de `turns.py` para la definicion completa
de esa nocion) ni reimplementar el ownership de sesiones.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession
from sqlalchemy.orm import aliased

from resultarai.adapters.persistence_postgres.models import Message, User
from resultarai.adapters.persistence_postgres.models import Session as SessionModel

__all__ = [
    "ancestor_chain",
    "count_active_descendants",
    "find_active_leaf",
    "find_owned_session",
]


def find_active_leaf(db: DbSession, session_id: str) -> Message | None:
    """Devuelve el leaf (mensaje sin hijos) con `created_at` mas reciente de la sesion.

    Define la rama activa (ver docstring de `turns.py`). `None` si la sesion todavia
    no tiene ningun mensaje.
    """
    child = aliased(Message)
    has_child = select(child.id).where(child.parent_id == Message.id).exists()
    stmt = (
        select(Message)
        .where(Message.session_id == session_id, ~has_child)
        .order_by(Message.created_at.desc(), Message.id.desc())
        .limit(1)
    )
    return db.execute(stmt).scalars().first()


def ancestor_chain(db: DbSession, message: Message) -> list[Message]:
    """Devuelve la cadena de `message` hasta la raiz, ordenada de raiz a `message`."""
    chain: list[Message] = [message]
    current = message
    while current.parent_id is not None:
        parent = db.get(Message, current.parent_id)
        if parent is None:
            break
        chain.append(parent)
        current = parent
    chain.reverse()
    return chain


def count_active_descendants(db: DbSession, message_id: uuid.UUID) -> int:
    """Cuenta los mensajes posteriores a `message_id` en su rama (para `reprocessed_count`).

    Baja desde `message_id` siguiendo, en cada bifurcacion, al hijo con `created_at` mas
    reciente (la misma nocion de "rama activa" del docstring de `turns.py`, acotada al
    subarbol de `message_id`). Devuelve 0 si `message_id` es una hoja.
    """
    count = 0
    current_id: uuid.UUID = message_id
    while True:
        child = (
            db.execute(
                select(Message)
                .where(Message.parent_id == current_id)
                .order_by(Message.created_at.desc(), Message.id.desc())
                .limit(1)
            )
            .scalars()
            .first()
        )
        if child is None:
            return count
        count += 1
        current_id = child.id


def find_owned_session(db: DbSession, user: User, session_id: str) -> SessionModel | None:
    """Devuelve la sesion si existe y pertenece a `user`; `None` en cualquier otro caso.

    No lanza: cada llamador (`turns.py`, `streaming.py`) traduce el `None` a su propia
    excepcion de dominio (`SessionNotFoundError` en ambos casos hoy, pero se deja la
    traduccion afuera para no crear un ciclo de import entre estos dos modulos).
    """
    session = db.get(SessionModel, session_id)
    if session is None or session.owner_user_id != user.id:
        return None
    return session
