"""Caso de uso de chat en streaming: turno con fragmentos incrementales (SSE).

d13-chat-conversacion, tareas 1.4 y 1.5.

Este módulo NO reemplaza `turns.py` (tareas 1.2/1.3): `send_turn`/`regenerate_response`
siguen síncronos y siguen siendo los que usa `POST /sessions/{id}/messages` y
`POST /messages/{id}/regenerate`. Este módulo agrega un camino paralelo -- mismo
bookkeeping de ramas (reutilizado de `_branching.py`, no duplicado), pero generación
en streaming -- para el nuevo endpoint `POST /sessions/{id}/messages/stream`
(`resultarai/app/api/chat_stream.py`).

**Por qué un módulo nuevo y no evolucionar `ResponseGenerator` in-place:** `send_turn`/
`regenerate_response` reciben `ResponseGenerator.__call__(...) -> str` (texto completo,
síncrono) y ese contrato debía seguir intacto (tareas 1.2/1.3 ya tienen tests verdes que
no debían tocarse). `StreamingResponseGenerator` es un protocolo *nuevo*, no una versión
de `ResponseGenerator`: produce un iterador de `TurnFragment` terminado en exactamente un
`TurnCompletion` (nunca al revés). Se eligió esta forma -- en vez de que el generador
`return`e los metadatos al agotarse (`StopIteration.value`) -- porque tipar y testear un
valor de retorno de generador en modo estricto (`mypy --strict`) es mucho más frágil que
un `Iterator[TurnFragment | TurnCompletion]` con `isinstance` explícito.

**Tarea 1.4 -- traducción del marcador de escalación:** `filter_escalation_marker`
elimina el literal `<<<NEEDS_PRO>>>` de CUALQUIER fragmento de texto entregado al
cliente, bufferizando como máximo `len(marcador) - 1` caracteres en la frontera entre
fragmentos consecutivos (para no dejar pasar un marcador partido en dos). El marcador se
elimina del texto **siempre**, incluso con `escalation.enabled: false` en el Agent
Manifest -- ese es precisamente el requirement de `chat-streaming` ("el endpoint SHALL
NUNCA transmitir el texto literal... al cliente", sin excepción por agente) y es una capa
de defensa adicional sobre la de `escalation-marker` de `b05` (que si el agente tiene la
escalación deshabilitada, deja el marcador viajar en su propio contrato de salida
`LLMResponse.text` sin filtrarlo -- ver `resultarai/adapters/llm_litellm/client.py`). Lo
único que sí depende de `escalation.enabled` es si se emite el evento de dominio
`EscalationDetected`: deshabilitada -> ni evento ni marcador en el texto (texto se sigue
filtrando, pero no hay evento ni tarjeta de escalación).

**Reason del evento de escalación:** `design/VISTAS/02-chat.md` (vista 08) describe
`escalation.reason` como "1-2 líneas generadas por el agente antes del marcador". El
contrato de `b05` (`LLMResponse`) no expone hoy un campo de razón estructurado -- solo
`needs_pro: bool` --, así que esta capa aproxima el reason con el texto local disponible
en el momento de la detección (una ventana de los últimos caracteres ya emitidos, ver
`_REASON_WINDOW_CHARS`), con un texto genérico de reserva si no hay nada útil en esa
ventana. Ver nota en `openspec/BACKLOG-DESCUBRIMIENTOS.md`: cuando b05/b06 expongan un
campo de razón estructurado en el contrato de salida, esta heurística debe reemplazarse
por ese campo.

**Persistencia (tarea 1.5) -- DESVIACIÓN DESCUBIERTA sobre el riesgo mitigado de
`design.md`:** `design.md` propone persistir cada fragmento ya emitido con un `UPDATE`
incremental sobre el `content` del mensaje de agente, para que un reinicio del proceso
pierda como máximo el fragmento en vuelo. Al implementar esta tarea se descubrió que
`messages` es append-only a nivel de BASE DE DATOS -- no solo por convención de
aplicación --: la migración `28d73d938a65` (`create_conversation_persistence`, b04)
instala un trigger (`prevent_update_or_delete`) que rechaza CUALQUIER `UPDATE` o
`DELETE` sobre `messages` con una excepción de Postgres, sin excepciones por columna.
Un mensaje de agente "placeholder" creado vacío y completado después con `UPDATE` es
literalmente imposible contra este schema (se comprobó en rojo: el test de streaming
fallaba con `ProgrammingError: Table is append-only`).

Por eso este módulo SÍ persiste el mensaje de usuario de inmediato (commit temprano,
sobrevive un reinicio) pero ACUMULA el texto de la respuesta solo en memoria de proceso
mientras transmite los fragmentos al cliente por SSE; el mensaje de agente se inserta
con un único `INSERT` atómico -- contenido final, `turn_metadata` y `status` ya
completos -- recién al cerrar el turno (mismo patrón de una sola escritura que
`send_turn`/`regenerate_response`, solo que después de haber transmitido, no antes de
generar). El riesgo real, corregido: un reinicio a mitad de un turno en streaming pierde
la respuesta COMPLETA del agente (no solo el fragmento en vuelo) -- el usuario ve su
mensaje enviado (sí sobrevive) sin respuesta, y puede reintentar. Ver
`openspec/BACKLOG-DESCUBRIMIENTOS.md` para el hueco que esto abre (una futura tabla de
log de fragmentos, append-only de verdad, resolvería la mitigación original de
`design.md`, pero requiere una migración nueva -- fuera de alcance de d13, que declaró
cerradas sus migraciones en `28d73d938a65`/`ed42bef9dc34`).

No vive en `core/` (regla dura 1): orquesta persistencia (SQLAlchemy), Registries y un
callable de aplicación, ninguno de los tres permitido dentro del núcleo.

**Tarea 1.7 -- cancelación:** `_produce_turn_events` consulta `buffer.cancel_requested`
entre cada evento producido por `filter_escalation_marker` (que a su vez envuelve al
`StreamingResponseGenerator` inyectado). Al detectarla, deja de consumir el generador
(intenta cerrarlo explícitamente vía `close()` si lo expone, para propagar
`GeneratorExit` y que una implementación real basada en un stream HTTP/proceso pueda
liberar sus recursos) y persiste lo acumulado hasta ese punto como un único `INSERT`
con `status="stopped"` -- el mismo patrón de escritura atómica al cierre que ya usa el
camino normal, solo que sin esperar el `TurnCompletion` real (se sintetiza uno neutro,
igual que el fail-safe existente para un generador mal implementado que no cierra con
uno). El evento `done` gana el campo `stopped` (`True` en este camino, `False` en el
camino normal -- se agrega a AMBOS para no bifurcar el shape del evento entre los dos
casos, ver `app/api/chat_stream.py`).

**Tarea 4.1 -- capa de telemetría por rol:** `Message.turn_metadata` sigue
persistiéndose SIEMPRE completo (`_turn_metadata_dict`/`build_raw_turn_metadata`, ver
`telemetry.py`); lo que cambia es el evento `done` transmitido al cliente, que expone
`telemetry.layer_turn_metadata(metadata, role=user.role, ...)` en vez del dict crudo
-- para Funcional, sin la clave `telemetry` (ausente, no vacía); para Técnico/Admin,
con `telemetry.{cost_usd,model_profile_id,...}`; para Admin además con
`telemetry.trace_id`. Ver el contrato exacto documentado en el docstring de
`app/api/chat_stream.py`.
"""

from __future__ import annotations

import json
import time
import uuid
from collections.abc import Iterable, Iterator, Sequence
from dataclasses import dataclass
from typing import Protocol

from sqlalchemy.orm import Session as DbSession

from resultarai.adapters.persistence_postgres.models import Message, User, get_utc_now
from resultarai.adapters.persistence_postgres.models import Session as SessionModel
from resultarai.app.attachments.config import AttachmentsConfig
from resultarai.app.use_cases.chat._attachments import (
    ComposedMessage,
    compose_message_with_attachments,
    evaluate_quota_before_generation,
    persist_attachment_links,
)
from resultarai.app.use_cases.chat._branching import (
    ancestor_chain,
    count_active_descendants,
    find_active_leaf,
    find_owned_session,
)
from resultarai.app.use_cases.chat._marker import ESCALATION_MARKER, strip_escalation_marker
from resultarai.app.use_cases.chat.stream_registry import (
    BufferedSseEvent,
    TurnStreamBuffer,
    TurnStreamRegistry,
)
from resultarai.app.use_cases.chat.telemetry import build_raw_turn_metadata, layer_turn_metadata
from resultarai.app.use_cases.chat.titles import generate_session_title
from resultarai.app.use_cases.chat.turns import MessageEditForbiddenError, SessionNotFoundError
from resultarai.core.registries import Registries

__all__ = [
    "EscalationDetected",
    "EscalationPayload",
    "MessageEditForbiddenError",
    "SessionNotFoundError",
    "StreamingResponseGenerator",
    "TextFragment",
    "TurnAlreadyInProgressError",
    "TurnCompletion",
    "TurnFragment",
    "filter_escalation_marker",
    "start_turn_stream",
    "strip_escalation_marker",
]

# Reexportado desde `_marker.py` (módulo hoja compartido con turns.py).
_ESCALATION_MARKER = ESCALATION_MARKER
# Ventana de texto ya emitido que se recuerda solo para aproximar el `reason` del evento
# de escalación (ver docstring del módulo); no afecta qué se entrega como fragmentos.
_REASON_WINDOW_CHARS = 200
_DEFAULT_ESCALATION_REASON = (
    "El modelo indicó que esta consulta se resuelve mejor con un perfil de mayor "
    "capacidad de razonamiento."
)


@dataclass(frozen=True)
class TurnFragment:
    """Fragmento de texto crudo emitido por el `StreamingResponseGenerator`.

    "Crudo" porque todavía puede contener el marcador de escalación sin filtrar (o
    partido entre dos fragmentos consecutivos): `filter_escalation_marker` es quien lo
    convierte en `TextFragment`, seguro para entregar al cliente.
    """

    text: str


@dataclass(frozen=True)
class TurnCompletion:
    """Metadatos finales de un turno generado en streaming.

    Mismo shape que `LLMResponse` (`resultarai/core/ports/llm.py`), más `compacted` --
    que ese contrato del núcleo no expone todavía (`context-compaction` de `b06` es quien
    lo calcula; hasta que el runtime real se conecte a este seam, queda en `False` por
    defecto, ver nota de módulo). Se define aquí (no extendiendo `LLMResponse` de
    `core/`) para no tocar el núcleo con un campo no autorizado explícitamente por esta
    tarea.
    """

    model_profile_id: str
    is_alternate_model: bool
    primary_model_profile_id: str | None = None
    fallback_reason: str | None = None
    cache_hit_tokens: int | None = None
    cache_miss_tokens: int | None = None
    cost_usd: float | None = None
    needs_pro: bool = False
    compacted: bool = False


class StreamingResponseGenerator(Protocol):
    """Callable inyectable que genera la respuesta del agente en streaming.

    Análogo a `ResponseGenerator` (tareas 1.2/1.3) pero produce un iterador de
    `TurnFragment` terminado en exactamente un `TurnCompletion` como último elemento
    (nunca antes, nunca más de uno). El bookkeeping de ramas (`parent_id`, hermanos,
    `status`, `model_profile`) lo resuelve `start_turn_stream`, no el generador -- mismo
    reparto de responsabilidades que `ResponseGenerator`.
    """

    def __call__(
        self, *, session: SessionModel, history: list[Message]
    ) -> Iterator[TurnFragment | TurnCompletion]: ...


@dataclass(frozen=True)
class TextFragment:
    """Fragmento de texto ya filtrado: seguro para entregar al cliente como evento SSE."""

    text: str


@dataclass(frozen=True)
class EscalationDetected:
    """Señal interna: se detectó el marcador de escalación durante el filtrado."""

    reason: str


@dataclass(frozen=True)
class EscalationPayload:
    """Payload público del evento de dominio `escalation` (y del campo homónimo en `done`)."""

    reason: str
    target_profile: str | None


def _split_pending_suffix(buffer: str) -> tuple[str, str]:
    """Separa `buffer` en `(seguro_para_emitir, sufijo_retenido)`.

    El sufijo retenido es, como máximo, `len(marcador) - 1` caracteres: el prefijo más
    largo de `_ESCALATION_MARKER` con el que `buffer` podría estar terminando a mitad de
    frontera entre fragmentos. Si no hay ningún prefijo así, se retiene nada y se puede
    emitir `buffer` completo.
    """
    max_check = min(len(_ESCALATION_MARKER) - 1, len(buffer))
    for length in range(max_check, 0, -1):
        suffix = buffer[-length:]
        if _ESCALATION_MARKER.startswith(suffix):
            return buffer[:-length], suffix
    return buffer, ""


def filter_escalation_marker(
    events: Iterable[TurnFragment | TurnCompletion], *, escalation_enabled: bool
) -> Iterator[TextFragment | EscalationDetected | TurnCompletion]:
    """Filtra `<<<NEEDS_PRO>>>` de un stream de fragmentos (tarea 1.4).

    El marcador se elimina SIEMPRE del texto entregado (incluso con
    `escalation_enabled=False`, ver docstring del módulo); solo se emite
    `EscalationDetected` cuando `escalation_enabled` es `True`, y como máximo una vez por
    stream (ocurrencias posteriores del marcador -- atípico, el modelo normalmente
    detiene la generación tras emitirlo -- se siguen filtrando del texto sin emitir un
    segundo evento). El `TurnCompletion` final pasa sin tocar, siempre como último ítem.
    """
    pending = ""
    recent_emitted = ""
    already_escalated = False

    for event in events:
        if isinstance(event, TurnCompletion):
            if pending:
                yield TextFragment(pending)
            yield event
            return

        pending += event.text
        idx = pending.find(_ESCALATION_MARKER)
        found_now = idx != -1
        reason_text: str | None = None
        if found_now:
            reason_text = (recent_emitted + pending[:idx]).strip()
            pending = pending.replace(_ESCALATION_MARKER, "")

        safe, pending = _split_pending_suffix(pending)
        if safe:
            yield TextFragment(safe)
            recent_emitted = (recent_emitted + safe)[-_REASON_WINDOW_CHARS:]

        if found_now and escalation_enabled and not already_escalated:
            yield EscalationDetected(reason_text or _DEFAULT_ESCALATION_REASON)
            already_escalated = True

    if pending:
        yield TextFragment(pending)


def _turn_metadata_dict(
    completion: TurnCompletion, escalation: EscalationPayload | None, *, latency_ms: int
) -> dict[str, object]:
    """Construye el dict CRUDO que se persiste en `Message.turn_metadata` (tarea 4.1:
    delega en `build_raw_turn_metadata`, único constructor de este shape compartido con
    `turns.py`, ver `telemetry.py`).

    `latency_ms` -- tarea 4.1 -- se mide en `_produce_turn_events` desde que arranca a
    consumir el `StreamingResponseGenerator` hasta que el turno cierra (éxito o
    cancelación), ver docstring de esa función.
    """
    return dict(
        build_raw_turn_metadata(
            model_profile_id=completion.model_profile_id,
            is_alternate_model=completion.is_alternate_model,
            primary_model_profile_id=completion.primary_model_profile_id,
            fallback_reason=completion.fallback_reason,
            cache_hit_tokens=completion.cache_hit_tokens,
            cache_miss_tokens=completion.cache_miss_tokens,
            cost_usd=completion.cost_usd,
            latency_ms=latency_ms,
            compacted=completion.compacted,
            escalation=(
                {"reason": escalation.reason, "target_profile": escalation.target_profile}
                if escalation is not None
                else None
            ),
        )
    )


def _produce_turn_events(
    *,
    db: DbSession,
    session: SessionModel,
    session_id: str,
    user_message: Message,
    history: list[Message],
    generate_response: StreamingResponseGenerator,
    escalation_enabled: bool,
    target_profile: str | None,
    turn_id: str,
    buffer: TurnStreamBuffer,
    reprocessed_count: int,
    role: str,
    composed_message: ComposedMessage,
) -> Iterator[BufferedSseEvent]:
    """Genera la respuesta del agente y produce eventos SSE-ready, persistiéndola al final.

    Función perezosa (generador): no hace nada hasta que se empieza a consumir --
    `start_turn_stream` la construye pero devuelve el control a la API antes de invocar al
    generador real, para que el endpoint pueda abrir el `StreamingResponse` recién cuando
    empieza a iterarla.

    El texto de la respuesta se acumula SOLO en memoria mientras se transmiten los
    fragmentos; el `Message` del agente se inserta una única vez, completo, al cerrar el
    turno (ver la nota de módulo sobre por qué -- `messages` es append-only a nivel de
    base, un `UPDATE` incremental sobre una fila placeholder no es posible).

    Tarea 1.7: si `buffer.cancel_requested` se activa mientras se consumen los eventos
    (`POST /api/messages/{id}/cancel` o `/api/turns/{id}/cancel`, `chat_stream.py`), se
    deja de consumir el generador de inmediato -- ni un fragmento más se produce ni se
    persiste -- y el turno se cierra igual que el camino normal, con `status="stopped"`
    en vez de `"complete"` y `stopped=True` en el evento `done`.

    Tarea 4.1: `role` (el de la sesión de identidad que arrancó el turno,
    `start_turn_stream` lo deriva de `user.role`) decide qué capa de metadatos lleva el
    evento `done` -- ver `telemetry.layer_turn_metadata`. `latency_ms` se mide desde
    que arranca a consumirse `filtered` (inicio real de generación, no la mera
    construcción perezosa del iterador) hasta que el bucle termina (éxito o
    cancelación).
    """
    accumulated = ""
    escalation_payload: EscalationPayload | None = None
    completion: TurnCompletion | None = None
    stopped = False

    # Tarea 6.3 -- seam de cuota (`d16`, ver docstring de `evaluate_quota_before_generation`
    # en `_attachments.py`): corre DESPUES de componer el mensaje completo (adjuntos ya
    # resueltos en `composed_message`) y ANTES de invocar al generador real.
    evaluate_quota_before_generation(session=session, composed=composed_message)

    generation_started_at = time.monotonic()
    raw_events = generate_response(session=session, history=history)
    filtered = filter_escalation_marker(raw_events, escalation_enabled=escalation_enabled)
    for item in filtered:
        if buffer.cancel_requested:
            stopped = True
            break
        if isinstance(item, TextFragment):
            if not item.text:
                continue
            accumulated += item.text
            yield buffer.append("fragment", json.dumps({"text": item.text}))
        elif isinstance(item, EscalationDetected):
            escalation_payload = EscalationPayload(
                reason=item.reason, target_profile=target_profile
            )
            yield buffer.append(
                "escalation",
                json.dumps(
                    {
                        "reason": escalation_payload.reason,
                        "target_profile": escalation_payload.target_profile,
                    }
                ),
            )
        else:
            completion = item

    if stopped:
        # Se deja de invocar `next()` sobre el generador; si expone `close()` (protocolo
        # estándar de generadores de Python), se invoca para propagar `GeneratorExit` y
        # que una implementación real (stream HTTP/proceso hacia el runtime) pueda
        # liberar sus recursos en vez de quedar colgada esperando un consumidor que ya
        # no va a llegar.
        close = getattr(filtered, "close", None)
        if callable(close):
            close()

    if completion is None:
        # El protocolo de `StreamingResponseGenerator` garantiza un `TurnCompletion` como
        # último elemento; si un generador mal implementado no lo produce -- o si se
        # canceló antes de que llegara -- se sintetiza uno neutro para no dejar el turno
        # sin cerrar (fail-safe, no fail-silent: el `model_profile_id` heredado de la
        # sesión delata que no vino del generador real).
        completion = TurnCompletion(
            model_profile_id=session.model_profile, is_alternate_model=False
        )

    latency_ms = round((time.monotonic() - generation_started_at) * 1000)
    metadata = _turn_metadata_dict(completion, escalation_payload, latency_ms=latency_ms)

    # INSERT único y atómico (no un UPDATE sobre una fila creada antes): ver nota de
    # módulo, `messages` rechaza cualquier UPDATE por trigger de b04. También el camino
    # de cancelación pasa por aquí: si no hay texto acumulado, se inserta contenido
    # vacío igual con `status="stopped"`, para que el turno quede regenerable.
    assistant_message = Message(
        session_id=session_id,
        parent_id=user_message.id,
        role="assistant",
        content=accumulated,
        model_profile=session.model_profile,
        status="stopped" if stopped else "complete",
        turn_metadata=metadata,
    )
    db.add(assistant_message)

    # Generación de título automático (tarea 2.2): si es el primer turno completo
    # de la sesión y el usuario no ha editado el título manualmente, genera uno
    # a partir del mensaje de usuario. Nunca se regenera si title_edited es True.
    if session.title is None and not session.title_edited:
        session.title = generate_session_title(user_message.content)

    session.last_activity_at = get_utc_now()
    db.add(session)
    db.flush()
    db.commit()

    # Tarea 4.1: `turn_metadata` CRUDO (arriba) se persiste siempre completo -- lo que
    # viaja en el evento `done` es la vista FILTRADA por rol (`layer_turn_metadata`),
    # nunca el dict crudo. Ver el contrato documentado en el docstring de
    # `app/api/chat_stream.py`.
    layered = layer_turn_metadata(metadata, role=role, fallback_trace_id=str(assistant_message.id))
    done_payload: dict[str, object] = {
        "turn_id": turn_id,
        "user_message_id": str(user_message.id),
        "assistant_message_id": str(assistant_message.id),
        "reprocessed_count": reprocessed_count,
        "stopped": stopped,
        **layered,
    }
    yield buffer.append("done", json.dumps(done_payload))


class TurnAlreadyInProgressError(Exception):
    """Ya hay un turno en streaming EN CURSO sobre esta sesión (tarea 2.5).

    Decisión de diseño (garantía server-side de no-duplicación, complementaria a
    `in_progress_turn` en `get_session_detail`, `history.py`): solo puede haber UN
    turno en curso por sesión a la vez. Un segundo intento de arrancar un turno --
    p. ej. un "reenviar" accidental desde otra pestaña/dispositivo que todavía no vio
    el turno vivo en el detalle de sesión -- se rechaza en vez de arrancar un segundo
    streaming concurrente sobre la misma rama, que produciría dos mensajes de agente
    compitiendo por el mismo `parent_id` (dos hijos del mismo mensaje de usuario, sin
    que ninguno de los dos sea una edición ni una regeneración intencional). `turn_id`
    es el del turno vivo, para que quien recibe el error se re-attachee a
    `GET /api/turns/{turn_id}/stream` (tarea 1.6) en vez de reintentar el envío.
    """

    def __init__(self, turn_id: str) -> None:
        super().__init__(f"Ya hay un turno en curso para esta sesión: {turn_id}")
        self.turn_id = turn_id


def start_turn_stream(
    db: DbSession,
    registries: Registries,
    turn_stream_registry: TurnStreamRegistry,
    user: User,
    session_id: str,
    text: str,
    generate_response: StreamingResponseGenerator,
    edits_message_id: uuid.UUID | None = None,
    *,
    attachment_ids: Sequence[uuid.UUID] | None = None,
    attachments_config: AttachmentsConfig | None = None,
) -> tuple[str, Iterator[BufferedSseEvent]]:
    """Arranca un turno en streaming (tarea 1.5): valida, encadena y devuelve el stream.

    La resolución de ownership/edición y la creación del mensaje de usuario son
    SÍNCRONAS (corren antes de devolver nada): así la API puede traducir
    `SessionNotFoundError`/`MessageEditForbiddenError`/`TurnAlreadyInProgressError` a
    HTTP 404/403/409 *antes* de abrir la respuesta `text/event-stream` (una vez
    abierta, ya no se puede cambiar el status code). Devuelve
    `(turn_id, iterador_de_eventos)`: el iterador es perezoso -- invoca al
    `StreamingResponseGenerator` real y persiste recién cuando se empieza a consumir
    (ver `_produce_turn_events`).

    El buffer del turno queda registrado con `owner_user_id=user.id`,
    `user_message_id=user_message.id` y `session_id=session_id` (tareas 1.6/1.7/2.5)
    ANTES de devolver el control: la API puede resolver
    `GET /api/turns/{turn_id}/stream` (reconexión) y `POST /api/messages/{id}/cancel` /
    `POST /api/turns/{id}/cancel` (cancelación) sobre este mismo buffer sin ninguna
    carrera posible con su creación.

    Tarea 2.5 -- un solo turno en curso por sesión: se verifica ANTES de crear
    ninguna fila (ni el mensaje de usuario nuevo), así que un intento rechazado no deja
    ningún rastro en la base -- ver `TurnAlreadyInProgressError`.

    **Tarea 6.3 -- adjuntos:** mismo contrato aditivo que `turns.py::send_turn`:
    `attachment_ids` es opcional (default `None`/vacío, comportamiento IDÉNTICO al de
    antes de d14). Con `attachment_ids` no vacío, `attachments_config` es obligatorio
    (`ValueError` si falta -- `registries` ya era un parámetro requerido de este
    endpoint, se reutiliza para resolver el tokenizer del `model_profile` de la sesión).
    El contenido compuesto (texto + adjuntos envueltos AL FINAL) reemplaza a `text` como
    `Message.content`, y las filas de `message_attachments` se persisten en la MISMA
    transacción que el mensaje de usuario (antes del `commit()` de abajo, atómico).
    """
    session = find_owned_session(db, user, session_id)
    if session is None:
        raise SessionNotFoundError(session_id)

    existing_turn = turn_stream_registry.get_open_by_session_id(session_id)
    if existing_turn is not None:
        raise TurnAlreadyInProgressError(existing_turn.turn_id)

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

    composed = ComposedMessage(content=text, links=[], total_attachment_tokens=0)
    if attachment_ids:
        if attachments_config is None:
            raise ValueError(
                "start_turn_stream: attachment_ids requiere 'attachments_config' (ver "
                "app/api/chat_stream.py: get_attachments_config)."
            )
        composed = compose_message_with_attachments(
            db, registries, attachments_config, user, session, text, attachment_ids
        )

    user_message = Message(
        session_id=session_id,
        parent_id=parent_id,
        role="user",
        content=composed.content,
        model_profile=session.model_profile,
    )
    db.add(user_message)
    db.flush()

    if composed.links:
        persist_attachment_links(db, user_message.id, composed)

    db.commit()

    history = ancestor_chain(db, user_message)

    agent = registries.agents.get_invocable(session.agent_id) if session.agent_id else None
    escalation_enabled = agent.escalation.enabled if agent is not None else False
    target_profile = agent.escalation.target_profile if agent is not None else None

    turn_id = f"turn_{uuid.uuid4().hex}"
    buffer = turn_stream_registry.create(
        turn_id,
        owner_user_id=user.id,
        user_message_id=user_message.id,
        session_id=session_id,
    )

    events = _produce_turn_events(
        db=db,
        session=session,
        session_id=session_id,
        user_message=user_message,
        history=history,
        generate_response=generate_response,
        escalation_enabled=escalation_enabled,
        target_profile=target_profile,
        turn_id=turn_id,
        buffer=buffer,
        reprocessed_count=reprocessed_count,
        role=user.role,
        composed_message=composed,
    )
    return turn_id, events
