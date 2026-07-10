"""FastAPI router para el streaming SSE de turnos, su reconexión y su cancelación.

d13-chat-conversacion, tareas 1.5, 1.6 y 1.7. Complementa (no reemplaza)
`resultarai/app/api/chat.py`: el endpoint no-streaming (`POST /sessions/{id}/messages`,
tarea 1.2) sigue existiendo para quien no consuma SSE; este es el camino que usará la UI
del chat (vista 05).

**Contrato SSE del turno (tarea 1.5):**

- Ruta: `POST /api/sessions/{session_id}/messages/stream`. Mismo payload que el endpoint
  no-streaming (`{"text": str, "edits_message_id": str | None}`): turno normal o edición,
  distinguidos por `edits_message_id` (decisión 4 de `design.md`).
- Respuesta: `text/event-stream`, un frame SSE por evento (`id:`, `event:`, `data:`,
  línea en blanco) más comentarios `: heartbeat` periódicos (sin `id` ni `event`: un
  comentario de protocolo, invisible para `EventSource.onmessage`, ver decisión 3 de
  `design.md`).
- Headers de respuesta: `X-Turn-Id` (identificador del turno) y `X-User-Message-Id`
  (identificador del mensaje de usuario recién creado) -- **este es el mecanismo exacto
  por el que el cliente descubre ambos identificadores tempranamente** (disponibles ni
  bien abre la conexión, sin esperar ningún evento): los necesita para reconectar
  (tarea 1.6, `turn_id`) y para cancelar (tarea 1.7, cualquiera de los dos).
- `id` es un entero incremental por turno (arranca en 1), asignado por el
  `TurnStreamBuffer` del turno (`app/use_cases/chat/stream_registry.py`) -- la
  reconexión lo reutiliza para el replay por `Last-Event-ID`.
- Eventos de dominio, en este orden: `fragment`* (cero o más) -> `escalation`? (cero o
  una vez) -> `done` (exactamente una vez, cierra el stream).
  - `fragment`: `data` = `{"text": str}` -- un fragmento incremental de texto, ya
    filtrado del marcador de escalación (tarea 1.4).
  - `escalation`: `data` = `{"reason": str, "target_profile": str | null}` -- solo si el
    Agent Manifest de la sesión tiene `escalation.enabled: true` y el modelo emitió el
    marcador; `target_profile` es `escalation.target_profile` del Agent Manifest.
  - `done`: `data` = metadatos del turno, filtrados por el ROL de la sesión de
    identidad que abrió la conexión (tarea 4.1, requirement `chat-experience` "Capa
    de telemetría por turno para Técnico/Admin" -- ver `telemetry.py`) --
    `{"turn_id": str, "user_message_id": str, "assistant_message_id": str,
    "reprocessed_count": int, "stopped": bool, "is_alternate_model": bool,
    "compacted": bool, "escalation": {"reason": str, "target_profile": str | null} |
    null, "telemetry": {...} }`. `turn_id`/`user_message_id`/`assistant_message_id`/
    `reprocessed_count`/`stopped`/`is_alternate_model`/`compacted`/`escalation`
    viajan SIEMPRE, para los tres roles (`is_alternate_model` es la etiqueta "modelo
    alterno" de la tarea 5.1, visible para todos). `stopped` es `true` únicamente
    cuando el turno cerró por cancelación (tarea 1.7); el shape es el MISMO en ambos
    casos (se agregó el campo, no se bifurcó el evento).
    - `telemetry` -- SOLO Técnico/Admin. Para Funcional la clave `telemetry` está
      AUSENTE del JSON (ni `null` ni `{}`: decisión 7 de `design.md`, el backend no
      confía en el cliente para ocultarla). Shape: `{"cost_usd": float | null,
      "model_profile_id": str | null, "primary_model_profile_id": str | null,
      "fallback_reason": str | null, "latency_ms": int | null, "cache_hit_tokens":
      int | null, "cache_miss_tokens": int | null, "cache_write_tokens": null}` --
      `cache_write_tokens` siempre `null` hasta que `LLMResponse` de
      `b05-gateway-modelos` lo exponga (ver `openspec/BACKLOG-DESCUBRIMIENTOS.md`).
      Para Admin, `telemetry` gana además `"trace_id": str` (enlace "ver traza" de
      la tarea 4.3).
- Nunca aparece el texto literal `<<<NEEDS_PRO>>>` en ningún `data` de ningún evento
  (tarea 1.4, defensa incondicional, ver `streaming.py`).
- El intervalo de heartbeat es configurable vía la variable de entorno
  `RESULTARAI_SSE_HEARTBEAT_INTERVAL_SECONDS` (segundos, float; default 15). Los tests
  la fijan baja para observar al menos un heartbeat sin esperar minutos reales.

**Transporte:** este POST no es compatible con `EventSource` nativo del navegador (no
soporta método/body en el request inicial) -- la UI debe consumirlo con `fetch()` +
`ReadableStream` (mismo patrón que Vercel AI SDK/assistant-ui).

**Reconexión (tarea 1.6) -- `GET /api/turns/{turn_id}/stream`:**

- Sí es compatible con `EventSource` nativo (método GET, sin body): el cliente puede usar
  `new EventSource(url)` directamente, que reenvía `Last-Event-ID` automáticamente en
  reconexiones. Para clientes que no usan `EventSource` (p. ej. si la UI sigue con
  `fetch()`/`ReadableStream` por consistencia con el POST), el mismo dato se acepta por
  query param `?last_event_id=`; si ambos vienen, el header `Last-Event-ID` gana.
  Sin ninguno de los dos, se asume `0` (reproduce el turno completo desde el principio).
- Ownership: el `turn_id` debe pertenecer a una sesión de un turno arrancado por el
  usuario autenticado actual (comparado contra `TurnStreamBuffer.owner_user_id`, NUNCA
  contra un parámetro de la petición). Si el turno no existe o es de otro usuario: 404
  (mismo criterio de no distinguir el motivo que el resto de la API de chat).
  `Last-Event-ID` sintácticamente inválido (no entero): 400.
- Reproduce (replay, sin invocar de nuevo a ningún `StreamingResponseGenerator`) los
  eventos ya bufferizados con `id > Last-Event-ID`, y continúa en vivo -- observando el
  mismo `TurnStreamBuffer` que sigue llenando la conexión original -- hasta el `done`,
  emitiendo heartbeats propios mientras tanto. Si el turno ya cerró, reproduce lo que
  falte (si `Last-Event-ID` ya cubre todo, solo el `done`) y cierra de inmediato.
- Misma respuesta `text/event-stream` que el POST (mismo `id`/`event`/`data`, mismo
  `X-Turn-Id` de respuesta); no repite `X-User-Message-Id` porque no siempre se conoce
  sin ir a buscarlo (no es necesario para reconectar).

**Cancelación (tarea 1.7):**

- `POST /api/turns/{turn_id}/cancel` y `POST /api/messages/{message_id}/cancel` --
  **ambos** disponibles: la tarea nombra el segundo, pero en el momento de cancelar el
  mensaje de agente puede no existir todavía como fila (se inserta recién al cerrar el
  turno, ver `streaming.py`), así que `message_id` se resuelve como el mensaje de
  USUARIO del turno (existe desde el arranque, ver `X-User-Message-Id` arriba) -- nunca
  el de agente. Ambas rutas terminan en la misma lógica de cancelación.
- Ownership: mismo criterio que la reconexión (`owner_user_id` del buffer). Turno
  inexistente o ajeno: 404.
- Turno ya cerrado (normal o cancelado antes): 409 -- la cancelación no es una consulta
  idempotente de estado, es una acción que solo tiene sentido sobre un turno en curso.
- Señala la cancelación (`TurnStreamBuffer.request_cancel`) y espera (acotado por
  `RESULTARAI_CANCEL_WAIT_TIMEOUT_SECONDS`, default 10 s) a que el productor del turno
  -- que corre en el hilo de la conexión SSE original, no en este request -- termine de
  persistir el mensaje parcial y cierre el buffer, antes de responder. Devuelve
  `{"turn_id": str, "user_message_id": str, "assistant_message_id": str, "status":
  "stopped"}`. Si el productor no cierra a tiempo (raro: implica que ni siquiera notó la
  señal), responde 504 -- la cancelación ya quedó señalada igual, el cliente puede
  reintentar o simplemente esperar el `done` en el stream.
- El stream original (`POST /sessions/{id}/messages/stream`, o su reconexión) recibe el
  mismo `done` de siempre con `stopped: true`, sin ningún evento de error de protocolo.
"""

from __future__ import annotations

import json
import os
import queue
import threading
import time
import uuid
from collections.abc import Iterator
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session as DbSession

from resultarai.adapters.persistence_postgres.models import User
from resultarai.app.api.chat import SendMessageRequest, get_registries

# Re-exportado explícitamente (alias redundante `as`): `app/api/__init__.py` y los
# tests de streaming siguen importando `get_turn_stream_registry` DESDE este módulo
# (ver la nota debajo), y mypy --strict exige la forma `import X as X` para que un
# nombre importado cuente como parte de la API pública re-exportada del módulo.
from resultarai.app.api.chat import get_turn_stream_registry as get_turn_stream_registry
from resultarai.app.identity import get_current_user, get_db
from resultarai.app.use_cases.chat.stream_registry import (
    BufferedSseEvent,
    TurnStreamBuffer,
    TurnStreamRegistry,
)
from resultarai.app.use_cases.chat.streaming import (
    MessageEditForbiddenError,
    SessionNotFoundError,
    StreamingResponseGenerator,
    TurnAlreadyInProgressError,
    start_turn_stream,
)
from resultarai.core.registries import Registries

router = APIRouter(prefix="/api", tags=["chat-stream"])

_HEARTBEAT_ENV_VAR = "RESULTARAI_SSE_HEARTBEAT_INTERVAL_SECONDS"
_DEFAULT_HEARTBEAT_INTERVAL_SECONDS = 15.0

_CANCEL_WAIT_TIMEOUT_ENV_VAR = "RESULTARAI_CANCEL_WAIT_TIMEOUT_SECONDS"
_DEFAULT_CANCEL_WAIT_TIMEOUT_SECONDS = 10.0

# `get_turn_stream_registry` vive en `app/api/chat.py` (tarea 2.5), no acá: tanto este
# router (streaming) como `GET /sessions/{id}` (detalle, reconciliación) necesitan
# depender del MISMO proveedor -- `app.dependency_overrides` de FastAPI indexa por
# identidad de función -- para que `create_app()` los cablee con un único
# `TurnStreamRegistry` de proceso con un único override. Se re-importa acá (en vez de
# redefinirlo) para no romper los imports existentes de este módulo
# (`from resultarai.app.api.chat_stream import get_turn_stream_registry`, usado por
# `app/api/__init__.py` y los tests de streaming).


def get_streaming_response_generator() -> StreamingResponseGenerator:
    """Proveedor inyectable del generador de respuesta en streaming (tarea 1.5).

    Sin override falla explícitamente, igual que `get_response_generator` (el generador
    síncrono de `app/api/chat.py`): obliga a la composición real a inyectar la
    implementación que invoca el runtime de `b06-runtime-grafos` en modo streaming (fuera
    de alcance de esta tarea, ver `openspec/BACKLOG-DESCUBRIMIENTOS.md`), o a los tests a
    inyectar un doble que produzca fragmentos fijos.
    """
    raise NotImplementedError(
        "get_streaming_response_generator debe sobreescribirse via "
        "app.dependency_overrides: en producción con la implementación que invoca el "
        "runtime de b06 en modo streaming; en tests, con un doble que produzca "
        "fragmentos fijos."
    )


def _heartbeat_interval_seconds() -> float:
    """Lee el intervalo de heartbeat de la variable de entorno en cada petición.

    Deliberadamente NO cacheado a nivel de módulo: los tests fijan la variable de
    entorno justo antes de hacer la petición (intervalo bajo, para no esperar minutos
    reales a un heartbeat), y ese valor debe tomar efecto sin reiniciar el proceso.
    """
    raw = os.environ.get(_HEARTBEAT_ENV_VAR)
    if raw is None:
        return _DEFAULT_HEARTBEAT_INTERVAL_SECONDS
    try:
        return float(raw)
    except ValueError:
        return _DEFAULT_HEARTBEAT_INTERVAL_SECONDS


def _cancel_wait_timeout_seconds() -> float:
    """Lee (por petición, sin cachear -- mismo motivo que `_heartbeat_interval_seconds`)
    cuánto espera como máximo `POST .../cancel` a que el productor del turno cierre el
    buffer tras señalar la cancelación (tarea 1.7).
    """
    raw = os.environ.get(_CANCEL_WAIT_TIMEOUT_ENV_VAR)
    if raw is None:
        return _DEFAULT_CANCEL_WAIT_TIMEOUT_SECONDS
    try:
        return float(raw)
    except ValueError:
        return _DEFAULT_CANCEL_WAIT_TIMEOUT_SECONDS


def _format_sse(event: BufferedSseEvent) -> bytes:
    """Formatea un `BufferedSseEvent` como un frame SSE (`id`/`event`/`data` + línea en blanco).

    `data` ya es un string JSON compacto (`json.dumps` sin indentación, ver
    `streaming.py`): nunca contiene saltos de línea literales, así que el frame siempre
    cabe en una sola línea `data:` (requisito de SSE: un salto de línea dentro de `data`
    partiría el evento en dos).
    """
    return f"id: {event.id}\nevent: {event.event}\ndata: {event.data}\n\n".encode()


_HEARTBEAT_COMMENT = b": heartbeat\n\n"


def _iter_sse_bytes(
    events: Iterator[BufferedSseEvent], heartbeat_interval: float
) -> Iterator[bytes]:
    """Envuelve `events` con heartbeats periódicos mientras no haya nada nuevo (tarea 1.5).

    `events` corre en un hilo aparte (productor) mientras este generador (consumido por
    `StreamingResponse` en el hilo de la petición) hace polling de una cola con timeout
    igual al intervalo de heartbeat: si el timeout vence sin nada nuevo, emite un
    comentario SSE (`: heartbeat`, decisión 3 de `design.md` -- nunca un evento de
    datos) y vuelve a esperar. Necesario porque `events` es un iterador SÍNCRONO: sin un
    hilo productor no hay forma de "esperar con un tope" la siguiente pieza y emitir un
    heartbeat mientras tanto desde el mismo hilo que la produce.
    """
    pending: queue.Queue[tuple[str, Any]] = queue.Queue()

    def _drain() -> None:
        try:
            for event in events:
                pending.put(("event", event))
        except Exception as exc:  # pragma: no cover - defensivo, ver comentario abajo
            # Cualquier fallo del generador de eventos (p. ej. el `StreamingResponseGenerator`
            # inyectado lanza) se reenvía al consumidor en vez de perderse silenciosamente:
            # el stream SSE corta con el error en vez de colgarse esperando un evento que
            # nunca llega.
            pending.put(("error", exc))
        finally:
            pending.put(("done", None))

    producer = threading.Thread(target=_drain, daemon=True)
    producer.start()
    try:
        while True:
            try:
                kind, payload = pending.get(timeout=heartbeat_interval)
            except queue.Empty:
                yield _HEARTBEAT_COMMENT
                continue
            if kind == "done":
                return
            if kind == "error":
                raise payload
            yield _format_sse(payload)
    finally:
        producer.join(timeout=1.0)


@router.post("/sessions/{session_id}/messages/stream")
def send_message_stream_endpoint(
    session_id: str,
    payload: SendMessageRequest,
    db: Annotated[DbSession, Depends(get_db)],
    registries: Annotated[Registries, Depends(get_registries)],
    turn_stream_registry: Annotated[TurnStreamRegistry, Depends(get_turn_stream_registry)],
    current_user: Annotated[User, Depends(get_current_user)],
    generate_response: Annotated[
        StreamingResponseGenerator, Depends(get_streaming_response_generator)
    ],
) -> StreamingResponse:
    """Envía un turno nuevo o edita uno existente, transmitiendo la respuesta por SSE.

    Mismo modelo de turno/edición que `POST /sessions/{id}/messages` (tarea 1.2): la
    única diferencia es que la respuesta del agente se transmite incremental en vez de
    devolverse completa en el cuerpo de la respuesta. Ver el contrato SSE documentado en
    el docstring del módulo.

    Tarea 2.5 -- un solo turno en curso por sesión: si ya hay un turno EN CURSO sobre
    esta sesión (típicamente un "reenviar" accidental desde otra pestaña/dispositivo
    que no vio todavía `in_progress_turn` en `GET /sessions/{id}`), responde 409 con
    `{"turn_id": str}` del turno vivo -- nunca arranca un segundo streaming
    concurrente sobre la misma rama. El cliente debe re-attachearse a
    `GET /api/turns/{turn_id}/stream` (tarea 1.6) en vez de reintentar el envío.
    """
    edits_message_id: uuid.UUID | None = payload.edits_message_id
    try:
        turn_id, events = start_turn_stream(
            db,
            registries,
            turn_stream_registry,
            current_user,
            session_id,
            payload.text,
            generate_response,
            edits_message_id=edits_message_id,
        )
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Sesión no encontrada.") from exc
    except MessageEditForbiddenError as exc:
        raise HTTPException(
            status_code=403, detail="No se puede editar un mensaje que no es propio."
        ) from exc
    except TurnAlreadyInProgressError as exc:
        raise HTTPException(status_code=409, detail={"turn_id": exc.turn_id}) from exc

    # El buffer ya está registrado en este punto (`start_turn_stream` lo crea de forma
    # síncrona antes de devolver el iterador perezoso, ver su docstring): se lee de
    # vuelta solo para exponer `user_message_id` en un header de respuesta (tarea 1.7,
    # mecanismo de descubrimiento documentado en el docstring del módulo). Si no
    # estuviera -- invariante roto -- se falla fuerte en vez de mandar un header vacío.
    buffer = turn_stream_registry.get(turn_id)
    if buffer is None:  # pragma: no cover - invariante garantizado por start_turn_stream
        raise HTTPException(
            status_code=500, detail="El turno se creó sin un buffer de streaming registrado."
        )

    return StreamingResponse(
        _iter_sse_bytes(events, _heartbeat_interval_seconds()),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            # Desactiva el buffering de proxies inversos comunes (nginx) para que los
            # fragmentos lleguen al cliente a medida que se emiten, no en un solo lote al
            # cerrar la conexión.
            "X-Accel-Buffering": "no",
            "X-Turn-Id": turn_id,
            "X-User-Message-Id": str(buffer.user_message_id),
        },
    )


def _parse_last_event_id(request: Request, last_event_id_param: str | None) -> int:
    """Resuelve `Last-Event-ID` (tarea 1.6): header primero, query param como equivalente
    para clientes que no usan `EventSource` nativo (ver docstring del módulo). Sin
    ninguno de los dos, `0` (reproduce el turno completo). Un valor no numérico es un 400
    explícito -- nuestros `id` son siempre enteros positivos (`BufferedSseEvent.id`), así
    que un `Last-Event-ID` no numérico solo puede ser un cliente mal implementado.
    """
    raw = request.headers.get("last-event-id")
    if raw is None:
        raw = last_event_id_param
    if raw is None:
        return 0
    try:
        return int(raw)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Last-Event-ID inválido.") from exc


def _iter_reconnect_sse_bytes(
    buffer: TurnStreamBuffer, last_event_id: int, heartbeat_interval: float
) -> Iterator[bytes]:
    """Reproduce lo ya bufferizado desde `last_event_id` y sigue en vivo hasta el `done`
    (tarea 1.6).

    A diferencia de `_iter_sse_bytes`, no hay un hilo productor propio: este generador
    solo LEE el `TurnStreamBuffer` que ya está llenando (o ya llenó) la conexión SSE
    original -- nunca invoca de nuevo a ningún `StreamingResponseGenerator`, así que no
    hay forma de que esta función duplique el costo de una generación. El ritmo del
    heartbeat se controla con un reloj monotónico propio (no con el resultado de
    `wait_for_new`): perder una notificación por una carrera benigna solo demora hasta
    `heartbeat_interval` la próxima vuelta del bucle, que siempre vuelve a consultar
    `events_after`/`closed` sin importar por qué se despertó la espera.
    """
    last_heartbeat = time.monotonic()
    while True:
        new_events = buffer.events_after(last_event_id)
        for event in new_events:
            yield _format_sse(event)
            last_event_id = event.id
        if new_events:
            last_heartbeat = time.monotonic()
        if buffer.closed and not buffer.events_after(last_event_id):
            return
        remaining = heartbeat_interval - (time.monotonic() - last_heartbeat)
        if remaining <= 0:
            yield _HEARTBEAT_COMMENT
            last_heartbeat = time.monotonic()
            continue
        buffer.wait_for_new(timeout=remaining)


@router.get("/turns/{turn_id}/stream")
def reconnect_turn_stream_endpoint(
    turn_id: str,
    request: Request,
    turn_stream_registry: Annotated[TurnStreamRegistry, Depends(get_turn_stream_registry)],
    current_user: Annotated[User, Depends(get_current_user)],
    last_event_id: Annotated[str | None, Query(alias="last_event_id")] = None,
) -> StreamingResponse:
    """Reconecta a un turno en curso (o recién cerrado) por su `turn_id` (tarea 1.6).

    Ver el contrato completo (headers, precedencia de `Last-Event-ID`, semántica de
    replay) en el docstring del módulo. Nunca reinvoca al `StreamingResponseGenerator`:
    solo relee el `TurnStreamBuffer` ya existente del turno.
    """
    buffer = turn_stream_registry.get(turn_id)
    if buffer is None or buffer.owner_user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Turno no encontrado.")

    resolved_last_event_id = _parse_last_event_id(request, last_event_id)

    return StreamingResponse(
        _iter_reconnect_sse_bytes(buffer, resolved_last_event_id, _heartbeat_interval_seconds()),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "X-Turn-Id": turn_id,
        },
    )


class CancelTurnResponse(BaseModel):
    """Respuesta de la cancelación de un turno en streaming (tarea 1.7)."""

    turn_id: str
    user_message_id: str
    assistant_message_id: str | None
    status: str


def _cancel_buffer(buffer: TurnStreamBuffer) -> CancelTurnResponse:
    """Lógica de cancelación compartida por ambas rutas (`/turns/{id}/cancel` y
    `/messages/{id}/cancel`), una vez resuelto y verificado el ownership del buffer.

    Un turno ya cerrado (normal o cancelado antes) responde 409: cancelar no es una
    consulta idempotente de estado, es una acción que solo tiene sentido sobre un turno
    todavía en curso (ver docstring del módulo). Señala la cancelación y espera --
    acotado por `RESULTARAI_CANCEL_WAIT_TIMEOUT_SECONDS` -- a que el productor del turno
    (que corre en el hilo de la conexión SSE original, no en este request) termine de
    persistir el mensaje parcial con `status="stopped"` y cierre el buffer, para poder
    devolver de una vez el estado final ya confirmado.
    """
    if buffer.closed:
        raise HTTPException(status_code=409, detail="El turno ya finalizó.")

    buffer.request_cancel()

    timeout = _cancel_wait_timeout_seconds()
    deadline = time.monotonic() + timeout
    while not buffer.closed:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise HTTPException(
                status_code=504,
                detail=(
                    "La cancelación se señaló pero el turno no cerró a tiempo; "
                    "el cierre puede seguir llegando por el stream."
                ),
            )
        buffer.wait_for_new(timeout=remaining)

    done_event = next((e for e in reversed(buffer.events_after(0)) if e.event == "done"), None)
    assistant_message_id: str | None = None
    if done_event is not None:
        assistant_message_id = json.loads(done_event.data).get("assistant_message_id")

    return CancelTurnResponse(
        turn_id=buffer.turn_id,
        user_message_id=str(buffer.user_message_id),
        assistant_message_id=assistant_message_id,
        status="stopped",
    )


@router.post("/turns/{turn_id}/cancel")
def cancel_turn_endpoint(
    turn_id: str,
    turn_stream_registry: Annotated[TurnStreamRegistry, Depends(get_turn_stream_registry)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CancelTurnResponse:
    """Cancela el turno `turn_id` en streaming (tarea 1.7). Ver docstring del módulo."""
    buffer = turn_stream_registry.get(turn_id)
    if buffer is None or buffer.owner_user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Turno no encontrado.")
    return _cancel_buffer(buffer)


@router.post("/messages/{message_id}/cancel")
def cancel_turn_by_message_endpoint(
    message_id: uuid.UUID,
    turn_stream_registry: Annotated[TurnStreamRegistry, Depends(get_turn_stream_registry)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> CancelTurnResponse:
    """Cancela el turno cuyo mensaje de usuario es `message_id` (tarea 1.7): el endpoint
    que pide la tarea textualmente. `message_id` es el mensaje de USUARIO del turno (el
    único que existe desde el arranque) -- ver docstring del módulo.
    """
    buffer = turn_stream_registry.get_by_user_message_id(message_id)
    if buffer is None or buffer.owner_user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Turno no encontrado.")
    return _cancel_buffer(buffer)
