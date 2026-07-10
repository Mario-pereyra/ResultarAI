"""Casos de uso de chat: listado, detalle y búsqueda del historial de sesiones.

d13-chat-conversacion, tareas 2.1 (`GET /sessions`), 2.3 (`GET /sessions/{id}`) y 2.4
(`GET /sessions/search`). Las tres consultas comparten una misma regla de ownership
(`find_owned_session`/`SessionModel.owner_user_id == user.id`, `_branching.py`): el
`userId` se deriva siempre de la sesión de identidad inyectada, nunca de un
parámetro de la petición.

**`branch_count` (indicador de ramas, requirement "Indicador de ramas por sesión"):**
cuenta los PUNTOS DE BIFURCACIÓN de la sesión -- valores de `parent_id` con más de un
mensaje que los referencia, incluida la raíz virtual `parent_id IS NULL` cuando el
PRIMER mensaje de la sesión fue editado -- no la cantidad de ramas ni de mensajes en
ramas descartadas. Una edición o una regeneración crean exactamente un punto de
bifurcación cada una (el mensaje editado/regenerado, o la raíz de la sesión, pasa a
tener ≥2 mensajes que lo referencian como `parent_id`). Una sesión sin ediciones ni
regeneraciones es puramente lineal: `branch_count == 0`. Se calcula con una consulta
agregada por sesión (`_branch_counts`), sin cargar los mensajes completos --
necesario porque el listado (tarea 2.1) no debe pagar el costo de traer el árbol
entero de cada sesión solo para contar bifurcaciones.

**Búsqueda (tarea 2.4):** server-side con `ILIKE` sobre `Session.title` y
`Message.content`, escapando `%`/`_` del término (`_escape_like_term`) para que un
término con esos caracteres se busque literal, no como comodín de SQL. Se eligió
`ILIKE` sobre `plainto_tsquery`/`tsvector` por ser suficiente para el volumen y la
UX esperada (subcadena case-insensitive, sin necesidad de stemming ni ranking por
relevancia) y no requerir una columna/índice `tsvector` ni una migración nueva; si el
volumen de mensajes crece lo suficiente para que el costo de un `ILIKE '%term%'` sin
índice de prefijo sea un problema, ese es el momento de migrar a full-text search
(anotado en `openspec/BACKLOG-DESCUBRIMIENTOS.md`). Cada resultado expone un
`snippet` (fragmento alrededor de la primera aparición del término, con elipsis en
los bordes truncados) y `match_start`/`match_end` -- offsets del término DENTRO del
snippet, no del texto completo -- para que la UI resalte el término sin tener que
volver a buscarlo del lado del cliente.

**Reanudar sesión / reconciliación (tarea 2.5, requirement "Reanudar sesión en su
última rama activa"):** `get_session_detail` acepta opcionalmente el
`TurnStreamRegistry` de proceso (`app/use_cases/chat/stream_registry.py`) para
detectar si hay un turno EN CURSO (streaming, todavía sin mensaje de agente
persistido) sobre esta sesión -- típicamente arrancado desde otra pestaña o
dispositivo -- y exponerlo como `in_progress_turn`. Sin ese turno vivo, el detalle ya
alcanza (árbol persistido + `active_leaf_id`) para "reanudar en la última rama
activa"; con él, el cliente que reanuda sabe que debe re-attachearse a
`GET /api/turns/{turn_id}/stream` (tarea 1.6) en vez de reenviar el mismo mensaje de
usuario -- que ya está persistido, solo falta la respuesta -- y así nunca se muestra
ni se crea un turno duplicado. El parámetro es opcional (`None` por defecto) para que
`get_session_detail` siga siendo invocable sin conocer ningún registro de streaming
cuando eso no aplica (p. ej. un futuro caller batch/administrativo); el único caller
de producción hoy (`app/api/chat.py`, `get_session_detail_endpoint`) siempre lo pasa.

No vive en `core/` (regla dura 1): orquesta persistencia (SQLAlchemy), ninguno de
los dos permitido dentro del núcleo.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Literal

from sqlalchemy import func, select
from sqlalchemy.orm import Session as DbSession

from resultarai.adapters.persistence_postgres.models import Message, User
from resultarai.adapters.persistence_postgres.models import Session as SessionModel
from resultarai.app.use_cases.chat._branching import find_active_leaf, find_owned_session
from resultarai.app.use_cases.chat.stream_registry import TurnStreamRegistry
from resultarai.app.use_cases.chat.turns import SessionNotFoundError

__all__ = [
    "InProgressTurn",
    "SearchHit",
    "SessionDetail",
    "SessionNotFoundError",
    "SessionSummary",
    "get_session_detail",
    "list_sessions",
    "search_sessions",
]

# Ancho (en caracteres) a cada lado del término encontrado que arma el `snippet` de
# búsqueda (tarea 2.4).
_SNIPPET_WINDOW = 40


@dataclass(frozen=True)
class SessionSummary:
    """Una fila del listado de sesiones propias (tarea 2.1): la sesión más sus
    contadores agregados (`message_count`, `branch_count`).
    """

    session: SessionModel
    message_count: int
    branch_count: int


@dataclass(frozen=True)
class InProgressTurn:
    """Turno en streaming EN CURSO sobre la sesión, visto desde otra pestaña o
    dispositivo (tarea 2.5).

    `user_message_id` ya está persistido (siempre, desde el arranque del turno en
    streaming, ver `streaming.py`); `turn_id` es el identificador con el que
    re-attachearse a `GET /api/turns/{turn_id}/stream` (tarea 1.6). `last_event_id` es
    el `id` del último evento SSE ya bufferizado para ese turno (0 si todavía no se
    emitió ninguno) -- útil como `Last-Event-ID` de arranque de esa reconexión, aunque
    no es obligatorio usarlo así (reconectar con `0` igual reproduce el turno
    completo).
    """

    turn_id: str
    user_message_id: uuid.UUID
    last_event_id: int


@dataclass(frozen=True)
class SessionDetail:
    """El árbol completo de una sesión (tarea 2.3): todos los mensajes de todas las
    ramas (activas y descartadas), más los metadatos que la UI necesita para la
    nota-enlace bidireccional de escalación, el selector de versiones y la
    reconciliación de un turno en streaming visto desde otra pestaña (tarea 2.5,
    `in_progress_turn`).
    """

    session: SessionModel
    messages: list[Message]
    active_leaf_id: uuid.UUID | None
    escalated_session_ids: list[str]
    in_progress_turn: InProgressTurn | None


@dataclass(frozen=True)
class SearchHit:
    """Una coincidencia de búsqueda (tarea 2.4): la sesión más dónde matcheó el
    término (`match_type`) y el fragmento que lo identifica (`snippet` +
    `match_start`/`match_end`, offsets relativos al propio `snippet`).
    """

    session: SessionModel
    match_type: Literal["title", "message"]
    message_id: uuid.UUID | None
    snippet: str
    match_start: int
    match_end: int


def _message_counts(db: DbSession, session_ids: list[str]) -> dict[str, int]:
    """Cuenta mensajes por sesión con una única consulta agregada."""
    if not session_ids:
        return {}
    rows = (
        db.execute(
            select(Message.session_id, func.count(Message.id))
            .where(Message.session_id.in_(session_ids))
            .group_by(Message.session_id)
        )
        .tuples()
        .all()
    )
    return dict(rows)


def _branch_counts(db: DbSession, session_ids: list[str]) -> dict[str, int]:
    """Cuenta puntos de bifurcación por sesión (ver docstring de módulo).

    Dos consultas agregadas (independientes de la cantidad de sesiones): primero los
    `parent_id` con más de un hijo agrupados por sesión, luego cuántos de esos
    `parent_id` tiene cada sesión. Ninguna de las dos carga los mensajes completos.

    Deliberadamente NO excluye `parent_id IS NULL`: Postgres agrupa todos los NULL de
    un `GROUP BY` en un único grupo, así que también cuenta como bifurcación el caso
    de editar el PRIMER mensaje de la sesión (dos mensajes raíz, ambos con
    `parent_id is None`) -- si se excluyera, ese fork quedaría sin contar porque no
    hay ningún mensaje "padre" real que tenga más de un hijo, solo la raíz virtual de
    la sesión.
    """
    if not session_ids:
        return {}
    fork_points = (
        select(Message.session_id, Message.parent_id)
        .where(Message.session_id.in_(session_ids))
        .group_by(Message.session_id, Message.parent_id)
        .having(func.count(Message.id) > 1)
        .subquery()
    )
    rows = (
        db.execute(
            select(fork_points.c.session_id, func.count()).group_by(fork_points.c.session_id)
        )
        .tuples()
        .all()
    )
    return dict(rows)


def list_sessions(
    db: DbSession, user: User, limit: int = 25, offset: int = 0
) -> list[SessionSummary]:
    """Lista las sesiones propias de `user`, más recientes primero (tarea 2.1).

    El `userId` se deriva exclusivamente de `user` (la sesión de identidad
    inyectada por `get_current_user`), nunca de un parámetro -- el listado de un
    usuario nunca puede incluir sesiones de otro. Orden por última actividad
    descendente (`last_activity_at`, con `created_at` como respaldo para las filas
    heredadas de `b04` que no la tengan poblada).
    """
    order_key = func.coalesce(SessionModel.last_activity_at, SessionModel.created_at)
    sessions = (
        db.execute(
            select(SessionModel)
            .where(SessionModel.owner_user_id == user.id)
            .order_by(order_key.desc(), SessionModel.id.desc())
            .limit(limit)
            .offset(offset)
        )
        .scalars()
        .all()
    )

    session_ids = [session.id for session in sessions]
    message_counts = _message_counts(db, session_ids)
    branch_counts = _branch_counts(db, session_ids)

    return [
        SessionSummary(
            session=session,
            message_count=message_counts.get(session.id, 0),
            branch_count=branch_counts.get(session.id, 0),
        )
        for session in sessions
    ]


def get_session_detail(
    db: DbSession,
    user: User,
    session_id: str,
    turn_stream_registry: TurnStreamRegistry | None = None,
) -> SessionDetail:
    """Devuelve el árbol completo de mensajes de `session_id` (tarea 2.3).

    Sesión ajena o inexistente: `SessionNotFoundError` (la API lo traduce a 404 sin
    filtrar cuál de los dos motivos aplica, mismo criterio que `turns.py`). Incluye
    TODOS los mensajes de la sesión -- ramas activas y descartadas por igual, sin
    ocultar ninguna -- y `active_leaf_id` (ver `find_active_leaf`, `_branching.py`)
    para que la UI sepa en qué hoja "reanudar".

    Tarea 2.5: con `turn_stream_registry`, además busca un turno EN CURSO sobre esta
    sesión (ver docstring de módulo) y lo expone como `in_progress_turn` -- `None` si
    no hay ninguno, o si no se pasó ningún registro. El mensaje de usuario de ese
    turno ya aparece en `messages` (se persiste al arrancar el turno, antes de generar
    la respuesta); lo único que falta es el mensaje de agente, todavía en memoria del
    buffer, no en la base -- por eso NO se sintetiza ningún mensaje "en progreso" en
    `messages`, la UI lo resuelve reconectándose al stream real.
    """
    session = find_owned_session(db, user, session_id)
    if session is None:
        raise SessionNotFoundError(session_id)

    messages = (
        db.execute(
            select(Message)
            .where(Message.session_id == session_id)
            .order_by(Message.created_at.asc(), Message.id.asc())
        )
        .scalars()
        .all()
    )

    active_leaf = find_active_leaf(db, session_id)

    escalated_session_ids = (
        db.execute(select(SessionModel.id).where(SessionModel.forked_from_id == session_id))
        .scalars()
        .all()
    )

    in_progress_turn: InProgressTurn | None = None
    if turn_stream_registry is not None:
        live_buffer = turn_stream_registry.get_open_by_session_id(session_id)
        if live_buffer is not None:
            in_progress_turn = InProgressTurn(
                turn_id=live_buffer.turn_id,
                user_message_id=live_buffer.user_message_id,
                last_event_id=len(live_buffer.events_after(0)),
            )

    return SessionDetail(
        session=session,
        messages=list(messages),
        active_leaf_id=active_leaf.id if active_leaf is not None else None,
        escalated_session_ids=list(escalated_session_ids),
        in_progress_turn=in_progress_turn,
    )


def _escape_like_term(term: str) -> str:
    """Escapa `\\`, `%` y `_` de `term` y lo envuelve en comodines de `ILIKE`.

    Sin este escape, un término de búsqueda que contenga `%` o `_` literal se
    interpretaría como comodín de SQL en vez de caracter literal (tarea 2.4: "término
    con `%` no rompe").
    """
    escaped = term.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _build_snippet(text: str, term: str, window: int = _SNIPPET_WINDOW) -> tuple[str, int, int]:
    """Recorta `text` alrededor de la primera aparición case-insensitive de `term`.

    Devuelve `(snippet, match_start, match_end)` con los offsets del término
    RELATIVOS al `snippet` devuelto (no al texto completo), contemplando la elipsis
    (`…`) que se antepone/agrega cuando el snippet no arranca/termina en el texto
    original.
    """
    lower_text = text.lower()
    lower_term = term.lower()
    index = lower_text.find(lower_term)
    if index == -1:
        # No debería pasar: el texto ya vino filtrado por ILIKE con el mismo
        # término. Se devuelve un fragmento sin marca como resguardo defensivo.
        snippet = text[: window * 2]
        return snippet, 0, 0

    start = max(0, index - window)
    end = min(len(text), index + len(term) + window)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    snippet = f"{prefix}{text[start:end]}{suffix}"

    match_start = len(prefix) + (index - start)
    match_end = match_start + len(term)
    return snippet, match_start, match_end


def search_sessions(
    db: DbSession, user: User, term: str, limit: int = 25, offset: int = 0
) -> list[SearchHit]:
    """Busca `term` en el título y el contenido de mensajes de las sesiones propias
    de `user` (tarea 2.4).

    Una sesión aparece UNA sola vez en el resultado aunque matchee por título y por
    varios mensajes: se prioriza el match de título (más barato de mostrar) y, si no
    hay, el primer mensaje que matchea por orden cronológico (`created_at` asc).
    Ordena por última actividad descendente, igual que `list_sessions`. Término
    ausente en todas las sesiones propias: lista vacía, sin lanzar ningún error.
    """
    pattern = _escape_like_term(term)

    title_sessions = (
        db.execute(
            select(SessionModel).where(
                SessionModel.owner_user_id == user.id,
                SessionModel.title.isnot(None),
                SessionModel.title.ilike(pattern, escape="\\"),
            )
        )
        .scalars()
        .all()
    )
    title_hits: dict[str, SearchHit] = {}
    for session in title_sessions:
        assert session.title is not None  # narrowed por el filtro `isnot(None)` de arriba
        snippet, match_start, match_end = _build_snippet(session.title, term)
        title_hits[session.id] = SearchHit(
            session=session,
            match_type="title",
            message_id=None,
            snippet=snippet,
            match_start=match_start,
            match_end=match_end,
        )

    message_rows = db.execute(
        select(Message, SessionModel)
        .join(SessionModel, Message.session_id == SessionModel.id)
        .where(
            SessionModel.owner_user_id == user.id,
            Message.content.ilike(pattern, escape="\\"),
        )
        .order_by(Message.session_id, Message.created_at.asc(), Message.id.asc())
    ).all()

    message_hits: dict[str, SearchHit] = {}
    for message, session in message_rows:
        if session.id in message_hits:
            continue  # ya se tomó el primer mensaje que matchea de esta sesión
        snippet, match_start, match_end = _build_snippet(message.content, term)
        message_hits[session.id] = SearchHit(
            session=session,
            match_type="message",
            message_id=message.id,
            snippet=snippet,
            match_start=match_start,
            match_end=match_end,
        )

    combined: dict[str, SearchHit] = {**message_hits, **title_hits}  # el título prioriza

    order_key = func.coalesce(SessionModel.last_activity_at, SessionModel.created_at)
    ordered_ids = (
        db.execute(
            select(SessionModel.id)
            .where(SessionModel.id.in_(combined.keys()))
            .order_by(order_key.desc(), SessionModel.id.desc())
        )
        .scalars()
        .all()
        if combined
        else []
    )

    ordered_hits = [combined[session_id] for session_id in ordered_ids]
    return ordered_hits[offset : offset + limit]
