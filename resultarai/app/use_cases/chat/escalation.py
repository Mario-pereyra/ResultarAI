"""Caso de uso de chat: escalación manual a un perfil de mayor capacidad.

d13-chat-conversacion, tarea 1.8. Implementa la confirmación explícita del usuario
tras un evento de escalación (tarea 1.4): `escalate_session` ES esa confirmación --
nunca se auto-invoca desde `streaming.py` ni desde ningún otro camino ("El sistema
SHALL NUNCA crear la sesión/rama escalada sin esa confirmación explícita del
usuario", requirement "Escalación manual crea una sesión/rama nueva con el perfil
configurado" de `chat-streaming`).

**Decisión 5 de `design.md` -- sesión nueva enlazada, no rama en la misma sesión.**
Coherente con la stickiness de `model_profile` (`b04`/`b05`: una sesión vive en un
único perfil): escalar no puede ser una rama de la sesión origen porque eso
violaría la FK compuesta `(session_id, model_profile)` de `messages` ->
`sessions`. La sesión escalada usa `forked_from_id` (columna ya existente desde
`b04`) como el enlace origen -> destino; el enlace inverso (destino -> origen, para
la nota-enlace bidireccional de la vista 08) se DERIVA consultando `Session` por
`forked_from_id == origin_session_id` -- no hace falta una columna nueva en el
sentido contrario.

**Siembra sin respuesta del agente.** La sesión escalada queda sembrada con un
único mensaje de usuario -- el re-planteo -- y NADA más: ningún mensaje de agente
se genera aquí. `design.md` (decisión 5) es explícito en que la sesión escalada
"no hereda el historial literal, solo un resumen del contexto"; esta tarea
implementa la versión mínima de ese re-planteo (el texto literal del mensaje de
usuario de origen, sin resumir -- resumir requeriría invocar un modelo, fuera de
alcance de un endpoint que debe responder sin llamar a ningún LLM). La UI navega a
la sesión nueva ya con ese mensaje visible y es quien decide cuándo disparar la
generación de la respuesta (turno normal contra `POST
.../messages`/`.../messages/stream`), igual que si el usuario lo hubiera escrito a
mano.

No vive en `core/` (regla dura 1): orquesta Registries (catálogo de manifiestos) y
persistencia (SQLAlchemy), ninguno de los dos permitido dentro del núcleo.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from resultarai.adapters.persistence_postgres.models import Message, User, get_utc_now
from resultarai.adapters.persistence_postgres.models import Session as SessionModel
from resultarai.app.use_cases.chat._branching import (
    ancestor_chain,
    find_active_leaf,
    find_owned_session,
)
from resultarai.app.use_cases.chat.turns import SessionNotFoundError
from resultarai.core.registries import Registries

__all__ = [
    "EscalationDisabledError",
    "EscalationMisconfiguredError",
    "EscalationResult",
    "NoEligibleOriginMessageError",
    "OriginMessageNotEligibleError",
    "SessionNotFoundError",
    "escalate_session",
]

# Claves de `Message.turn_metadata` del mensaje de usuario SEMBRADO en la sesión
# escalada (ver `_find_existing_escalation`): reutiliza la columna JSONB ya
# existente desde la tarea 1.5 (hoy poblada solo en mensajes `assistant` por
# `streaming.py`; el schema no restringe su uso a un rol específico).
_ORIGIN_SESSION_KEY = "escalation_origin_session_id"
_ORIGIN_MESSAGE_KEY = "escalation_origin_message_id"


class EscalationDisabledError(Exception):
    """El Agent Manifest de la sesión no tiene la escalación habilitada.

    Cubre también el caso de una sesión sin `agent_id` resoluble (agente
    desconocido/no invocable): sin agente no hay forma de confirmar que la
    escalación está habilitada, así que se trata igual que deshabilitada -- mismo
    criterio conservador que `escalation_enabled` en `streaming.py`.
    """

    def __init__(self, agent_id: str | None) -> None:
        super().__init__(f"la escalación está deshabilitada para el agente: {agent_id!r}")
        self.agent_id = agent_id


class EscalationMisconfiguredError(Exception):
    """`escalation.enabled` es `true` pero `escalation.target_profile` es `None`.

    Error de configuración del agente, no de la petición del usuario: se traduce a
    422 (mismo criterio que `EmptyFallbackCascadeError` de `sessions.py`).
    """

    def __init__(self, agent_id: str) -> None:
        super().__init__(
            f"el agente {agent_id!r} tiene la escalación habilitada pero no declara "
            "escalation.target_profile: no hay perfil de destino que fijar"
        )
        self.agent_id = agent_id


class OriginMessageNotEligibleError(Exception):
    """`origin_message_id` no referencia un mensaje de usuario de la sesión origen."""

    def __init__(self, message_id: uuid.UUID) -> None:
        super().__init__(
            f"origin_message_id no corresponde a un mensaje de usuario de esta "
            f"sesión: {message_id!r}"
        )
        self.message_id = message_id


class NoEligibleOriginMessageError(Exception):
    """La sesión origen no tiene ningún mensaje de usuario para re-plantear.

    Solo ocurre sin `origin_message_id` explícito, sobre una sesión sin mensajes
    todavía (caso de borde: no debería alcanzarse en el flujo real de UI, que solo
    ofrece "Continuar con Pro" tras un evento de escalación, el cual solo puede
    ocurrir después de al menos un turno).
    """

    def __init__(self, session_id: str) -> None:
        super().__init__(
            f"la sesión {session_id!r} no tiene ningún mensaje de usuario que re-plantear"
        )
        self.session_id = session_id


@dataclass(frozen=True)
class EscalationResult:
    """Resultado de `escalate_session`: ambas sesiones, el mensaje sembrado y si se
    creó de cero o se devolvió una escalación ya existente (idempotencia).
    """

    escalated_session: SessionModel
    origin_session: SessionModel
    seeded_message: Message
    created: bool


def _generate_session_id() -> str:
    """Genera un identificador de sesión único: prefijo `sess_` + uuid4 hex.

    Duplica deliberadamente el helper homónimo (privado) de `sessions.py` en vez de
    importarlo: es una función de una línea sin estado compartido, y mantener este
    módulo sin depender de un símbolo con prefijo `_` de otro módulo evita acoplar
    dos casos de uso por un detalle de implementación que ninguno de los dos
    expone en su `__all__`.
    """
    return f"sess_{uuid.uuid4().hex}"


def _resolve_origin_message(
    db: DbSession, session_id: str, origin_message_id: uuid.UUID | None
) -> Message:
    """Resuelve el mensaje de usuario a re-plantear en la sesión escalada.

    Con `origin_message_id` explícito: debe ser un mensaje de rol `user` de esta
    misma sesión (`OriginMessageNotEligibleError` en cualquier otro caso, incluido
    "no existe"). Sin él: el último mensaje de usuario de la rama activa (mismos
    helpers de `_branching.py` que usan `turns.py`/`streaming.py` para la misma
    noción de "rama activa") -- si el leaf de la rama activa es un mensaje de
    agente (caso normal: la respuesta que disparó el evento de escalación), se sube
    por la cadena de ancestros hasta el último mensaje de usuario.
    """
    if origin_message_id is not None:
        message = db.get(Message, origin_message_id)
        if message is None or message.session_id != session_id or message.role != "user":
            raise OriginMessageNotEligibleError(origin_message_id)
        return message

    leaf = find_active_leaf(db, session_id)
    if leaf is None:
        raise NoEligibleOriginMessageError(session_id)
    if leaf.role == "user":
        return leaf
    for message in reversed(ancestor_chain(db, leaf)):
        if message.role == "user":
            return message
    raise NoEligibleOriginMessageError(session_id)


def _find_existing_escalation(
    db: DbSession, origin_session_id: str, origin_message_id: uuid.UUID
) -> tuple[SessionModel, Message] | None:
    """Idempotencia server-side (soporta la tarea 5.3 de UI: doble clic/doble
    pestaña sobre "Continuar con Pro").

    **Clave de idempotencia elegida:** `(forked_from_id == origin_session_id,
    seed.turn_metadata["escalation_origin_message_id"] == str(origin_message_id))`.
    No alcanza con `forked_from_id` solo: `Session` no tiene ninguna columna para
    "qué turno específico de la sesión origen se re-planteó" -- una misma sesión
    origen puede escalar más de un turno distinto a lo largo de su vida (dos
    respuestas distintas, cada una con su propio evento de escalación), y cada una
    de esas escalaciones debe ser una sesión escalada DISTINTA, no colisionar entre
    sí. Por eso el mensaje sembrado (root de la sesión escalada, `parent_id is
    None`) guarda el `id` del mensaje de origen re-planteado en su
    `turn_metadata` -- columna JSONB ya existente, sin migración nueva.
    """
    candidates = (
        db.execute(select(SessionModel).where(SessionModel.forked_from_id == origin_session_id))
        .scalars()
        .all()
    )
    target = str(origin_message_id)
    for candidate in candidates:
        seed = (
            db.execute(
                select(Message)
                .where(Message.session_id == candidate.id, Message.parent_id.is_(None))
                .order_by(Message.created_at.asc(), Message.id.asc())
                .limit(1)
            )
            .scalars()
            .first()
        )
        if seed is None or not seed.turn_metadata:
            continue
        if seed.turn_metadata.get(_ORIGIN_MESSAGE_KEY) == target:
            return candidate, seed
    return None


def escalate_session(
    db: DbSession,
    registries: Registries,
    user: User,
    session_id: str,
    origin_message_id: uuid.UUID | None = None,
) -> EscalationResult:
    """Escala manualmente `session_id` a una sesión nueva con el perfil configurado.

    Orden de validación (todas ANTES de crear nada, en este orden):
    1. La sesión existe y pertenece a `user` (`SessionNotFoundError` -> 404).
    2. El Agent Manifest de la sesión tiene `escalation.enabled: true`
       (`EscalationDisabledError` -> 403) -- ver docstring de módulo, esta llamada
       ES la confirmación explícita que exige la spec.
    3. `escalation.target_profile` está configurado (`EscalationMisconfiguredError`
       -> 422).
    4. `origin_message_id` (si vino) referencia un mensaje de usuario propio de la
       sesión, o hay un último mensaje de usuario en la rama activa que resolver
       (`OriginMessageNotEligibleError`/`NoEligibleOriginMessageError` -> 422).

    Solo después de las cuatro validaciones se busca una escalación ya existente
    (idempotencia, ver `_find_existing_escalation`) y, si no hay ninguna, se crea
    la sesión nueva (`forked_from_id` = sesión origen) sembrada con un único
    mensaje de usuario -- el re-planteo -- sin generar ninguna respuesta de agente
    (ver docstring de módulo).
    """
    origin_session = find_owned_session(db, user, session_id)
    if origin_session is None:
        raise SessionNotFoundError(session_id)

    agent = (
        registries.agents.get_invocable(origin_session.agent_id)
        if origin_session.agent_id
        else None
    )
    if agent is None or not agent.escalation.enabled:
        raise EscalationDisabledError(origin_session.agent_id)

    target_profile = agent.escalation.target_profile
    if not target_profile:
        raise EscalationMisconfiguredError(agent.id)

    origin_message = _resolve_origin_message(db, session_id, origin_message_id)

    existing = _find_existing_escalation(db, session_id, origin_message.id)
    if existing is not None:
        escalated_session, seeded_message = existing
        return EscalationResult(
            escalated_session=escalated_session,
            origin_session=origin_session,
            seeded_message=seeded_message,
            created=False,
        )

    now = get_utc_now()
    escalated_title = f"{origin_session.title} (Pro)" if origin_session.title else None

    escalated_session = SessionModel(
        id=_generate_session_id(),
        model_profile=target_profile,
        owner_user_id=user.id,
        agent_id=origin_session.agent_id,
        forked_from_id=origin_session.id,
        title=escalated_title,
        last_activity_at=now,
    )
    db.add(escalated_session)
    db.flush()

    seeded_message = Message(
        session_id=escalated_session.id,
        parent_id=None,
        role="user",
        content=origin_message.content,
        model_profile=escalated_session.model_profile,
        turn_metadata={
            _ORIGIN_SESSION_KEY: origin_session.id,
            _ORIGIN_MESSAGE_KEY: str(origin_message.id),
        },
    )
    db.add(seeded_message)
    db.flush()

    return EscalationResult(
        escalated_session=escalated_session,
        origin_session=origin_session,
        seeded_message=seeded_message,
        created=True,
    )
