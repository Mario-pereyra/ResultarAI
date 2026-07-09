"""`McpToolClient`: adapter que implementa `ToolPort` (`core/ports/tool.py`) sobre el cliente MCP.

`ToolPort.execute` es síncrono (firma exacta heredada de `core/`); este
adapter ejecuta la sesión MCP async completa por debajo con `anyio.run`.

Regla dura del proyecto respetada aquí (Decision 4 de
`openspec/changes/c09-mcp-tools/design.md`): el cliente JAMÁS emite
`tools/call` si la `PolicyDecision` no es `allow`. Cuando `decision.effect`
es `deny` o `escalate_hitl`, `execute` devuelve un `ToolExecutionRejected` de
inmediato, sin abrir sesión MCP ni contactar al server — ni siquiera para
Tools de lectura. La orquestación completa del Policy Gate y el `AuditEvent`
por decisión los añade la sección 2 de este change; este adapter solo
garantiza que nunca contradice una decisión ya tomada.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

import anyio
from mcp.shared.exceptions import McpError

from resultarai.adapters.tools_mcp.errors import UnknownToolError
from resultarai.adapters.tools_mcp.session import (
    McpToolSession,
    ToolCallOutcome,
    ToolExecutionFailure,
    ToolProtocolFailure,
)
from resultarai.adapters.tools_mcp.transports import TransportConfig
from resultarai.core.policy import PolicyDecision

__all__ = ["McpToolClient", "ToolExecutionRejected"]

# Resultado observable del `ToolPort` (`McpToolClient.execute`). Tres casos
# distintos que ocurren tras contactar al server con decisión `allow`:
# `ToolCallOutcome` (éxito), `ToolExecutionFailure` (`isError: true`) y
# `ToolProtocolFailure` (error JSON-RPC). El cuarto, `ToolExecutionRejected`,
# ocurre cuando la Policy no autoriza y NUNCA se toca el server.
type ToolExecutionResult = (
    ToolCallOutcome | ToolExecutionFailure | ToolProtocolFailure | ToolExecutionRejected
)


@dataclass(frozen=True, slots=True)
class ToolExecutionRejected:
    """Resultado devuelto por `McpToolClient.execute` cuando la `PolicyDecision` no es `allow`.

    El cliente jamás abre sesión MCP ni emite `tools/call` en este caso: ni
    siquiera intenta contactar al server. Para `effect == "escalate_hitl"`
    (SIEMPRE el caso de las escrituras, regla dura 4), el evento queda en
    espera de aprobación — la Tarjeta HITL operativa es `d17`; aquí solo se
    modela el resultado tipado que expone el cliente MCP.
    """

    tool_name: str
    effect: Literal["deny", "escalate_hitl"]
    reason: str


class McpToolClient:
    """Adapter que implementa `ToolPort` sobre un único MCP Server/transport.

    Constructor: recibe la `TransportConfig` del MCP Server al que se
    conectará. El binding de qué server corresponde a cada `tool_name`
    (`ToolManifest` → server, `a02`/sección 2 de este change) es
    responsabilidad de la capa que construye este cliente, no de esta clase.
    """

    def __init__(self, transport: TransportConfig) -> None:
        self._transport = transport

    def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        decision: PolicyDecision,
    ) -> ToolExecutionResult:
        """Ejecuta `tool_name` solo si `decision.effect == "allow"` (firma exacta de `ToolPort`).

        Con `allow`: ejecuta una sesión MCP completa (`initialize` →
        `tools/list` para resolver el descriptor de `tool_name` →
        validación de `arguments` → `tools/call`) vía `anyio.run` y distingue
        los tres desenlaces posibles como VALORES tipados (nunca lanzando el
        fallo hacia arriba), de modo que el contrato observable del `ToolPort`
        separe los tres casos sin ambigüedad (Requirement "Manejo de errores
        diferenciado"):

        - éxito (`isError: false`) → `ToolCallOutcome`;
        - Tool Execution Error (`isError: true`) → `ToolExecutionFailure`,
          conservando el mensaje accionable de la Tool;
        - Protocol Error JSON-RPC (`McpError`, p. ej. `-32602`) →
          `ToolProtocolFailure` con `code`/`message` del server.

        `UnknownToolError` conserva su semántica local: si `tool_name` no está
        en el `tools/list` del server, se detecta ANTES de emitir `tools/call`
        y se lanza (no se contacta al server para esa Tool). El caso en que el
        propio server rechaza un `name` con `-32602` se cubre por el camino
        `McpError` → `ToolProtocolFailure`.

        Con `deny`/`escalate_hitl`: devuelve `ToolExecutionRejected` de
        inmediato, sin tocar el transport.
        """
        effect = decision.effect
        if effect != "allow":
            return ToolExecutionRejected(tool_name=tool_name, effect=effect, reason=decision.reason)

        return anyio.run(self._execute_allowed, tool_name, arguments)

    async def _execute_allowed(
        self, tool_name: str, arguments: dict[str, Any]
    ) -> ToolCallOutcome | ToolExecutionFailure | ToolProtocolFailure:
        try:
            async with McpToolSession(self._transport) as session:
                descriptors = await session.list_tools()
                descriptor = next((d for d in descriptors if d.name == tool_name), None)
                if descriptor is None:
                    raise UnknownToolError(tool_name)
                return await session.call_tool(tool_name, arguments, descriptor)
        except McpError as exc:
            # Protocol Error JSON-RPC del server (Tool desconocida server-side,
            # request mal formado, error interno): se mapea a valor tipado, no
            # se propaga. `UnknownToolError` (fallo local, no McpError) sí sigue
            # propagándose, conservando su semántica.
            return ToolProtocolFailure.from_mcp_error(tool_name, exc)
