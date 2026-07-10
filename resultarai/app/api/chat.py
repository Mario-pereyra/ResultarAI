"""FastAPI router para endpoints de chat /api/sessions y /api/messages.

d13-chat-conversacion, tareas 1.1 (`POST /sessions`), 1.2 (`POST /sessions/{id}/messages`),
1.3 (`POST /messages/{id}/regenerate`), 1.8 (`POST /sessions/{id}/escalate`), 2.1
(`GET /sessions`), 2.3 y 2.5 (`GET /sessions/{id}`, árbol completo + reconciliación de
un turno en streaming en curso), 2.4 (`GET /sessions/search`) y el endpoint de
feedback exigido por el proposal (`POST /messages/{id}/feedback`, `b07-observabilidad`).

También define `get_turn_stream_registry` (tarea 2.5): aunque el registro de buffers
en streaming es sobre todo consumido por `app/api/chat_stream.py`, el proveedor vive
acá porque `GET /sessions/{id}` (este módulo) también lo necesita para reconciliar
`in_progress_turn` -- ver el docstring de `get_turn_stream_registry` para por qué
importa que ambos módulos compartan la MISMA función proveedora.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DbSession

from resultarai.adapters.persistence_postgres.models import Message, User
from resultarai.adapters.persistence_postgres.models import Session as SessionModel
from resultarai.app.identity import get_current_user, get_db
from resultarai.app.use_cases.chat import (
    AgentNotFoundError,
    EmptyFallbackCascadeError,
    EscalationDisabledError,
    EscalationMisconfiguredError,
    FeedbackMessageNotFoundError,
    FeedbackSubmitter,
    InProgressTurn,
    MessageEditForbiddenError,
    MessageNotEligibleError,
    MessageNotEligibleForFeedbackError,
    MessageNotFoundError,
    NoEligibleOriginMessageError,
    OriginMessageNotEligibleError,
    ResponseGenerator,
    SearchHit,
    SessionDetail,
    SessionNotFoundError,
    SessionSummary,
    create_session,
    escalate_session,
    get_session_detail,
    list_sessions,
    regenerate_response,
    search_sessions,
    send_turn,
    submit_message_feedback,
)
from resultarai.app.use_cases.chat.stream_registry import TurnStreamRegistry
from resultarai.core.registries import Registries

# Límites de paginación (listado y búsqueda de sesiones, tareas 2.1/2.4): ventanas de
# 25 (`design/VISTAS/02-chat.md`, vista 12: "lista paginada por scroll, ventanas de
# 25"); 100 es el techo defensivo contra un `limit` desmedido en la query string.
_DEFAULT_PAGE_SIZE = 25
_MAX_PAGE_SIZE = 100


def _clamp_pagination(limit: int, offset: int) -> tuple[int, int]:
    """Normaliza `limit`/`offset` de la query string a valores sanos.

    Fuera de rango cae al default en vez de responder 422: son parámetros de
    paginación, no de validación de negocio (mismo criterio que `page`/`page_size`
    de `resultarai/app/api/notifications.py`).
    """
    if limit < 1 or limit > _MAX_PAGE_SIZE:
        limit = _DEFAULT_PAGE_SIZE
    if offset < 0:
        offset = 0
    return limit, offset


router = APIRouter(prefix="/api", tags=["chat"])


def get_registries() -> Registries:
    """Proveedor inyectable de los Registries del catalogo de manifiestos.

    Sin override falla explicitamente en vez de devolver `None`, igual que `get_db`
    de `identity/dependency.py`: obliga a la composicion real (`create_app`) o al
    test a inyectar los `Registries` concretos (un `bootstrap()` cacheado en
    produccion, o los `Registries` reales de `manifests/` en los tests).
    """
    raise NotImplementedError(
        "get_registries debe sobreescribirse via app.dependency_overrides con los "
        "Registries reales que produce bootstrap()."
    )


def get_response_generator() -> ResponseGenerator:
    """Proveedor inyectable del generador de la respuesta del agente (tareas 1.2/1.3).

    Sin override falla explicitamente, igual que `get_registries`: obliga a la
    composicion real a inyectar la implementacion que invoca el runtime de
    `b06-runtime-grafos` (`resultarai/adapters/runtime_langgraph/default_chat_graph.py`),
    o a los tests de API a inyectar un doble que devuelva texto fijo (mismo patron que
    `tests/contracts/fixtures/doubles.py`). La composicion real de este provider queda
    fuera del alcance de las tareas 1.2/1.3 (ver `turns.py`): se resuelve cuando el
    change conecte la escalacion (tarea 1.4) y el streaming (tarea 1.5), que son quienes
    necesitan manejar el contrato completo de salida del runtime (marcador de
    escalacion, metadatos de costo/cache) antes de persistir texto del modelo real.
    """
    raise NotImplementedError(
        "get_response_generator debe sobreescribirse via app.dependency_overrides: en "
        "produccion con la implementacion que invoca el runtime de b06; en tests, con "
        "un doble que devuelva texto fijo."
    )


def get_turn_stream_registry() -> TurnStreamRegistry:
    """Proveedor inyectable del registro de buffers de turnos en streaming.

    Definido acá (no en `app/api/chat_stream.py`, que lo importa de vuelta) para que
    tanto el streaming (tareas 1.5/1.6/1.7) como el detalle de sesión (tarea 2.5,
    `get_session_detail_endpoint` de este mismo módulo) dependan del MISMO objeto
    proveedor -- `app.dependency_overrides` de FastAPI indexa por identidad de la
    función, así que un único `create_app()` con un único override
    (`app/api/__init__.py`) alcanza para que ambos endpoints vean el mismo
    `TurnStreamRegistry` de proceso; si cada módulo definiera su propio proveedor
    homónimo, harían falta dos overrides sincronizados a mano, con el riesgo de que
    quedaran apuntando a instancias distintas.

    Sin override falla explícitamente (mismo patrón fail-loud que `get_registries`/
    `get_response_generator`): `create_app()` lo sobreescribe con una instancia real
    por app (no cacheada globalmente, para que cada `create_app()` de test quede
    aislado); es infraestructura de proceso sin I/O externo, así que en los tests
    alcanza con la misma implementación real, sin necesidad de un doble.
    """
    raise NotImplementedError(
        "get_turn_stream_registry debe sobreescribirse via app.dependency_overrides con "
        "una instancia real de TurnStreamRegistry (una por proceso/app)."
    )


def get_feedback_submitter() -> FeedbackSubmitter:
    """Proveedor inyectable del envío de feedback a Langfuse (endpoint de feedback).

    Sin override falla explícitamente, mismo patrón fail-loud que `get_registries`/
    `get_response_generator`. A diferencia de `get_response_generator` (que sí queda
    sin override de producción -- ver `openspec/BACKLOG-DESCUBRIMIENTOS.md`, el
    Policy Gate todavía no autoriza ningún turno real), este provider SÍ se
    sobreescribe en `create_app()` (`resultarai/app/api/__init__.py`) con una
    implementación real que delega en
    `resultarai.adapters.tracing_langfuse.feedback.submit_feedback`: el adapter de
    Langfuse ya está implementado y probado (`tests/contracts/test_response_feedback.py`),
    no depende de ningún wiring pendiente del runtime. En los tests de API se
    sobreescribe con un doble que registra las llamadas recibidas.
    """
    raise NotImplementedError(
        "get_feedback_submitter debe sobreescribirse via app.dependency_overrides: en "
        "produccion con la implementacion que delega en "
        "tracing_langfuse.feedback.submit_feedback; en tests, con un doble que "
        "registre las llamadas."
    )


class CreateSessionRequest(BaseModel):
    """Payload de `POST /sessions`: el unico dato que el cliente elige es el agente."""

    agent_id: str = Field(..., min_length=1)


class SessionResponse(BaseModel):
    """Respuesta de una sesion recien creada."""

    id: str
    agent_id: str | None
    model_profile: str
    created_at: str


@router.post("/sessions", status_code=201)
def create_session_endpoint(
    payload: CreateSessionRequest,
    db: Annotated[DbSession, Depends(get_db)],
    registries: Annotated[Registries, Depends(get_registries)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> SessionResponse:
    """Crea una sesion de chat asociada a un agente del catalogo.

    Fija el `model_profile` inicial de la sesion segun el primer elemento de
    `fallback_cascade` del Agent Manifest (stickiness, `chat-streaming` spec). El
    usuario dueno de la sesion se deriva **siempre** de la cookie de sesion
    (`get_current_user`), nunca de un parametro del body.
    """
    try:
        session = create_session(db, registries, current_user, payload.agent_id)
    except AgentNotFoundError as exc:
        raise HTTPException(
            status_code=404, detail="Agente no encontrado o no disponible."
        ) from exc
    except EmptyFallbackCascadeError as exc:
        raise HTTPException(
            status_code=422,
            detail="El agente no tiene una cascada de perfiles de modelo configurada.",
        ) from exc

    return SessionResponse(
        id=session.id,
        agent_id=session.agent_id,
        model_profile=session.model_profile,
        created_at=session.created_at.isoformat(),
    )


class SessionSummaryResponse(BaseModel):
    """Una fila del listado de sesiones propias (tarea 2.1, vista 12)."""

    id: str
    agent_id: str | None
    title: str | None
    model_profile: str
    last_activity_at: str | None
    message_count: int
    branch_count: int


class ListSessionsResponse(BaseModel):
    """Respuesta paginada de `GET /sessions`."""

    items: list[SessionSummaryResponse]
    limit: int
    offset: int


def _to_session_summary_response(summary: SessionSummary) -> SessionSummaryResponse:
    """Traduce un `SessionSummary` del caso de uso a su representación de API."""
    session = summary.session
    return SessionSummaryResponse(
        id=session.id,
        agent_id=session.agent_id,
        title=session.title,
        model_profile=session.model_profile,
        last_activity_at=(
            session.last_activity_at.isoformat() if session.last_activity_at is not None else None
        ),
        message_count=summary.message_count,
        branch_count=summary.branch_count,
    )


@router.get("/sessions")
def list_sessions_endpoint(
    db: Annotated[DbSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    limit: int = _DEFAULT_PAGE_SIZE,
    offset: int = 0,
) -> ListSessionsResponse:
    """Lista las sesiones propias del usuario autenticado (tarea 2.1).

    El propietario se deriva **siempre** de la cookie de sesión (`get_current_user`),
    nunca de un parámetro de la petición: el listado de un usuario nunca incluye
    sesiones de otro. Orden por última actividad descendente, con `message_count` y
    `branch_count` (ver docstring de `history.py` para la definición exacta de
    "punto de bifurcación") calculados con consultas agregadas, sin cargar el árbol
    de mensajes completo de cada sesión.
    """
    limit, offset = _clamp_pagination(limit, offset)
    summaries = list_sessions(db, current_user, limit=limit, offset=offset)
    return ListSessionsResponse(
        items=[_to_session_summary_response(summary) for summary in summaries],
        limit=limit,
        offset=offset,
    )


class SessionSearchHitResponse(BaseModel):
    """Una coincidencia de `GET /sessions/search` (tarea 2.4).

    `snippet` es el fragmento de texto (título o contenido de mensaje) alrededor del
    término encontrado; `match_start`/`match_end` son los offsets del término DENTRO
    de `snippet` (no del texto completo), para que la UI lo resalte sin tener que
    volver a buscarlo del lado del cliente.
    """

    session_id: str
    agent_id: str | None
    title: str | None
    last_activity_at: str | None
    match_type: Literal["title", "message"]
    message_id: str | None
    snippet: str
    match_start: int
    match_end: int


class SearchSessionsResponse(BaseModel):
    """Respuesta paginada de `GET /sessions/search`."""

    items: list[SessionSearchHitResponse]
    limit: int
    offset: int


def _to_search_hit_response(hit: SearchHit) -> SessionSearchHitResponse:
    """Traduce un `SearchHit` del caso de uso a su representación de API."""
    session = hit.session
    return SessionSearchHitResponse(
        session_id=session.id,
        agent_id=session.agent_id,
        title=session.title,
        last_activity_at=(
            session.last_activity_at.isoformat() if session.last_activity_at is not None else None
        ),
        match_type=hit.match_type,
        message_id=str(hit.message_id) if hit.message_id is not None else None,
        snippet=hit.snippet,
        match_start=hit.match_start,
        match_end=hit.match_end,
    )


@router.get("/sessions/search")
def search_sessions_endpoint(
    db: Annotated[DbSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    q: Annotated[str, Query(min_length=1)],
    limit: int = _DEFAULT_PAGE_SIZE,
    offset: int = 0,
) -> SearchSessionsResponse:
    """Busca `q` en el título y el contenido de mensajes de las sesiones propias
    del usuario autenticado (tarea 2.4).

    Declarado ANTES de `GET /sessions/{session_id}` a propósito: en FastAPI, la
    ruta literal `/sessions/search` debe registrarse antes que la ruta paramétrica
    `/sessions/{session_id}` para que `"search"` no matchee como un `session_id`.
    Término ausente en todas las sesiones propias del usuario: `items: []`, sin
    lanzar ningún error. La búsqueda de un usuario nunca retorna sesiones de otro
    (mismo filtro de ownership que el listado).
    """
    limit, offset = _clamp_pagination(limit, offset)
    hits = search_sessions(db, current_user, q, limit=limit, offset=offset)
    return SearchSessionsResponse(
        items=[_to_search_hit_response(hit) for hit in hits],
        limit=limit,
        offset=offset,
    )


class SessionTreeMessageResponse(BaseModel):
    """Un mensaje del árbol completo de una sesión (tarea 2.3).

    Expone `turn_metadata` tal cual está persistido (costo, perfil, cache,
    escalación, etc. -- ver `Message.turn_metadata` en `models.py`); el filtrado de
    qué mostrar según el rol de la sesión de identidad es responsabilidad de la UI
    (tarea 4.1 de este mismo change), no de este endpoint.
    """

    id: str
    parent_id: str | None
    role: str
    content: str
    status: str
    created_at: str
    turn_metadata: dict[str, Any] | None


class InProgressTurnResponse(BaseModel):
    """Turno en streaming EN CURSO sobre la sesión, visto desde otra pestaña o
    dispositivo (tarea 2.5): con esto el cliente que reanuda sabe que debe
    re-attachearse a `GET /api/turns/{turn_id}/stream` (tarea 1.6) en vez de reenviar
    el mismo mensaje de usuario -- que ya aparece en `messages`, sin respuesta de
    agente todavía -- evitando así un turno duplicado.
    """

    turn_id: str
    user_message_id: str
    last_event_id: int


class SessionDetailResponse(BaseModel):
    """Respuesta de `GET /sessions/{session_id}` (tarea 2.3): el árbol completo de
    mensajes de la sesión, más los metadatos que la UI necesita para el selector de
    versiones, la nota-enlace bidireccional de escalación (vista 08) y la
    reconciliación de un turno en streaming en otra pestaña (tarea 2.5).
    """

    id: str
    agent_id: str | None
    title: str | None
    model_profile: str
    forked_from_id: str | None
    escalated_session_ids: list[str]
    active_leaf_id: str | None
    messages: list[SessionTreeMessageResponse]
    in_progress_turn: InProgressTurnResponse | None


def _to_session_tree_message_response(message: Message) -> SessionTreeMessageResponse:
    """Traduce un `Message` persistido a su representación en el árbol de la sesión."""
    return SessionTreeMessageResponse(
        id=str(message.id),
        parent_id=str(message.parent_id) if message.parent_id is not None else None,
        role=message.role,
        content=message.content,
        status=message.status,
        created_at=message.created_at.isoformat(),
        turn_metadata=message.turn_metadata,
    )


def _to_in_progress_turn_response(turn: InProgressTurn) -> InProgressTurnResponse:
    """Traduce un `InProgressTurn` del caso de uso a su representación de API."""
    return InProgressTurnResponse(
        turn_id=turn.turn_id,
        user_message_id=str(turn.user_message_id),
        last_event_id=turn.last_event_id,
    )


def _to_session_detail_response(detail: SessionDetail) -> SessionDetailResponse:
    """Traduce un `SessionDetail` del caso de uso a su representación de API."""
    session = detail.session
    return SessionDetailResponse(
        id=session.id,
        agent_id=session.agent_id,
        title=session.title,
        model_profile=session.model_profile,
        forked_from_id=session.forked_from_id,
        escalated_session_ids=detail.escalated_session_ids,
        active_leaf_id=str(detail.active_leaf_id) if detail.active_leaf_id is not None else None,
        messages=[_to_session_tree_message_response(message) for message in detail.messages],
        in_progress_turn=(
            _to_in_progress_turn_response(detail.in_progress_turn)
            if detail.in_progress_turn is not None
            else None
        ),
    )


@router.get("/sessions/{session_id}")
def get_session_detail_endpoint(
    session_id: str,
    db: Annotated[DbSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    turn_stream_registry: Annotated[TurnStreamRegistry, Depends(get_turn_stream_registry)],
) -> SessionDetailResponse:
    """Devuelve el árbol completo de mensajes de `session_id` (tarea 2.3).

    Incluye TODOS los mensajes de la sesión -- ramas activas y descartadas (por
    edición o "Seguir con Flash") por igual, cada uno con su `parent_id` -- para que
    la UI reconstruya cualquier rama y el selector de versiones. Sesión ajena o
    inexistente: 404 sin distinguir el motivo (mismo criterio de no filtrar
    existencia que el resto de los endpoints de sesión).

    Tarea 2.5 (reanudar sesión): también reconcilia un turno en streaming EN CURSO
    sobre esta sesión -- arrancado desde otra pestaña o dispositivo -- exponiéndolo
    como `in_progress_turn` (ver `InProgressTurnResponse`). El mensaje de usuario de
    ese turno YA aparece en `messages` (se persiste al arrancar, antes de generar la
    respuesta); reanudar nunca reenvía ese mismo texto, así que nunca duplica el
    turno -- el cliente que reanuda se re-attachea al stream real en vez de reenviar.
    """
    try:
        detail = get_session_detail(db, current_user, session_id, turn_stream_registry)
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Sesión no encontrada.") from exc

    return _to_session_detail_response(detail)


class SendMessageRequest(BaseModel):
    """Payload de `POST /sessions/{id}/messages`: turno normal o edición (decisión 4).

    `edits_message_id` es el único campo que distingue un turno normal de una edición
    (`design.md`, decisión 4): reutiliza este mismo endpoint en vez de un `PATCH`
    separado, porque ambas operaciones son "crear un mensaje nuevo en la rama".
    """

    text: str = Field(..., min_length=1)
    edits_message_id: uuid.UUID | None = None


class MessageResponse(BaseModel):
    """Representación de un mensaje persistido (usuario o agente)."""

    id: str
    session_id: str
    parent_id: str | None
    role: str
    content: str
    status: str
    created_at: str


class SendMessageResponse(BaseModel):
    """Respuesta de un turno enviado o editado: ambos mensajes creados y el reproceso."""

    user_message: MessageResponse
    assistant_message: MessageResponse
    reprocessed_count: int


class RegenerateResponse(BaseModel):
    """Respuesta de una regeneración: el mensaje nuevo y su posición entre versiones."""

    message: MessageResponse
    version: int
    version_count: int


def _to_message_response(message: Message) -> MessageResponse:
    """Traduce un `Message` persistido a su representación de API."""
    return MessageResponse(
        id=str(message.id),
        session_id=message.session_id,
        parent_id=str(message.parent_id) if message.parent_id is not None else None,
        role=message.role,
        content=message.content,
        status=message.status,
        created_at=message.created_at.isoformat(),
    )


@router.post("/sessions/{session_id}/messages", status_code=201)
def send_message_endpoint(
    session_id: str,
    payload: SendMessageRequest,
    db: Annotated[DbSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    generate_response: Annotated[ResponseGenerator, Depends(get_response_generator)],
) -> SendMessageResponse:
    """Envía un turno nuevo o edita uno existente (tarea 1.2).

    Editar reutiliza este mismo endpoint (decisión 4 de `design.md`): la única
    diferencia con un turno normal es de qué `parent_id` cuelga el mensaje de usuario
    nuevo. El usuario dueño se deriva **siempre** de la cookie de sesión
    (`get_current_user`), nunca del payload; una sesión ajena responde 404 (sin filtrar
    existencia) y editar un mensaje que no pertenece a esta sesión responde 403 sin
    crear ninguna fila.
    """
    try:
        result = send_turn(
            db,
            current_user,
            session_id,
            payload.text,
            generate_response,
            edits_message_id=payload.edits_message_id,
        )
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Sesión no encontrada.") from exc
    except MessageEditForbiddenError as exc:
        raise HTTPException(
            status_code=403, detail="No se puede editar un mensaje que no es propio."
        ) from exc

    return SendMessageResponse(
        user_message=_to_message_response(result.user_message),
        assistant_message=_to_message_response(result.assistant_message),
        reprocessed_count=result.reprocessed_count,
    )


@router.post("/messages/{message_id}/regenerate", status_code=201)
def regenerate_message_endpoint(
    message_id: uuid.UUID,
    db: Annotated[DbSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    generate_response: Annotated[ResponseGenerator, Depends(get_response_generator)],
) -> RegenerateResponse:
    """Regenera la respuesta de un mensaje de agente como versión hermana (tarea 1.3).

    Solo aplica a mensajes de rol `assistant` (422 en cualquier otro caso); la sesión del
    mensaje debe pertenecer al usuario actual (404 sin filtrar existencia en caso
    contrario, ni crear nada).
    """
    try:
        result = regenerate_response(db, current_user, message_id, generate_response)
    except MessageNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Mensaje no encontrado.") from exc
    except MessageNotEligibleError as exc:
        raise HTTPException(
            status_code=422, detail="Solo se puede regenerar una respuesta del agente."
        ) from exc

    return RegenerateResponse(
        message=_to_message_response(result.message),
        version=result.version,
        version_count=result.version_count,
    )


class EscalateSessionRequest(BaseModel):
    """Payload de `POST /sessions/{id}/escalate`: qué turno re-plantear.

    `origin_message_id` es opcional: sin él, se re-plantea el último mensaje de
    usuario de la rama activa de la sesión (ver `escalate_session` en
    `use_cases/chat/escalation.py`).
    """

    origin_message_id: uuid.UUID | None = None


class EscalateSessionResponse(BaseModel):
    """Respuesta de una escalación (creada de cero o idempotente).

    Incluye el título de AMBAS sesiones (`origin_session_title`/
    `escalated_session_title`) para que la UI pueda armar la nota-enlace
    bidireccional de la vista 08 sin una consulta adicional en ningún sentido.
    """

    escalated_session_id: str
    origin_session_id: str
    model_profile: str
    seeded_message_id: str
    created: bool
    origin_session_title: str | None
    escalated_session_title: str | None


@router.post("/sessions/{session_id}/escalate")
def escalate_session_endpoint(
    session_id: str,
    payload: EscalateSessionRequest,
    response: Response,
    db: Annotated[DbSession, Depends(get_db)],
    registries: Annotated[Registries, Depends(get_registries)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> EscalateSessionResponse:
    """Escala manualmente `session_id` a una sesión nueva con el perfil configurado
    (tarea 1.8). Ver el docstring completo de `escalate_session`
    (`use_cases/chat/escalation.py`) para el orden de validaciones y la clave de
    idempotencia.

    Esta llamada ES la confirmación explícita del usuario que exige la spec: nunca
    se dispara automáticamente al recibir un evento de escalación en el stream.
    Responde `201` si crea una sesión escalada nueva, `200` si devuelve una ya
    existente (segunda llamada idempotente sobre el mismo turno de origen -- doble
    clic/doble pestaña, tarea 5.3 de UI).
    """
    try:
        result = escalate_session(
            db, registries, current_user, session_id, payload.origin_message_id
        )
    except SessionNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Sesión no encontrada.") from exc
    except EscalationDisabledError as exc:
        raise HTTPException(
            status_code=403, detail="La escalación está deshabilitada para este agente."
        ) from exc
    except EscalationMisconfiguredError as exc:
        raise HTTPException(
            status_code=422,
            detail="El agente tiene la escalación habilitada pero sin un perfil de "
            "destino configurado.",
        ) from exc
    except OriginMessageNotEligibleError as exc:
        raise HTTPException(
            status_code=422,
            detail="origin_message_id no corresponde a un mensaje de usuario de esta sesión.",
        ) from exc
    except NoEligibleOriginMessageError as exc:
        raise HTTPException(
            status_code=422,
            detail="La sesión no tiene ningún mensaje de usuario para re-plantear.",
        ) from exc

    response.status_code = 201 if result.created else 200
    return EscalateSessionResponse(
        escalated_session_id=result.escalated_session.id,
        origin_session_id=result.origin_session.id,
        model_profile=result.escalated_session.model_profile,
        seeded_message_id=str(result.seeded_message.id),
        created=result.created,
        origin_session_title=result.origin_session.title,
        escalated_session_title=result.escalated_session.title,
    )


class SubmitFeedbackRequest(BaseModel):
    """Payload de `POST /messages/{id}/feedback`: voto obligatorio, comentario opcional."""

    vote: Literal["up", "down"]
    comment: str | None = None


class SubmitFeedbackResponse(BaseModel):
    """Respuesta de un feedback registrado."""

    message_id: str
    vote: str
    trace_id: str


@router.post("/messages/{message_id}/feedback", status_code=201)
def submit_message_feedback_endpoint(
    message_id: uuid.UUID,
    payload: SubmitFeedbackRequest,
    db: Annotated[DbSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
    submit: Annotated[FeedbackSubmitter, Depends(get_feedback_submitter)],
) -> SubmitFeedbackResponse:
    """Registra un voto 👍/👎 (con comentario opcional) sobre una respuesta del
    agente, ligado a su traza (endpoint exigido por el proposal, `b07-observabilidad`).

    Solo sobre mensajes de rol `assistant` de sesiones propias (422 en cualquier
    otro caso; sesión ajena o mensaje inexistente: 404 sin filtrar el motivo).
    Votar de nuevo sobre el mismo mensaje reenvía un score nuevo -- ver la nota de
    "reemplazo de voto" en `use_cases/chat/feedback.py`: el voto vigente es,
    semánticamente, el último enviado, sin mutar ningún score anterior en Langfuse.
    """
    try:
        result = submit_message_feedback(
            db, current_user, message_id, payload.vote, payload.comment, submit
        )
    except FeedbackMessageNotFoundError as exc:
        raise HTTPException(status_code=404, detail="Mensaje no encontrado.") from exc
    except MessageNotEligibleForFeedbackError as exc:
        raise HTTPException(
            status_code=422, detail="Solo se puede calificar una respuesta del agente."
        ) from exc

    return SubmitFeedbackResponse(
        message_id=str(result.message_id), vote=result.vote, trace_id=result.trace_id
    )


class UpdateSessionTitleRequest(BaseModel):
    """Payload de `PATCH /sessions/{session_id}`: edición manual del título."""

    title: str = Field(..., min_length=1, max_length=120)


class UpdateSessionTitleResponse(BaseModel):
    """Respuesta de `PATCH /sessions/{session_id}`: metadatos del título actualizado."""

    id: str
    title: str
    title_edited: bool


@router.patch("/sessions/{session_id}")
def update_session_title_endpoint(
    session_id: str,
    payload: UpdateSessionTitleRequest,
    db: Annotated[DbSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> UpdateSessionTitleResponse:
    """Edita manualmente el título de una sesión (tarea 2.2).

    El usuario dueño se deriva **siempre** de la cookie de sesión (`get_current_user`),
    nunca del payload; una sesión ajena responde 404 (sin filtrar existencia). El
    título debe tener al menos 1 carácter y máximo 120, y no puede ser solo espacios.
    Establece `title_edited=True` para evitar que turnos posteriores regeneren el
    título automáticamente.
    """
    # Valida que el título no sea solo espacios.
    if not payload.title.strip():
        raise HTTPException(status_code=422, detail="El título no puede contener solo espacios.")

    # Busca la sesión asegurando que pertenece al usuario actual.
    session = db.get(SessionModel, session_id)
    if session is None or session.owner_user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Sesión no encontrada.")

    # Actualiza el título y marca como editado manualmente.
    session.title = payload.title
    session.title_edited = True
    db.flush()

    return UpdateSessionTitleResponse(
        id=session.id, title=session.title, title_edited=session.title_edited
    )
