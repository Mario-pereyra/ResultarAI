"""Schema del Tool Manifest: gobernanza sobre una tool de un MCP server.

Un Tool Manifest **referencia** una tool de un MCP server (spec oficial MCP,
revision fijada por el change `c09`) por `server` + `tool_name`, y anade la capa de
gobernanza que la spec no cubre: clasificacion lectura/escritura (`risk.operation_type`),
nivel de riesgo (`risk.level`), permisos, seguridad, auditoria y el binding con el
Tool Registry (ver docs/04-manifiestos.md, seccion "Tool Manifest").

**Clasificacion fija por `version` e inmutable en runtime (c09, tarea 2.2).** La
clasificacion lectura/escritura y el nivel de riesgo (`risk`) son inmutables: no hay
mutacion en runtime. Cambiar la clasificacion o el riesgo exige una **nueva `version`**
del Manifest (un PR revisado). El schema lo garantiza con `frozen=True` tanto en el
`ToolManifest` como en sus sub-modelos (`_StrictSubModel`): reasignar
`manifest.risk.operation_type` o `manifest.risk.level` en runtime lanza un
`ValidationError` de pydantic (frozen), nunca una mutacion silenciosa. El `frozen=True` se
acota a este Manifest (el que la spec de `tool-registry-binding` declara inmutable); el
resto de Manifests conservan la config de `BaseManifest`.

**Regla dura 5.** `security.allow_sql_freeform` DEBE ser `false`; un `true` es rechazado
por el validador (jamas SQL libre contra el ERP).
"""

from __future__ import annotations

import enum
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, field_validator

from resultarai.core.manifests.base import BaseManifest, RiskLevel

__all__ = [
    "McpBinding",
    "OperationType",
    "PermissionMode",
    "RiskLevel",
    "ToolAdapter",
    "ToolAudit",
    "ToolEvals",
    "ToolManifest",
    "ToolPermissions",
    "ToolRisk",
    "ToolSecurity",
    "ToolType",
]


class ToolType(enum.StrEnum):
    """Tipo de tool. Solo `mcp_tool` en el conjunto de fabrica (openapi = Etapa P)."""

    MCP_TOOL = "mcp_tool"


class ToolAdapter(enum.StrEnum):
    """Adapter que resuelve la tool en runtime. `mcp` es el de fabrica."""

    MCP = "mcp"


class OperationType(enum.StrEnum):
    """Clasificacion lectura/escritura de la tool (fija por `version`)."""

    READ = "read"
    WRITE = "write"


class PermissionMode(enum.StrEnum):
    """Modo de permiso de la tool."""

    READ_ONLY = "read_only"
    READ_WRITE = "read_write"


# Los enums llegan del YAML como strings; strict=False los admite sin coercion insegura
# (solo valores del enum), igual que StatusField en base.py. El resto sigue estricto.
ToolTypeField = Annotated[ToolType, Field(strict=False)]
ToolAdapterField = Annotated[ToolAdapter, Field(strict=False)]
OperationTypeField = Annotated[OperationType, Field(strict=False)]
RiskLevelField = Annotated[RiskLevel, Field(strict=False)]
PermissionModeField = Annotated[PermissionMode, Field(strict=False)]

# Identificador no vacio (server, tool_name, endpoint_ref, template, spec_revision).
NonEmptyStr = Annotated[str, Field(min_length=1)]


class _StrictSubModel(BaseModel):
    """Base de los sub-modelos del Tool Manifest: strict + extra forbid + frozen.

    Replica la config de `BaseManifest` para que los bloques anidados (`mcp`, `risk`,
    `security`, ...) rechacen tambien coerciones implicitas y claves desconocidas, y anade
    `frozen=True`: la clasificacion (`risk.operation_type`, `risk.level`) y el binding MCP
    quedan inmutables en runtime (c09, tarea 2.2). Reasignar `manifest.risk.operation_type`
    lanza un `ValidationError` de pydantic (frozen), no una mutacion silenciosa; cambiar la
    clasificacion exige una nueva `version` del Manifest (un PR).
    """

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)


class McpBinding(_StrictSubModel):
    """Referencia obligatoria al MCP server: `server` + `tool_name` (spec MCP).

    Omitir `server` o `tool_name` hace fallar la validacion nombrando el binding ausente
    (Field required), porque sin referencia no hay tool que gobernar.
    """

    server: NonEmptyStr
    tool_name: NonEmptyStr
    spec_revision: NonEmptyStr
    endpoint_ref: NonEmptyStr


class ToolRisk(_StrictSubModel):
    """Clasificacion obligatoria y fija por `version`: nivel + lectura/escritura."""

    level: RiskLevelField
    operation_type: OperationTypeField


class ToolPermissions(_StrictSubModel):
    """Permisos de ejecucion de la tool."""

    mode: PermissionModeField
    requires_human_approval: bool


class ToolSecurity(_StrictSubModel):
    """Controles de seguridad. `allow_sql_freeform` DEBE ser false (regla dura 5)."""

    allow_sql_freeform: bool
    allow_dynamic_table_access: bool
    mask_sensitive_fields: bool

    @field_validator("allow_sql_freeform")
    @classmethod
    def _reject_sql_freeform(cls, value: bool) -> bool:
        """Regla dura 5: jamas SQL libre contra el ERP; solo `false` es admisible."""
        if value:
            raise ValueError(
                "regla dura 5: nunca SQL libre contra el ERP; "
                "security.allow_sql_freeform debe ser false"
            )
        return value


class ToolAudit(_StrictSubModel):
    """Que se registra en el audit log al invocar la tool."""

    log_request: bool
    log_response_summary: bool
    log_user: bool
    log_tenant: bool


class ToolEvals(_StrictSubModel):
    """Eval placeholder obligatorio: referencia el template de eval de la tool."""

    status: NonEmptyStr
    template: NonEmptyStr


class ToolManifest(BaseManifest):
    """Manifiesto de una tool: referencia MCP + capa de gobernanza.

    Hereda `id`, `status` y `version` de `BaseManifest` (strict + extra forbid). La
    referencia MCP (`mcp`) y la clasificacion (`risk`) son obligatorias; el riesgo y la
    clasificacion lectura/escritura quedan fijos por `version` (cambiarlos = nueva
    version = PR). `security.allow_sql_freeform: true` es rechazado por regla dura 5.

    Override local de `model_config` con `frozen=True` (c09, tarea 2.2): a diferencia de
    los otros 5 Manifests (que heredan la config de `BaseManifest`), el ToolManifest es
    inmutable en runtime porque su clasificacion es autoritativa para la gobernanza y no
    debe poder rebajarse por mutacion. Reasignar cualquier campo (p. ej. `manifest.risk`)
    lanza un `ValidationError` de pydantic (frozen).
    """

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    name: NonEmptyStr
    type: ToolTypeField
    adapter: ToolAdapterField
    mcp: McpBinding
    risk: ToolRisk
    permissions: ToolPermissions
    security: ToolSecurity
    audit: ToolAudit
    evals: ToolEvals
