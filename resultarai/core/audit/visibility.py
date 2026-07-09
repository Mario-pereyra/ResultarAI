"""Proyeccion de lectura de la Tool call visible (c09-mcp-tools, tareas 3.1/3.2).

El `AuditEvent` (`resultarai.core.audit.models`) es la unica fuente de verdad
append-only. Este modulo NO crea una fuente de verdad paralela: deriva, a partir
de un `AuditEvent` ya existente y del resultado de la invocacion, un registro de
solo lectura pensado para que la UI lo muestre colapsado y expandible
(design/FUNCIONALIDADES.md SS4), y una vista por rol sobre ese mismo registro
(design/FUNCIONALIDADES.md SS4 y SS12).
"""

from __future__ import annotations

import enum
from typing import Any

from pydantic import BaseModel, ConfigDict

from resultarai.core.audit.models import AuditEvent

# Sufijo que marca de forma explicita que el resultado fue truncado para el preview.
_TRUNCATION_SUFFIX = "… [truncado]"

# Largo maximo por defecto del preview del resultado, en caracteres.
_DEFAULT_MAX_PREVIEW_CHARS = 500


class ToolCallStatus(enum.StrEnum):
    """Estado de la Tool call visible, derivado del `effect` del Policy Gate.

    Mapeo: `allow` -> `executed`, `escalate_hitl` -> `pending_approval`,
    `deny` -> `denied`.
    """

    EXECUTED = "executed"
    PENDING_APPROVAL = "pending_approval"
    DENIED = "denied"


# Copys de producto (espanol) para el estado de gobernanza mostrado en la UI.
_STATUS_LABELS: dict[ToolCallStatus, str] = {
    ToolCallStatus.EXECUTED: "ejecutada",
    ToolCallStatus.PENDING_APPROVAL: "en espera de aprobación",
    ToolCallStatus.DENIED: "denegada",
}

# `effect` del AuditEvent -> ToolCallStatus de la Tool call visible.
_EFFECT_TO_STATUS: dict[str, ToolCallStatus] = {
    "allow": ToolCallStatus.EXECUTED,
    "escalate_hitl": ToolCallStatus.PENDING_APPROVAL,
    "deny": ToolCallStatus.DENIED,
}


class ViewerRole(enum.StrEnum):
    """Roles del producto que pueden ver una Tool call visible.

    Valores exactos usados en `manifests/skills/*.yaml` (bloque `visibility.roles`)
    y en `docs/03-glosario-dominio.md`: `admin`, `tecnico`, `funcional`.
    """

    ADMIN = "admin"
    TECNICO = "tecnico"
    FUNCIONAL = "funcional"


class VisibleToolCall(BaseModel):
    """Proyeccion de lectura de una invocacion de Tool, lista para la UI.

    Se muestra colapsada por defecto y expandible (`collapsed_by_default`).
    Es inmutable: se construye una sola vez a partir de un `AuditEvent` y del
    resultado de la invocacion, y no se vuelve a escribir.
    """

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    audit_event_id: str
    tool_name: str
    arguments: dict[str, Any]
    status: ToolCallStatus
    result_preview: str | None
    result_truncated: bool
    duration_ms: int | None
    collapsed_by_default: bool = True


class VisibleToolCallView(BaseModel):
    """Vista renderizada de una `VisibleToolCall` para un rol concreto.

    Misma `VisibleToolCall` (mismo `AuditEvent` de origen) para todos los roles:
    la diferencia es unicamente de presentacion (`render_for_role`).
    """

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    tool_name: str
    status: ToolCallStatus
    status_label: str
    simple_description: str
    parameters: dict[str, Any] | None
    result_preview: str | None
    duration_ms: int | None


def _truncate_result(result_text: str | None, max_preview_chars: int) -> tuple[str | None, bool]:
    """Trunca `result_text` a `max_preview_chars` marcando explicitamente el corte.

    Devuelve `(preview, truncated)`. Si `result_text` es `None` o no excede el
    limite, se devuelve tal cual con `truncated=False`.
    """
    if result_text is None:
        return None, False
    if len(result_text) <= max_preview_chars:
        return result_text, False

    cutoff = max(max_preview_chars - len(_TRUNCATION_SUFFIX), 0)
    return f"{result_text[:cutoff]}{_TRUNCATION_SUFFIX}", True


def project_visible_tool_call(
    event: AuditEvent,
    result_text: str | None,
    duration_ms: int | None,
    max_preview_chars: int = _DEFAULT_MAX_PREVIEW_CHARS,
) -> VisibleToolCall:
    """Proyecta un `AuditEvent` (mas el resultado de la invocacion) a una Tool call visible.

    Funcion pura: no muta `event` (es frozen) ni ningun otro estado. `event.parameters`
    ya llega enmascarado por `create_audit_event`/`_enmask_parameters`; esta funcion no
    vuelve a enmascarar, solo proyecta.
    """
    status = _EFFECT_TO_STATUS[event.effect]
    preview, truncated = _truncate_result(result_text, max_preview_chars)

    return VisibleToolCall(
        audit_event_id=event.id,
        tool_name=event.tool,
        arguments=dict(event.parameters),
        status=status,
        result_preview=preview,
        result_truncated=truncated,
        duration_ms=duration_ms,
    )


def _simple_description(call: VisibleToolCall) -> str:
    """Redacta una descripcion en lenguaje simple, sin jerga ni argumentos crudos."""
    if call.status is ToolCallStatus.PENDING_APPROVAL:
        return f"Se intentó usar «{call.tool_name}»; está en espera de aprobación."
    if call.status is ToolCallStatus.DENIED:
        return f"Se intentó usar «{call.tool_name}»; la acción fue denegada."

    if call.result_preview:
        return f"Se consultó «{call.tool_name}». Resultado: {call.result_preview}"
    return f"Se consultó «{call.tool_name}»."


def render_for_role(call: VisibleToolCall, role: ViewerRole) -> VisibleToolCallView:
    """Renderiza la misma `VisibleToolCall` con la capa de presentacion del rol.

    Funcional: lenguaje simple, sin parametros tecnicos (`parameters is None`).
    Tecnico/Admin: parametros completos (`parameters == call.arguments`).
    El estado de gobernanza (ejecutada/en espera de aprobacion/denegada) es el
    mismo para todos los roles; una escritura escalada nunca se muestra como
    ejecutada.
    """
    parameters = None if role is ViewerRole.FUNCIONAL else dict(call.arguments)

    return VisibleToolCallView(
        tool_name=call.tool_name,
        status=call.status,
        status_label=_STATUS_LABELS[call.status],
        simple_description=_simple_description(call),
        parameters=parameters,
        result_preview=call.result_preview,
        duration_ms=call.duration_ms,
    )
