"""Composicion server-side del mensaje con adjuntos (d14-attachments, tareas 6.2-6.3).

Modulo interno (prefijo `_`, mismo criterio que `_branching.py`/`_marker.py`): expone la
logica de "adjuntar" que `turns.py` (camino sincrono) y `streaming.py` (SSE) reutilizan
sin duplicarla, siguiendo el pipeline de ANEXO §8 pasos [7]-[9]:

- `compose_message_with_attachments` (tarea 6.3): dado el texto del usuario y los
  `attachment_id` en estado `listo` del borrador (`session_id` fijado,
  `message_id IS NULL` hasta enviarse -- ver `app/attachments/upload.py`), produce
  `contenido = texto + "\\n\\n" + wrap_extraction(inserted_text) por cada adjunto, AL
  FINAL`, validando el gate `is_sendable()` y el presupuesto de tokens por mensaje.
- `persist_attachment_links`: una vez que el `Message` del usuario esta `flush()`-eado
  (existe `message_id`), inserta las filas de `message_attachments` y fija
  `Attachment.message_id` en la PRIMERA insercion de cada adjunto (deja de contar como
  "borrador", `app/attachments/upload.py::count_pending_attachments`).
- `evaluate_quota_before_generation` (ANEXO §8 paso [9]): el seam documentado donde
  `d16-cuotas-liberaciones` debe enganchar la evaluacion REAL de cuota, con el mensaje ya
  compuesto (texto + adjuntos) y ANTES de llamar al generador -- hoy es un passthrough.
- `request_attachment_fragment` (tarea 6.2, "pedir otra parte"): corta un fragmento
  NUEVO del `full_text` ya almacenado (sin re-parsear el binario ni re-truncar la
  insercion original) y lo inserta como mensaje nuevo, append-only.

**Truncado UNA VEZ por adjunto, no por mensaje (P4 + ANEXO §7 punto 4):** la clave de
"ya truncado" es el `attachment_id`, no el par `(message_id, attachment_id)`. La PRIMERA
vez que un adjunto se inserta en CUALQUIER mensaje de la sesion, `truncate_for_insertion`
corre con el texto de ESE mensaje para la relevancia y el resultado queda fijo para
siempre (`app/attachments/insertion.py::find_first_insertion`). Si el mismo adjunto
vuelve a aparecer en un mensaje posterior -- tipicamente una rama por edicion, que puede
traer un texto de usuario DISTINTO -- se reutiliza esa `inserted_text` byte-identica sin
volver a evaluar relevancia: eso es precisamente lo que garantiza que las ramas compartan
prefijo cacheable (ANEXO §7 punto 4, "ramas comparten extraccion").

**Hueco documentado (bloqueante para produccion, no para estas tareas):** para que
`compose_message_with_attachments` funcione necesita `Attachment.extraction` poblado
(`extraction_id` fijado + fila en `extractions`). La tarea `7.1` (dedup + persistencia de
`full_text`, `tasks.md` de este change) todavia NO esta implementada: el endpoint de
subida (`app/api/attachments.py::upload_attachment_endpoint`) hoy solo llega a
`create_attachment` (estado `uploaded`) y ningun camino de produccion invoca
`extract_attachment`/persiste `Extraction` todavia (`extract_attachment` solo se ejercita
en tests unitarios, `tests/app/attachments/test_extraction.py`). Hasta que `7.1` cablee
eso, un adjunto real subido por HTTP nunca llega a `attachment.extraction != None` y esta
composicion levantaria `AttachmentExtractionMissingError` para CUALQUIER adjunto real.
Los tests de estas tareas (6.1-6.3) construyen `Attachment`+`Extraction` directamente en
la base (mismo patron que `tests/app/attachments/test_confirm_test_data.py`), simulando
lo que `7.1` dejara wireado.
"""

from __future__ import annotations

import datetime
import uuid
from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy.orm import Session as DbSession

from resultarai.adapters.persistence_postgres.models import (
    Attachment,
    Message,
    MessageAttachment,
    User,
    get_utc_now,
)
from resultarai.adapters.persistence_postgres.models import Session as SessionModel
from resultarai.app.attachments.config import AttachmentsConfig
from resultarai.app.attachments.data_scan import is_sendable
from resultarai.app.attachments.errors import AttachmentExtractionMissingError
from resultarai.app.attachments.insertion import find_first_insertion, resolve_token_counter_model
from resultarai.app.attachments.spotlight import wrap_extraction
from resultarai.app.attachments.truncation import (
    find_section_body,
    truncate_for_insertion,
    truncate_fragment,
)
from resultarai.app.use_cases.chat._branching import find_active_leaf
from resultarai.core.ports.extraction import AttachmentKind
from resultarai.core.registries import Registries

__all__ = [
    "AttachmentLink",
    "AttachmentNotFoundError",
    "AttachmentNotSendableError",
    "ComposedMessage",
    "MessageTokenBudgetExceededError",
    "SectionNotFoundError",
    "compose_message_with_attachments",
    "evaluate_quota_before_generation",
    "persist_attachment_links",
    "request_attachment_fragment",
]


class AttachmentNotFoundError(Exception):
    """`attachment_id` no existe, no pertenece al usuario actual o no es de esta sesion.

    Un solo `error_code`/HTTP para ambos motivos (mismo criterio anti-filtrado de
    existencia que `SessionNotFoundError`/`MessageEditForbiddenError` de `turns.py`).
    """

    error_code = "attachment_not_found"

    def __init__(self, attachment_id: uuid.UUID) -> None:
        super().__init__(f"adjunto no encontrado o ajeno: {attachment_id!r}")
        self.attachment_id = attachment_id


class AttachmentNotSendableError(Exception):
    """`is_sendable(attachment)` es `False`: bloqueado (N3), N2 sin confirmar, o no `ready`."""

    error_code = "attachment_not_sendable"

    def __init__(self, attachment_id: uuid.UUID, status: str) -> None:
        super().__init__(f"adjunto no enviable (status={status!r}): {attachment_id!r}")
        self.attachment_id = attachment_id
        self.status = status


class MessageTokenBudgetExceededError(Exception):
    """La suma de tokens de los adjuntos del mensaje supera el presupuesto (ANEXO §3.1).

    NO trunca mas: es un rechazo del envio con un error tipado accionable (decision de
    la tarea 6.3, distinta del truncado POR ARCHIVO de la 6.1, que si trunca). El
    presupuesto por archivo (12k default) ya se aplico a cada adjunto individualmente
    ANTES de sumar; si la suma de esos totales ya truncados sigue por encima del
    presupuesto por mensaje (24k default -- "maximo 2 archivos llenos por turno",
    ANEXO §3.1), el unico remedio es que el usuario quite algun adjunto.
    """

    error_code = "message_token_budget_exceeded"

    def __init__(self, *, total_tokens: int, budget_tokens: int) -> None:
        super().__init__(f"presupuesto de mensaje excedido: {total_tokens} > {budget_tokens}")
        self.total_tokens = total_tokens
        self.budget_tokens = budget_tokens


class SectionNotFoundError(Exception):
    """La seccion pedida ("pedir otra parte", tarea 6.2) no existe en el `full_text`."""

    error_code = "section_not_found"

    def __init__(self, attachment_id: uuid.UUID, section_title: str) -> None:
        super().__init__(f"seccion {section_title!r} no encontrada en {attachment_id!r}")
        self.attachment_id = attachment_id
        self.section_title = section_title


@dataclass(frozen=True)
class AttachmentLink:
    """Una insercion de adjunto lista para persistir en `message_attachments`."""

    attachment: Attachment
    inserted_text: str
    token_count: int
    truncated: bool
    is_first_insertion: bool


@dataclass(frozen=True)
class ComposedMessage:
    """Resultado de componer el contenido del mensaje con sus adjuntos (tarea 6.3).

    `content` es lo que se persiste como `Message.content`: texto del usuario +
    `wrap_extraction(...)` de cada adjunto, AL FINAL, en el orden de `attachment_ids`.
    Sin adjuntos, `content == text` (paso-a-traves, ningun cambio de comportamiento
    respecto de d13). `links` queda vacio en ese mismo caso.
    """

    content: str
    links: list[AttachmentLink]
    total_attachment_tokens: int


def _kind_of(detected_type: str | None) -> AttachmentKind:
    """Traduce `Attachment.detected_type` (string persistido, `FileCategory.value`) a
    `AttachmentKind` (el tipo que espera `truncate_for_insertion`)."""
    mapping = {
        "excel": AttachmentKind.SPREADSHEET,
        "csv": AttachmentKind.SPREADSHEET,
        "pdf": AttachmentKind.PDF,
        "docx": AttachmentKind.DOCX,
        "text": AttachmentKind.TEXT,
        "code": AttachmentKind.CODE,
        "log": AttachmentKind.LOG,
    }
    return mapping.get(detected_type or "", AttachmentKind.TEXT)


def _require_owned_attachment(
    db: DbSession, user: User, session: SessionModel, attachment_id: uuid.UUID
) -> Attachment:
    attachment = db.get(Attachment, attachment_id)
    if (
        attachment is None
        or attachment.uploaded_by != str(user.id)
        or attachment.session_id != session.id
    ):
        raise AttachmentNotFoundError(attachment_id)
    if not is_sendable(attachment):
        raise AttachmentNotSendableError(attachment_id, attachment.status)
    return attachment


def compose_message_with_attachments(
    db: DbSession,
    registries: Registries,
    config: AttachmentsConfig,
    user: User,
    session: SessionModel,
    text: str,
    attachment_ids: Sequence[uuid.UUID],
) -> ComposedMessage:
    """Compone `texto + wrap_extraction(inserted_text) por adjunto, AL FINAL` (tarea 6.3).

    Para cada `attachment_id` (deduplicados preservando el orden de llegada):

    1. Verifica pertenencia (mismo usuario Y misma sesion que `session`) y el gate de
       envio `is_sendable()` -- bloqueado (N3) o N2 sin confirmar rechaza TODO el envio,
       sin componer nada parcial (`AttachmentNotSendableError`).
    2. Si el adjunto YA tiene una insercion previa en la sesion (cualquier mensaje,
       `find_first_insertion`), reutiliza esa `inserted_text`/`token_count`/`truncated`
       BYTE-IDENTICA (P4/ANEXO §7 punto 4) -- nunca vuelve a truncar.
    3. Si es la PRIMERA vez, corre `truncate_for_insertion` con el texto de ESTE mensaje
       para la relevancia (design.md decision 8: "al componer el mensaje, cuando ya
       existe el texto del usuario").

    Al final valida el presupuesto POR MENSAJE (`config.token_budget_per_message`, suma
    de `token_count` de todos los adjuntos): si lo excede, levanta
    `MessageTokenBudgetExceededError` SIN haber tocado la base de datos (esta funcion es
    de solo lectura; los `INSERT` los hace `persist_attachment_links`, invocada por el
    llamador solo si esta funcion no levanto nada).
    """
    if not attachment_ids:
        return ComposedMessage(content=text, links=[], total_attachment_tokens=0)

    model = resolve_token_counter_model(registries, session)

    seen: set[uuid.UUID] = set()
    ordered_ids: list[uuid.UUID] = []
    for attachment_id in attachment_ids:
        if attachment_id not in seen:
            seen.add(attachment_id)
            ordered_ids.append(attachment_id)

    links: list[AttachmentLink] = []
    wrapped_chunks: list[str] = []
    total_tokens = 0

    for attachment_id in ordered_ids:
        attachment = _require_owned_attachment(db, user, session, attachment_id)

        existing = find_first_insertion(db, attachment_id)
        if existing is not None:
            inserted_text = existing.inserted_text
            token_count = existing.token_count
            truncated = existing.truncated
            is_first = False
        else:
            if attachment.extraction is None:
                raise AttachmentExtractionMissingError(attachment_id=str(attachment_id))
            result = truncate_for_insertion(
                attachment.extraction.full_text,
                kind=_kind_of(attachment.detected_type),
                budget_tokens=config.token_budget_per_file,
                user_text=text,
                model=model,
            )
            inserted_text = result.text
            token_count = result.token_count
            truncated = result.truncated
            is_first = True

        spotlighted = wrap_extraction(
            inserted_text,
            filename=attachment.original_name,
            file_type=attachment.detected_type or "",
        )
        wrapped_chunks.append(spotlighted.text)
        total_tokens += token_count
        links.append(
            AttachmentLink(
                attachment=attachment,
                inserted_text=inserted_text,
                token_count=token_count,
                truncated=truncated,
                is_first_insertion=is_first,
            )
        )

    if total_tokens > config.token_budget_per_message:
        raise MessageTokenBudgetExceededError(
            total_tokens=total_tokens, budget_tokens=config.token_budget_per_message
        )

    content = text + "\n\n" + "\n\n".join(wrapped_chunks)
    return ComposedMessage(content=content, links=links, total_attachment_tokens=total_tokens)


def persist_attachment_links(
    db: DbSession,
    message_id: uuid.UUID,
    composed: ComposedMessage,
    *,
    now: datetime.datetime | None = None,
) -> None:
    """Persiste `message_attachments` y fija `Attachment.message_id` en la 1ra insercion.

    Se llama DESPUES de `db.flush()` del `Message` de usuario (necesita `message_id`
    real). No hace `db.commit()` -- misma convencion que el resto de casos de uso de
    chat (`turns.py`/`streaming.py`), el commit es responsabilidad del llamador.
    """
    timestamp = now or get_utc_now()
    for link in composed.links:
        db.add(
            MessageAttachment(
                message_id=message_id,
                attachment_id=link.attachment.id,
                inserted_text=link.inserted_text,
                token_count=link.token_count,
                truncated=link.truncated,
                created_at=timestamp,
            )
        )
        if link.is_first_insertion:
            link.attachment.message_id = message_id
    db.flush()


def evaluate_quota_before_generation(*, session: SessionModel, composed: ComposedMessage) -> None:
    """Punto de evaluacion de cuota (`d16-cuotas-liberaciones`), DESPUES de componer el
    mensaje completo y ANTES de llamar al generador (ANEXO §8 paso [9]: "cuota ADR-0007
    evaluada con el mensaje completo ANTES de llamar al LLM").

    HOY es un passthrough deliberado: `d16` (ver `docs/07-roadmap.md`) todavia no existe
    como change, y el gateway (`b05`) tampoco emite un 402 real hoy -- la señal `QUOTA`
    que hoy consume el frontend es una heuristica de TRANSPORTE sobre un `402` que este
    backend NO emite (ver `openspec/BACKLOG-DESCUBRIMIENTOS.md`, nota de d13 tareas
    6.1/6.2). Este seam existe para que `d16` tenga un UNICO punto de enganche
    documentado: evaluar la cuota de sesion con el costo REAL del turno (texto del
    usuario + adjuntos ya compuestos y truncados -- ANEXO §3.1, "el costo del adjunto se
    re-paga en CADA turno siguiente") antes de gastar una llamada al LLM.
    `session`/`composed` ya se reciben con esa forma para que la firma no cambie cuando
    `d16` la implemente de verdad (solo cambia el cuerpo, de `pass` a la evaluacion
    real -- posiblemente levantando su propia excepcion tipada, hoy inexistente).
    """
    return None


def request_attachment_fragment(
    db: DbSession,
    registries: Registries,
    config: AttachmentsConfig,
    user: User,
    session: SessionModel,
    attachment_id: uuid.UUID,
    section_title: str,
    *,
    now: datetime.datetime | None = None,
) -> Message:
    """ "Pedir otra parte": corta un fragmento NUEVO del `full_text` ya almacenado y lo
    inserta como mensaje nuevo, append-only (tarea 6.2, ANEXO §3.2 "el usuario la pide y
    el sistema inserta OTRO fragmento del mismo archivo almacenado como nuevo mensaje").

    NO re-parsea el binario (usa `Attachment.extraction.full_text`, ya persistido) ni
    re-trunca la insercion ORIGINAL (esa fila de `message_attachments`, si existe,
    permanece intacta -- append-only). El fragmento entra como el contenido COMPLETO de
    un mensaje de rol `user` nuevo -- consistente con P1 ("el archivo nunca viaja al LLM;
    viaja su extraccion") -- envuelto igual que cualquier insercion (`wrap_extraction`,
    spotlighting anti-injection ANEXO §4.3), colgado del leaf de la rama activa (mismo
    encadenado que un turno normal, `_branching.find_active_leaf`).

    El fragmento se acota al MISMO presupuesto por archivo (`config.token_budget_per_file`)
    por si la seccion pedida sigue siendo enorme -- usa `truncate_fragment` (siempre
    head+tail generico, nunca consciente-de-estructura: la seccion ya fue elegida
    explicitamente por titulo, ver su docstring en `truncation.py`).

    El disparador CONVERSACIONAL completo (que el agente ofrezca esto, o que el usuario
    lo pida en lenguaje natural y el runtime lo traduzca a esta llamada) llega con el
    runtime (`b06-runtime-grafos`, fuera de alcance de `d14`); esta funcion es la
    OPERACION que ese disparador invocara -- ver tambien el endpoint delgado
    `POST /api/sessions/{session_id}/attachments/{attachment_id}/fragment` en
    `app/api/chat.py`.
    """
    attachment = _require_owned_attachment(db, user, session, attachment_id)
    if attachment.extraction is None:
        raise AttachmentExtractionMissingError(attachment_id=str(attachment_id))

    fragment_body = find_section_body(attachment.extraction.full_text, section_title)
    if fragment_body is None:
        raise SectionNotFoundError(attachment_id, section_title)

    model = resolve_token_counter_model(registries, session)
    result = truncate_fragment(
        fragment_body, budget_tokens=config.token_budget_per_file, model=model
    )

    spotlighted = wrap_extraction(
        result.text,
        filename=attachment.original_name,
        file_type=attachment.detected_type or "",
    )

    parent = find_active_leaf(db, session.id)
    message = Message(
        session_id=session.id,
        parent_id=parent.id if parent is not None else None,
        role="user",
        content=spotlighted.text,
        model_profile=session.model_profile,
    )
    db.add(message)
    db.flush()

    timestamp = now or get_utc_now()
    db.add(
        MessageAttachment(
            message_id=message.id,
            attachment_id=attachment.id,
            inserted_text=result.text,
            token_count=result.token_count,
            truncated=result.truncated,
            created_at=timestamp,
        )
    )
    db.flush()
    return message
