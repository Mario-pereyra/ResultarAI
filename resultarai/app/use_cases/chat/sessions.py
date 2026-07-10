"""Caso de uso: creacion de sesion de chat con stickiness de model_profile.

d13-chat-conversacion, tarea 1.1. Fija el `model_profile` de una sesion nueva segun
la cascada de fallback (`fallback_cascade`) del Agent Manifest del catalogo, y ya
no lo vuelve a tocar despues: la stickiness ("una sesion vive en un unico
`model_profile`", requirement de `chat-streaming`) la garantiza este caso de uso al
fijarlo una sola vez en la creacion, reforzada ademas a nivel de base de datos por
la FK compuesta `(session_id, model_profile)` de `messages` -> `sessions`
(`uq_sessions_id_model_profile`, `b04-persistencia-postgres`): ningun mensaje
posterior puede colgar de la sesion con un `model_profile` distinto al que se fijo
aqui.

No vive en `core/` (regla dura 1): orquesta Registries (catalogo de manifiestos) y
persistencia (SQLAlchemy), ninguno de los dos permitidos dentro del nucleo.
"""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session as DbSession

from resultarai.adapters.persistence_postgres.models import Session as SessionModel
from resultarai.adapters.persistence_postgres.models import User, get_utc_now
from resultarai.core.registries import Registries

__all__ = [
    "AgentNotFoundError",
    "EmptyFallbackCascadeError",
    "create_session",
]


class AgentNotFoundError(Exception):
    """El agente solicitado no esta catalogado o no es invocable (`status: active`).

    La API traduce este error a 404: desde la perspectiva de quien crea la sesion,
    un agente `draft`/`deprecated` es indistinguible de uno inexistente (no se puede
    iniciar una sesion contra el de todos modos).
    """

    def __init__(self, agent_id: str) -> None:
        super().__init__(f"agente no encontrado o no invocable: {agent_id!r}")
        self.agent_id = agent_id


class EmptyFallbackCascadeError(Exception):
    """El Agent Manifest existe y es invocable pero no declara `fallback_cascade`.

    Sin cascada no hay perfil inicial que fijar por stickiness; la API lo traduce a
    422 (el agente esta mal configurado, no es un problema de la peticion del
    usuario ni de "no encontrado").
    """

    def __init__(self, agent_id: str) -> None:
        super().__init__(
            f"el agente {agent_id!r} no declara fallback_cascade: no hay perfil "
            "inicial que fijar para la sesion"
        )
        self.agent_id = agent_id


def _generate_session_id() -> str:
    """Genera un identificador de sesion unico: prefijo `sess_` + uuid4 hex."""
    return f"sess_{uuid.uuid4().hex}"


def create_session(
    db: DbSession,
    registries: Registries,
    user: User,
    agent_id: str,
) -> SessionModel:
    """Crea una sesion asociada a `agent_id`, fijando su `model_profile` por stickiness.

    Valida que `agent_id` este catalogado y sea invocable (`status: active`) antes de
    crear nada; si no, lanza `AgentNotFoundError` sin tocar la base. El `model_profile`
    inicial es el primer elemento de `fallback_cascade` del Agent Manifest -- si la
    cascada esta vacia, lanza `EmptyFallbackCascadeError` (tambien antes de crear nada).

    No hace `db.commit()`: la transaccion es responsabilidad de quien inyecta `db`
    (el override de `get_db` en la composicion real hace commit al cerrar la
    peticion; los tests que usan `get_db_session()` directamente tambien).
    """
    agent = registries.agents.get_invocable(agent_id)
    if agent is None:
        raise AgentNotFoundError(agent_id)

    if not agent.fallback_cascade:
        raise EmptyFallbackCascadeError(agent_id)

    model_profile = agent.fallback_cascade[0]
    now = get_utc_now()

    session = SessionModel(
        id=_generate_session_id(),
        model_profile=model_profile,
        owner_user_id=user.id,
        agent_id=agent_id,
        last_activity_at=now,
    )
    db.add(session)
    db.flush()
    return session
