"""Registro en memoria de los buffers de eventos SSE de turnos en streaming.

d13-chat-conversacion, tarea 1.5 (decisión 2 de `design.md`): cada turno en streaming
acumula sus eventos SSE ya emitidos (con su `id` incremental) en un `TurnStreamBuffer`
propio, vivo mientras dure el proceso. Se diseña explícitamente para que:

- la tarea 1.6 (reconexión por `Last-Event-ID`) pueda hacer
  `registry.get(turn_id).events_after(last_event_id)` y reproducir sin volver a invocar
  al runtime, sin tener que rehacer este módulo;
- la tarea 1.7 (cancelación) pueda usar el mismo registro para localizar el turno en
  curso por `turn_id` y marcarlo para detener la generación.

No es persistencia (`b04`): si el proceso se reinicia, el buffer desaparece -- y con él
la respuesta en curso completa, porque `messages` es append-only a nivel de base y la
respuesta del agente se inserta en un único INSERT recién al cierre del turno (ver la
nota de módulo de `streaming.py` y el descubrimiento correspondiente en
`openspec/BACKLOG-DESCUBRIMIENTOS.md`; el mensaje de usuario sí sobrevive y el turno
queda reintentable).

No vive en `core/` (regla dura 1): es infraestructura de proceso (hilos, memoria), no
lógica de dominio.

**Tarea 1.6 (reconexión) -- `owner_user_id` y `wait_for_new`:** el `TurnStreamBuffer`
guarda el dueño del turno desde su creación (nunca se resuelve por un parámetro de la
petición: la API de reconexión/cancelación siempre compara contra el usuario autenticado
actual). `wait_for_new` expone una espera acotada notificada por `append` -- así
`app/api/chat_stream.py` puede "seguir" un turno en curso sin hacer polling ciego: espera
hasta `timeout` o hasta que `append` notifique, lo que ocurra primero, y siempre
re-consulta el estado real después (ninguna decisión de corrección depende de si la
espera terminó por notificación o por timeout, solo el ritmo del heartbeat).

**Tarea 1.7 (cancelación) -- `user_message_id` y `request_cancel`:** el mensaje de
usuario del turno existe desde el arranque (se persiste antes de generar la respuesta,
ver `streaming.py`), así que es un identificador estable para cancelar incluso antes de
que exista el mensaje de agente. El registro indexa también por `user_message_id` para
que `POST /api/messages/{id}/cancel` pueda resolver el turno en curso sin conocer su
`turn_id`. `request_cancel` solo levanta una bandera thread-safe (`threading.Event`) y
notifica a quien esté esperando eventos nuevos -- quien realmente detiene la generación es
el consumidor del `StreamingResponseGenerator` en `streaming.py`, que la consulta entre
fragmento y fragmento.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field

__all__ = ["BufferedSseEvent", "TurnStreamBuffer", "TurnStreamRegistry"]


@dataclass(frozen=True)
class BufferedSseEvent:
    """Un evento SSE ya formateado (listo para servirse), con su `id` incremental."""

    id: int
    event: str
    data: str


@dataclass
class TurnStreamBuffer:
    """Buffer de los eventos SSE emitidos para un turno concreto.

    Los `id` son incrementales por turno (empiezan en 1), como pide la decisión 2 de
    `design.md` (habilita `Last-Event-ID` en la tarea 1.6). `closed` se vuelve `True` al
    agregar el evento `done` (cierre del turno, normal o cancelado).

    `owner_user_id` y `user_message_id` se fijan una única vez al crear el buffer
    (`TurnStreamRegistry.create`) y nunca cambian: son la base del control de acceso de
    la reconexión y la cancelación (ownership derivado siempre del buffer, nunca de un
    parámetro de la petición).
    """

    turn_id: str
    owner_user_id: uuid.UUID
    user_message_id: uuid.UUID
    events: list[BufferedSseEvent] = field(default_factory=list)
    closed: bool = False
    _condition: threading.Condition = field(
        default_factory=threading.Condition, repr=False, compare=False
    )
    _cancel_event: threading.Event = field(
        default_factory=threading.Event, repr=False, compare=False
    )

    def append(self, event: str, data: str) -> BufferedSseEvent:
        """Agrega un evento nuevo, asignándole el siguiente `id` incremental."""
        with self._condition:
            buffered = BufferedSseEvent(id=len(self.events) + 1, event=event, data=data)
            self.events.append(buffered)
            if event == "done":
                self.closed = True
            self._condition.notify_all()
            return buffered

    def events_after(self, last_event_id: int) -> list[BufferedSseEvent]:
        """Eventos con `id` estrictamente mayor a `last_event_id` (replay, tarea 1.6)."""
        with self._condition:
            return [e for e in self.events if e.id > last_event_id]

    def wait_for_new(self, timeout: float) -> bool:
        """Espera, acotado por `timeout`, a que se agregue un evento nuevo.

        Devuelve `True` si hubo una notificación (`append`/`request_cancel`) antes de
        agotar `timeout`, `False` si el timeout venció sin novedades. El llamador
        SIEMPRE debe re-consultar el estado real (`events_after`/`closed`) después de
        llamar a este método -- una notificación perdida por una carrera benigna (p. ej.
        `append` ocurre justo entre que el llamador revisó el estado y llamó a este
        método) solo demora hasta `timeout` la próxima comprobación, nunca produce un
        resultado incorrecto (ver `app/api/chat_stream.py`, que siempre vuelve a
        consultar el buffer al tope de su bucle sin importar el resultado de esta
        llamada).
        """
        with self._condition:
            return self._condition.wait(timeout=timeout)

    def request_cancel(self) -> None:
        """Señala al productor del turno que detenga la generación (tarea 1.7).

        Thread-safe (`threading.Event`): el productor (`streaming.py`,
        `_produce_turn_events`) consulta `cancel_requested` entre fragmento y
        fragmento del `StreamingResponseGenerator` inyectado -- no interrumpe una
        invocación en curso al generador (Python no tiene forma segura de abortar un
        hilo desde afuera), pero impide que se lo siga consumiendo más allá del
        próximo punto de control, y notifica a quien esté esperando en
        `wait_for_new` para que no se quede esperando el heartbeat completo.
        """
        self._cancel_event.set()
        with self._condition:
            self._condition.notify_all()

    @property
    def cancel_requested(self) -> bool:
        """`True` si `request_cancel` ya fue invocado para este turno."""
        return self._cancel_event.is_set()


class TurnStreamRegistry:
    """Registro de `TurnStreamBuffer` por `turn_id`, en memoria del proceso.

    Una instancia vive por proceso/deployable (patrón análogo a `_load_registries` en
    `app/api/__init__.py`, pero sin `lru_cache`: `create_app()` instancia una por app
    para que los tests de distintos clientes queden aislados entre sí).

    Indexa también por `user_message_id` (tarea 1.7), usando `str(uuid.UUID)` como
    clave del índice secundario.
    """

    def __init__(self) -> None:
        self._buffers: dict[str, TurnStreamBuffer] = {}
        self._turn_id_by_user_message: dict[str, str] = {}
        self._lock = threading.Lock()

    def create(
        self, turn_id: str, *, owner_user_id: uuid.UUID, user_message_id: uuid.UUID
    ) -> TurnStreamBuffer:
        """Crea (y registra) un buffer nuevo y vacío para `turn_id`.

        `owner_user_id` y `user_message_id` son obligatorios: todo turno en streaming
        tiene un dueño y un mensaje de usuario desde su creación (ver `streaming.py`,
        `start_turn_stream`), y ambos son la base de la resolución de ownership de la
        reconexión (tarea 1.6) y la cancelación (tarea 1.7).
        """
        with self._lock:
            buffer = TurnStreamBuffer(
                turn_id=turn_id, owner_user_id=owner_user_id, user_message_id=user_message_id
            )
            self._buffers[turn_id] = buffer
            self._turn_id_by_user_message[str(user_message_id)] = turn_id
            return buffer

    def get(self, turn_id: str) -> TurnStreamBuffer | None:
        """Devuelve el buffer de `turn_id`, o `None` si no existe (turno desconocido)."""
        with self._lock:
            return self._buffers.get(turn_id)

    def get_by_user_message_id(self, user_message_id: uuid.UUID) -> TurnStreamBuffer | None:
        """Devuelve el buffer del turno cuyo mensaje de usuario es `user_message_id`.

        Tarea 1.7: permite `POST /api/messages/{id}/cancel` resolver el turno en curso
        a partir del mensaje de usuario (el único identificador estable disponible
        desde el arranque del turno, antes de que exista el mensaje de agente).
        """
        with self._lock:
            turn_id = self._turn_id_by_user_message.get(str(user_message_id))
            if turn_id is None:
                return None
            return self._buffers.get(turn_id)

    def discard(self, turn_id: str) -> None:
        """Elimina el buffer de `turn_id` (limpieza tras cerrar/cancelar el turno)."""
        with self._lock:
            buffer = self._buffers.pop(turn_id, None)
            if buffer is not None:
                self._turn_id_by_user_message.pop(str(buffer.user_message_id), None)
