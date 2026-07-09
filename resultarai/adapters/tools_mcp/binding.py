"""Binding entre el `ToolManifest` (Tool Registry, `a02`) y una Tool de un MCP Server.

Materializa el eslabon "solo lo declarado existe" (regla dura 6) y la clasificacion
autoritativa e inmutable del `ToolManifest` (Decisions 3 y 5 de
`openspec/changes/c09-mcp-tools/design.md`):

- `resolve_tool_binding` usa `ToolRegistry.get_invocable`: SOLO los manifiestos con
  `status: active` existen para el runtime. Una Tool que el server publique en
  `tools/list` pero sin `ToolManifest` activo devuelve `None` -> no es invocable, NO se
  consulta al Policy Gate y NO se emite `tools/call`.
- `ResolvedToolBinding` lee `operation_type` y `risk_level` EXCLUSIVAMENTE del manifiesto
  por `version`; las `annotations` del descriptor del server (no confiables, spec MCP
  Tool Safety) NUNCA entran aqui. El binding es frozen: reasignar su clasificacion en
  runtime lanza un `ValidationError` de pydantic.
- `validate_binding_against_server` es la validacion cruzada que se corre al pasar el
  manifiesto a `active` (ciclo `draft -> validated -> active`, ver
  `resultarai.core.manifests.lifecycle.validate_status_transition`): comprueba que el
  `tool_name` del manifiesto exista en el `tools/list` real del server.

Vive en el adapter (no en `core/`) porque depende del cliente/sesion MCP; `core/` no
importa MCP (import-linter).
"""

from __future__ import annotations

from collections.abc import Collection

from pydantic import BaseModel, ConfigDict

from resultarai.adapters.tools_mcp.session import McpToolSession
from resultarai.adapters.tools_mcp.transports import TransportConfig
from resultarai.core.manifests.base import RiskLevel
from resultarai.core.manifests.tool import OperationType, ToolManifest
from resultarai.core.registries.loader import ToolRegistry

__all__ = [
    "BindingValidationError",
    "ResolvedToolBinding",
    "resolve_tool_binding",
    "validate_binding_against_live_server",
    "validate_binding_against_server",
]


class ResolvedToolBinding(BaseModel):
    """Binding resuelto de una Tool: server + tool_name + clasificacion, todo del manifiesto.

    Frozen (pydantic): `operation_type` y `risk_level` se leen del `ToolManifest` por
    `version` y no pueden mutarse en runtime -- reasignar `binding.operation_type` lanza un
    `ValidationError` de pydantic (c09, tarea 2.2). Las `annotations` del descriptor del
    server (no confiables, spec MCP Tool Safety) NUNCA entran aqui: la gobernanza usa
    siempre esta clasificacion, no la que anuncie el server.
    """

    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)

    manifest_id: str
    manifest_version: str
    server: str
    tool_name: str
    endpoint_ref: str
    operation_type: OperationType
    risk_level: RiskLevel

    @classmethod
    def from_manifest(cls, manifest: ToolManifest) -> ResolvedToolBinding:
        """Construye el binding leyendo server, tool_name y clasificacion del manifiesto.

        Toda la informacion sale del `ToolManifest`: el binding nunca deriva nada del
        descriptor del server.
        """
        return cls(
            manifest_id=manifest.id,
            manifest_version=manifest.version,
            server=manifest.mcp.server,
            tool_name=manifest.mcp.tool_name,
            endpoint_ref=manifest.mcp.endpoint_ref,
            operation_type=manifest.risk.operation_type,
            risk_level=manifest.risk.level,
        )


def resolve_tool_binding(tool_id: str, tool_registry: ToolRegistry) -> ResolvedToolBinding | None:
    """Resuelve `tool_id` a un `ResolvedToolBinding` si existe un `ToolManifest` `active`.

    Usa `tool_registry.get_invocable`: solo los manifiestos `status: active` existen para
    el runtime. `None` significa que la Tool NO existe para el runtime (sin manifiesto
    activo): no es invocable, no se consulta al Policy Gate y no se emite `tools/call`
    (deny-by-default a nivel de registro, regla dura 6). Un `draft`/`validated`/`deprecated`
    o un `tool_id` no catalogado devuelven `None` por igual: para invocar, todos son
    "no existe".
    """
    manifest = tool_registry.get_invocable(tool_id)
    if manifest is None:
        return None
    return ResolvedToolBinding.from_manifest(manifest)


class BindingValidationError(Exception):
    """El `tool_name` de un `ToolManifest` MCP no existe en el `tools/list` de su server.

    Validacion cruzada del binding (c09, tarea 2.3): se corre al pasar el manifiesto a
    `active` (ciclo `draft -> validated -> active`). El mensaje nombra el `tool_name`
    ausente y el server, de modo que el fallo sea accionable y el manifiesto no quede
    `active` apuntando a una Tool inexistente.
    """

    def __init__(
        self,
        manifest_id: str,
        tool_name: str,
        server: str,
        available: Collection[str],
    ) -> None:
        self.manifest_id = manifest_id
        self.tool_name = tool_name
        self.server = server
        self.available = tuple(available)
        disponibles = ", ".join(sorted(self.available)) if self.available else "(ninguna)"
        super().__init__(
            f"validacion cruzada del binding fallida: el ToolManifest {manifest_id!r} "
            f"referencia el tool_name {tool_name!r}, que el MCP Server {server!r} no expone "
            f"en su tools/list; Tools disponibles: {disponibles}"
        )


def validate_binding_against_server(
    manifest: ToolManifest, server_tool_names: Collection[str]
) -> None:
    """Valida que `manifest.mcp.tool_name` exista en `server_tool_names` (tools/list del server).

    Check puro (sin red): recibe los nombres ya obtenidos del `tools/list`. Lanza
    `BindingValidationError` nombrando el `tool_name` ausente si no esta en el server. Es
    el check que corre al pasar el manifiesto a `active`; el punto de escritura de `status`
    llega en `d21`, aqui se entrega la validacion invocable.
    """
    if manifest.mcp.tool_name not in server_tool_names:
        raise BindingValidationError(
            manifest_id=manifest.id,
            tool_name=manifest.mcp.tool_name,
            server=manifest.mcp.server,
            available=server_tool_names,
        )


async def validate_binding_against_live_server(
    manifest: ToolManifest, transport: TransportConfig
) -> None:
    """Variante de conveniencia: obtiene el `tools/list` real via `McpToolSession` y valida.

    Abre una sesion MCP contra el `transport` del server, lista sus Tools reales y delega en
    `validate_binding_against_server`. Uso: verificar los `ToolManifest` de fabrica contra
    el server de ejemplo por stdio.
    """
    async with McpToolSession(transport) as session:
        descriptors = await session.list_tools()
    validate_binding_against_server(manifest, {descriptor.name for descriptor in descriptors})
