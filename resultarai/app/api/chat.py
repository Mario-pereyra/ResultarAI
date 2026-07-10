"""FastAPI router para endpoints de chat /api/sessions y /api/messages.

d13-chat-conversacion, tareas 1.1 (`POST /sessions`), 1.2 (`POST /sessions/{id}/messages`),
1.3 (`POST /messages/{id}/regenerate`), 1.8 (`POST /sessions/{id}/escalate`) y el endpoint
de feedback exigido por el proposal (`POST /messages/{id}/feedback`, `b07-observabilidad`).
"""

from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DbSession

from resultarai.adapters.persistence_postgres.models import Message, User
from resultarai.app.identity import get_current_user, get_db
from resultarai.app.use_cases.chat import (
    AgentNotFoundError,
    EmptyFallbackCascadeError,
    EscalationDisabledError,
    EscalationMisconfiguredError,
    FeedbackMessageNotFoundError,
    FeedbackSubmitter,
    MessageEditForbiddenError,
    MessageNotEligibleError,
    MessageNotEligibleForFeedbackError,
    MessageNotFoundError,
    NoEligibleOriginMessageError,
    OriginMessageNotEligibleError,
    ResponseGenerator,
    SessionNotFoundError,
    create_session,
    escalate_session,
    regenerate_response,
    send_turn,
    submit_message_feedback,
)
from resultarai.core.registries import Registries

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
