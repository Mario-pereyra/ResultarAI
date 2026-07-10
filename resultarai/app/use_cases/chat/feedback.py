"""Caso de uso de chat: feedback 👍/👎 por respuesta, ligado a la traza (b07).

d13-chat-conversacion, tarea 1.8 -- endpoint exigido por el proposal (§What
Changes: "feedback 👍/👎 por respuesta ligado a la traza, `b07-observabilidad`") y
consumido por la tarea 3.6 de UI (popover de comentario, reemplazo de voto) y el
E2E 9.1. Reutiliza `resultarai.adapters.tracing_langfuse.feedback.submit_feedback`
(`response-feedback` spec de `b07`) vía un provider inyectable
(`FeedbackSubmitter`), mismo patrón "provider fail-loud" que `ResponseGenerator`/
`get_response_generator` (`turns.py`/`app/api/chat.py`): permite inyectar un doble
determinista en los tests sin depender del modo mock global de
`get_langfuse_client` para verificar llamadas.

**Reemplazo de voto -- desvío documentado sobre `chat-experience`
("Cambiar el voto reemplaza el anterior").** `submit_feedback` es, por diseño,
append-only: `tests/contracts/test_response_feedback.py::test_append_only_score_updates`
fija como contrato que dos llamadas sobre la misma traza producen DOS scores, sin
mutar el primero -- exactamente lo que exige `response-feedback` (b07), Requirement
"Retención permanente exenta de purgas": "una corrección se expresa como un score
nuevo, nunca como edición del existente". Este módulo NO intenta mutar ni deduplicar
nada en Langfuse (violaría ese contrato ya fijado y testeado). "Reemplazar" se
resuelve al nivel semántico, no de almacenamiento: cada voto -- incluido un cambio
de opinión -- se reenvía tal cual a `submit_feedback` como un score nuevo; el voto
VIGENTE de un usuario sobre un mensaje es, por definición, el último que se envió.
Se evaluó usar un `score_id` determinista (`user_id` + `message_id`) para lograr un
upsert real del lado de Langfuse -- el SDK de Langfuse sí soporta reemplazar un
score por `id`, pero solo si además coinciden `name` Y la fecha (granularidad de
día) del `timestamp` (verificado contra la documentación oficial de Langfuse,
"Update a score" / `create_score`); condicionar el reemplazo a "dentro del mismo
día" es fantasioso para un voto que puede cambiar semanas después, así que se
descartó. No se agrega una tabla propia en Postgres para "el voto vigente": el
sistema de registro es Langfuse (`response-feedback`: "El sistema SHALL persistir
el feedback como score en Langfuse"); una tabla espejo duplicaría esa fuente de
verdad sin que la tarea lo pida. Ver `openspec/BACKLOG-DESCUBRIMIENTOS.md` para la
limitación que esto abre (sin un `GET` que consulte "mi voto actual" agregando por
`trace_id`+`name`+fecha más reciente, la UI debe recordar localmente el último voto
emitido en la sesión del navegador).

**`trace_id` -- desvío documentado.** `response-feedback` exige que el feedback
quede ligado al `trace_id` del turno. Hoy ningún camino de persistencia de `d13`
(`turns.py` síncrono, `streaming.py` en SSE) escribe un `trace_id` real de Langfuse
en `Message.turn_metadata`: el runtime (`b06-runtime-grafos`) todavía no abre una
traza de Langfuse por turno, solo está fijado el contrato de observabilidad
(`AgentManifest.observability`). Mientras esa traza real no exista, se usa el
propio `id` del mensaje de agente evaluado como identificador estable ligado al
turno (`_resolve_trace_id` primero intenta `turn_metadata["trace_id"]`, para que el
día que `b06` lo complete este módulo lo recoja sin cambios). Ver
`openspec/BACKLOG-DESCUBRIMIENTOS.md`.

No vive en `core/` (regla dura 1): orquesta persistencia (SQLAlchemy) y un callable
de aplicación (el adapter de Langfuse), ninguno de los dos permitido dentro del
núcleo.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.orm import Session as DbSession

from resultarai.adapters.persistence_postgres.models import Message, User
from resultarai.adapters.persistence_postgres.models import Session as SessionModel

__all__ = [
    "FeedbackResult",
    "FeedbackSubmitter",
    "MessageNotEligibleForFeedbackError",
    "MessageNotFoundError",
    "submit_message_feedback",
]


class MessageNotFoundError(Exception):
    """El mensaje no existe o su sesión no pertenece al usuario actual.

    No distingue el motivo exacto (mismo criterio de no filtrar existencia de
    recursos ajenos que `turns.py`/`streaming.py`).
    """

    def __init__(self, message_id: uuid.UUID) -> None:
        super().__init__(f"mensaje no encontrado o no pertenece al usuario: {message_id!r}")
        self.message_id = message_id


class MessageNotEligibleForFeedbackError(Exception):
    """Solo se puede calificar un mensaje de rol `assistant` (una respuesta)."""

    def __init__(self, message_id: uuid.UUID) -> None:
        super().__init__(f"solo se puede calificar una respuesta del agente: {message_id!r}")
        self.message_id = message_id


class FeedbackSubmitter(Protocol):
    """Callable inyectable equivalente a `submit_feedback` de
    `tracing_langfuse.feedback` (mismo reparto de responsabilidades que
    `ResponseGenerator`): registra un score en Langfuse para `trace_id`, sin que
    este módulo conozca ningún detalle del cliente Langfuse.
    """

    def __call__(self, *, trace_id: str, value: int, comment: str | None) -> None: ...


@dataclass(frozen=True)
class FeedbackResult:
    """Resultado de `submit_message_feedback`: lo que la API necesita devolver."""

    message_id: uuid.UUID
    vote: str
    trace_id: str


def _resolve_trace_id(message: Message) -> str:
    """Deriva el `trace_id` a ligar (ver nota de módulo sobre el desvío)."""
    if message.turn_metadata:
        trace_id = message.turn_metadata.get("trace_id")
        if trace_id:
            return str(trace_id)
    return str(message.id)


def submit_message_feedback(
    db: DbSession,
    user: User,
    message_id: uuid.UUID,
    vote: str,
    comment: str | None,
    submit: FeedbackSubmitter,
) -> FeedbackResult:
    """Registra el voto `vote` (`"up"`/`"down"`, ya validado por la API) sobre
    `message_id`, ligado a su traza (ver `_resolve_trace_id`).

    Solo sobre mensajes de rol `assistant` de sesiones propias del usuario actual
    -- ownership derivada siempre de la sesión del mensaje, nunca de un parámetro
    de la petición (`MessageNotFoundError` -> 404 si el mensaje no existe o la
    sesión es ajena; `MessageNotEligibleForFeedbackError` -> 422 si no es una
    respuesta del agente). Votar de nuevo sobre el mismo mensaje reenvía un score
    nuevo (ver nota de módulo sobre "reemplazo").
    """
    message = db.get(Message, message_id)
    if message is None:
        raise MessageNotFoundError(message_id)

    session = db.get(SessionModel, message.session_id)
    if session is None or session.owner_user_id != user.id:
        raise MessageNotFoundError(message_id)

    if message.role != "assistant":
        raise MessageNotEligibleForFeedbackError(message_id)

    trace_id = _resolve_trace_id(message)
    value = 1 if vote == "up" else 0
    submit(trace_id=trace_id, value=value, comment=comment)

    return FeedbackResult(message_id=message.id, vote=vote, trace_id=trace_id)
