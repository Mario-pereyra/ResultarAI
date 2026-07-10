"""Consulta de tokens/insercion de un adjunto, compartida entre chat y los endpoints de
consulta (d14-attachments, tarea 6.3 y el soporte de consulta/preview de 8.1/8.3).

`message_attachments` no tiene una columna dedicada "primera insercion": la fila
CRONOLOGICAMENTE MAS ANTIGUA de un `attachment_id` dado (en cualquier mensaje) ES la
insercion truncada canonica (ANEXO §7 punto 4 / P4) -- las inserciones posteriores del
MISMO adjunto (ramas por edicion, reenvios) reutilizan su `inserted_text` byte-identica
en vez de re-truncar. `find_first_insertion` centraliza ese criterio para que tanto la
composicion del mensaje (`app/use_cases/chat/_attachments.py`) como los endpoints de
consulta (`GET /attachments/{id}`, `GET /attachments/{id}/preview`,
`app/api/attachments.py`) usen exactamente el mismo lookup, sin que el router de
adjuntos tenga que importar del bounded context de chat (evita un ciclo de import entre
`app/api/attachments.py` y `app/api/chat.py`).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session as DbSession

from resultarai.adapters.llm_litellm.tokens import count_tokens
from resultarai.adapters.persistence_postgres.models import Attachment, MessageAttachment
from resultarai.adapters.persistence_postgres.models import Session as SessionModel
from resultarai.app.attachments.config import AttachmentsConfig
from resultarai.core.registries import Registries

__all__ = [
    "TokenUsageInfo",
    "describe_token_usage",
    "find_first_insertion",
    "resolve_token_counter_model",
]

# Fallback defensivo cuando no se puede resolver el `model_profile` de la sesion (sesion
# huerfana / perfil desactivado entretanto): LiteLLM igual aproxima con un tokenizer
# generico (ver `adapters/llm_litellm/tokens.py`) -- preferible a fallar un endpoint de
# solo lectura por un dato inconsistente que no es responsabilidad de esta consulta.
_FALLBACK_TOKEN_MODEL = "gpt-4o-mini"


def resolve_token_counter_model(registries: Registries, session: SessionModel | None) -> str:
    """`ModelProfile.model` (id real de LiteLLM) del `model_profile` de `session`.

    `session.model_profile` es el `ModelProfile.id` (p. ej. `deepseek_v4_flash`, ver
    `manifests/model_profiles.yaml`); el tokenizer necesita el `model` real
    (`deepseek/deepseek-v4-flash`). Cae a `_FALLBACK_TOKEN_MODEL` si `session` es `None`
    o el perfil no resuelve en el registro (dato inconsistente).
    """
    if session is None:
        return _FALLBACK_TOKEN_MODEL
    profile = registries.model_profiles.get(session.model_profile)
    return profile.model if profile is not None else _FALLBACK_TOKEN_MODEL


def find_first_insertion(db: DbSession, attachment_id: uuid.UUID) -> MessageAttachment | None:
    """La PRIMERA fila (por `created_at`) de `message_attachments` para este adjunto."""
    stmt = (
        select(MessageAttachment)
        .where(MessageAttachment.attachment_id == attachment_id)
        .order_by(MessageAttachment.created_at.asc())
        .limit(1)
    )
    return db.scalars(stmt).first()


@dataclass(frozen=True)
class TokenUsageInfo:
    """Tokens/% de un adjunto, para `GET /attachments/{id}` y su `/preview` (8.1/8.3).

    `inserted=True`: `token_count`/`included_percent`/`truncated` describen la
    `inserted_text` YA persistida (exacta, ANEXO §7 punto 4). `inserted=False`:
    describen una ESTIMACION sobre `full_text` tal cual quedaria si se enviara ahora
    (ANEXO §3.4) -- todos `None` si todavia no hay extraccion disponible (adjunto no
    `ready`/`blocked` todavia, o `full_text` purgado por retencion, ANEXO §5).
    """

    inserted: bool
    token_count: int | None
    included_percent: int | None
    truncated: bool | None


def describe_token_usage(
    db: DbSession,
    registries: Registries,
    config: AttachmentsConfig,
    attachment: Attachment,
) -> TokenUsageInfo:
    """Resuelve el uso de tokens de `attachment`: insercion real o estimacion (8.1/8.3).

    Devuelve AMBOS `token_count` (unidad Tecnico/Admin) e `included_percent` (unidad
    Funcional) -- ANEXO §3.4: "el conteo de tokens se muestra ... en % para Funcional y
    en tokens para Tecnico/Admin". Decision documentada (a diferencia de
    `telemetry.layer_turn_metadata`, que OCULTA claves enteras por rol porque son datos
    sensibles -- costo, `trace_id`): tokens/% de un adjunto no son sensibles, es la
    MISMA magnitud en dos unidades, asi que el backend devuelve las dos y el cliente
    elige cual mostrar segun el rol. No hay necesidad de gating server-side aqui.
    """
    first_insertion = find_first_insertion(db, attachment.id)
    if first_insertion is not None:
        included_percent: int | None = None
        if attachment.extraction is not None:
            model = resolve_token_counter_model(registries, _session_of(db, attachment))
            full_tokens = count_tokens(attachment.extraction.full_text, model=model)
            if full_tokens > 0:
                included_percent = min(100, round(first_insertion.token_count / full_tokens * 100))
        elif not first_insertion.truncated:
            included_percent = 100
        return TokenUsageInfo(
            inserted=True,
            token_count=first_insertion.token_count,
            included_percent=included_percent,
            truncated=first_insertion.truncated,
        )

    if attachment.extraction is None:
        return TokenUsageInfo(
            inserted=False, token_count=None, included_percent=None, truncated=None
        )

    model = resolve_token_counter_model(registries, _session_of(db, attachment))
    full_tokens = count_tokens(attachment.extraction.full_text, model=model)
    budget = config.token_budget_per_file
    if full_tokens <= budget:
        return TokenUsageInfo(
            inserted=False, token_count=full_tokens, included_percent=100, truncated=False
        )
    provisional_percent = max(1, round(budget / full_tokens * 100))
    return TokenUsageInfo(
        inserted=False,
        token_count=full_tokens,
        included_percent=provisional_percent,
        truncated=True,
    )


def _session_of(db: DbSession, attachment: Attachment) -> SessionModel | None:
    if attachment.session_id is None:
        return None
    return db.get(SessionModel, attachment.session_id)
