"""Casos de uso de chat: envío de turno, edición (bifurcación) y regeneración de respuesta.

d13-chat-conversacion, tareas 1.2 y 1.3. Separa dos responsabilidades que hasta ahora
vivían implícitas en el modelo de datos de `b04-persistencia-postgres`:

(a) el encadenado del mensaje de usuario (`send_turn`) -- decide de qué `parent_id`
    cuelga el mensaje nuevo (turno normal: el último mensaje de la rama activa; edición:
    el mismo `parent_id` que el mensaje editado, creando una rama hermana) -- y

(b) la generación de la respuesta del agente, que NO vive aquí: se recibe como un
    callable inyectado (`ResponseGenerator`), siguiendo el mismo patrón "provider" que
    `get_db`/`get_registries` (`resultarai/app/api/chat.py`,
    `resultarai/app/identity/dependency.py`). En producción ese provider invocará el
    runtime de `b06-runtime-grafos`
    (`resultarai/adapters/runtime_langgraph/default_chat_graph.py`); en los tests de API
    se sobreescribe con un doble que devuelve texto fijo (mismo patrón que
    `tests/contracts/fixtures/doubles.py`, sin depender de él porque este módulo no es un
    contract test). Separar (a) de (b) es lo que permite que la tarea 1.5 (streaming SSE)
    reemplace únicamente el generador por una versión que emite fragmentos incrementales,
    sin tocar el bookkeeping de ramas de este módulo.

**Rama activa (decisión de diseño, sin columnas nuevas):** la rama activa de una sesión
es la que termina en el "leaf" (mensaje sin hijos, es decir, ningún otro mensaje lo
referencia como `parent_id`) con el `created_at` más reciente de la sesión. Un turno
normal (`send_turn` sin `edits_message_id`) cuelga el mensaje de usuario nuevo de ese
leaf. No hace falta una columna `is_active_branch` ni similar: el propio orden temporal
de inserción (append-only, nunca se reescribe la historia) alcanza para derivarla en cada
petición. Esta misma regla la reutilizan la tarea 2.5 ("reanudar": abrir una sesión
posiciona en su rama activa) y el selector de versiones de la tarea 5.4 en el frontend.

No vive en `core/` (regla dura 1): orquesta persistencia (SQLAlchemy) y un callable de
aplicación, ninguno de los dos permitido dentro del núcleo.

**Tarea 4.1 -- `turn_metadata` en el camino síncrono.** A diferencia de
`streaming.py` (que recibe un `TurnCompletion` con costo/cache del runtime), el
`ResponseGenerator` de este módulo devuelve únicamente `str` (contrato deliberado de
las tareas 1.2/1.3, ver `ResponseGenerator` abajo): no hay costo, cache ni
"modelo alterno" real que reportar. Aun así se persiste `Message.turn_metadata` (vía
`build_raw_turn_metadata`, `telemetry.py`) con lo que SÍ se conoce --
`model_profile_id` (de `session.model_profile`) y `latency_ms` (medido alrededor de
`generate_response`) -- y el resto en `None`/`False`, para que el filtrado por rol de
la tarea 4.1 (`app/api/chat.py`) tenga un dict crudo consistente con el que arma
`streaming.py`, aunque más pobre en datos. Hueco anotado en
`openspec/BACKLOG-DESCUBRIMIENTOS.md`: el día que `ResponseGenerator` (o su
implementación real) exponga esos datos, esta función los recoge sin cambiar su
shape.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from resultarai.adapters.persistence_postgres.models import Message, User, get_utc_now
from resultarai.adapters.persistence_postgres.models import Session as SessionModel
from resultarai.app.use_cases.chat._branching import (
    ancestor_chain,
    count_active_descendants,
    find_active_leaf,
    find_owned_session,
)
from resultarai.app.use_cases.chat.telemetry import build_raw_turn_metadata
from resultarai.app.use_cases.chat.titles import generate_session_title

__all__ = [
    "MessageEditForbiddenError",
    "MessageNotEligibleError",
    "MessageNotFoundError",
    "RegenerateResult",
    "ResponseGenerator",
    "SessionNotFoundError",
    "TurnResult",
    "regenerate_response",
    "send_turn",
]


class SessionNotFoundError(Exception):
    """La sesión no existe o no pertenece al usuario actual.

    La API traduce esto a 404 sin distinguir "no existe" de "existe pero es de otro
    usuario" (regla dura de ownership: nunca filtrar existencia de sesiones ajenas).
    """

    def __init__(self, session_id: str) -> None:
        super().__init__(f"sesión no encontrada o no pertenece al usuario: {session_id!r}")
        self.session_id = session_id


class MessageEditForbiddenError(Exception):
    """`edits_message_id` no referencia un mensaje de usuario propio de esta sesión.

    Cubre tanto "el mensaje no existe" como "pertenece a otra sesión/otro rol": en ambos
    casos se rechaza sin crear ninguna fila, sin distinguir el motivo exacto al cliente
    (mismo criterio de no filtrar detalles que `SessionNotFoundError`).
    """

    def __init__(self, message_id: uuid.UUID) -> None:
        super().__init__(f"mensaje no editable por el usuario actual: {message_id!r}")
        self.message_id = message_id


class MessageNotFoundError(Exception):
    """El mensaje a regenerar no existe o su sesión no pertenece al usuario actual."""

    def __init__(self, message_id: uuid.UUID) -> None:
        super().__init__(f"mensaje no encontrado o no pertenece al usuario: {message_id!r}")
        self.message_id = message_id


class MessageNotEligibleError(Exception):
    """Se intentó regenerar un mensaje que no es una respuesta del agente."""

    def __init__(self, message_id: uuid.UUID) -> None:
        super().__init__(f"solo se puede regenerar un mensaje de rol 'assistant': {message_id!r}")
        self.message_id = message_id


class ResponseGenerator(Protocol):
    """Callable inyectable que genera el texto de la respuesta del agente.

    Recibe la sesión (para leer su `model_profile` fijado por stickiness, tarea 1.1) y el
    historial completo de la rama sobre la que se genera la respuesta -- de raíz al
    último mensaje de usuario, inclusive. Devuelve únicamente el texto plano; el
    bookkeeping de ramas (`parent_id`, hermanos, `status`, `model_profile`) lo resuelve
    este módulo, no el generador.

    En esta tarea la generación es SÍNCRONA: la implementación real devuelve el texto
    completo de una sola vez (la tarea 1.5 introduce el streaming SSE, reemplazando este
    callable por una versión que emite fragmentos, sin cambiar `send_turn`/
    `regenerate_response`).
    """

    def __call__(self, *, session: SessionModel, history: list[Message]) -> str: ...


@dataclass(frozen=True)
class TurnResult:
    """Resultado de `send_turn`: los dos mensajes creados y el conteo de reproceso."""

    user_message: Message
    assistant_message: Message
    reprocessed_count: int


@dataclass(frozen=True)
class RegenerateResult:
    """Resultado de `regenerate_response`: el mensaje nuevo y su posición entre versiones."""

    message: Message
    version: int
    version_count: int


def _require_owned_session(db: DbSession, user: User, session_id: str) -> SessionModel:
    """Devuelve la sesión si pertenece a `user`; lanza `SessionNotFoundError` si no.

    Envoltorio fino sobre `find_owned_session` (compartido con `streaming.py` via
    `_branching.py`) que traduce el caso `None` a la excepción de dominio de este
    módulo.
    """
    session = find_owned_session(db, user, session_id)
    if session is None:
        raise SessionNotFoundError(session_id)
    return session


def send_turn(
    db: DbSession,
    user: User,
    session_id: str,
    text: str,
    generate_response: ResponseGenerator,
    edits_message_id: uuid.UUID | None = None,
) -> TurnResult:
    """Envía un turno nuevo o edita uno existente (mismo endpoint, tarea 1.2 / decisión 4).

    Turno normal (`edits_message_id` ausente): el mensaje de usuario cuelga del leaf de
    la rama activa (ver `find_active_leaf` en `_branching.py`).

    Edición (`edits_message_id` presente): crea un mensaje HERMANO bajo el mismo
    `parent_id` que el mensaje editado -- el original y todos sus descendientes quedan
    intactos y navegables, nunca se tocan ni se borran (append-only, regla del modelo de
    `b04`). Solo se puede editar un mensaje de rol `user` que pertenezca a esta misma
    sesión; cualquier otro caso lanza `MessageEditForbiddenError` sin crear ninguna fila.

    En ambos casos invoca `generate_response` para generar y persistir la respuesta del
    agente sobre el mensaje de usuario recién creado, y actualiza `last_activity_at` de la
    sesión. No hace `db.commit()` (misma convención que `create_session`).
    """
    session = _require_owned_session(db, user, session_id)

    reprocessed_count = 0
    if edits_message_id is not None:
        original = db.get(Message, edits_message_id)
        if original is None or original.session_id != session_id or original.role != "user":
            raise MessageEditForbiddenError(edits_message_id)
        parent_id = original.parent_id
        reprocessed_count = count_active_descendants(db, original.id)
    else:
        active_leaf = find_active_leaf(db, session_id)
        parent_id = active_leaf.id if active_leaf is not None else None

    user_message = Message(
        session_id=session_id,
        parent_id=parent_id,
        role="user",
        content=text,
        model_profile=session.model_profile,
    )
    db.add(user_message)
    db.flush()

    history = ancestor_chain(db, user_message)
    generation_started_at = time.monotonic()
    response_text = generate_response(session=session, history=history)
    latency_ms = round((time.monotonic() - generation_started_at) * 1000)

    assistant_message = Message(
        session_id=session_id,
        parent_id=user_message.id,
        role="assistant",
        content=response_text,
        model_profile=session.model_profile,
        status="complete",
        turn_metadata=dict(
            build_raw_turn_metadata(model_profile_id=session.model_profile, latency_ms=latency_ms)
        ),
    )
    db.add(assistant_message)
    db.flush()

    # Generación de título automático (tarea 2.2): si es el primer turno completo
    # de la sesión y el usuario no ha editado el título manualmente, genera uno
    # a partir del mensaje de usuario. Nunca se regenera si title_edited es True.
    if session.title is None and not session.title_edited:
        session.title = generate_session_title(user_message.content)

    session.last_activity_at = get_utc_now()

    return TurnResult(
        user_message=user_message,
        assistant_message=assistant_message,
        reprocessed_count=reprocessed_count,
    )


def regenerate_response(
    db: DbSession,
    user: User,
    message_id: uuid.UUID,
    generate_response: ResponseGenerator,
) -> RegenerateResult:
    """Regenera la respuesta del agente `message_id` (tarea 1.3).

    Crea un mensaje de agente HERMANO bajo el mismo `parent_id` (el mensaje de usuario
    que originó la respuesta), sin borrar ni modificar ninguna versión anterior
    (append-only). Solo aplica a mensajes de rol `assistant` (`MessageNotEligibleError` en
    cualquier otro caso); solo a sesiones propias del usuario actual, ownership derivada
    de la sesión del mensaje y nunca de un parámetro de la petición.
    """
    message = db.get(Message, message_id)
    if message is None:
        raise MessageNotFoundError(message_id)

    session = db.get(SessionModel, message.session_id)
    if session is None or session.owner_user_id != user.id:
        raise MessageNotFoundError(message_id)

    if message.role != "assistant":
        raise MessageNotEligibleError(message_id)

    parent_id = message.parent_id
    parent_message = db.get(Message, parent_id) if parent_id is not None else None
    history = ancestor_chain(db, parent_message) if parent_message is not None else []

    generation_started_at = time.monotonic()
    response_text = generate_response(session=session, history=history)
    latency_ms = round((time.monotonic() - generation_started_at) * 1000)

    new_message = Message(
        session_id=session.id,
        parent_id=parent_id,
        role="assistant",
        content=response_text,
        model_profile=session.model_profile,
        status="complete",
        turn_metadata=dict(
            build_raw_turn_metadata(model_profile_id=session.model_profile, latency_ms=latency_ms)
        ),
    )
    db.add(new_message)
    db.flush()

    session.last_activity_at = get_utc_now()

    siblings = (
        db.execute(
            select(Message)
            .where(Message.parent_id == parent_id, Message.role == "assistant")
            .order_by(Message.created_at.asc(), Message.id.asc())
        )
        .scalars()
        .all()
    )
    version_count = len(siblings)
    version = next(
        index + 1 for index, sibling in enumerate(siblings) if sibling.id == new_message.id
    )

    return RegenerateResult(message=new_message, version=version, version_count=version_count)
