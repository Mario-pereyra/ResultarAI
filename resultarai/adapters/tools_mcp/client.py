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

from resultarai.adapters.tools_mcp.errors import UnknownToolError
from resultarai.adapters.tools_mcp.session import McpToolSession, ToolCallOutcome
from resultarai.adapters.tools_mcp.transports import TransportConfig
from resultarai.core.policy import PolicyDecision

__all__ = ["McpToolClient", "ToolExecutionRejected"]


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
    ) -> ToolCallOutcome | ToolExecutionRejected:
        """Ejecuta `tool_name` solo si `decision.effect == "allow"` (firma exacta de `ToolPort`).

        Con `allow`: ejecuta una sesión MCP completa (`initialize` →
        `tools/list` para resolver el descriptor de `tool_name` →
        validación de `arguments` → `tools/call`) vía `anyio.run` y devuelve
        el `ToolCallOutcome`. Si `tool_name` no aparece en el `tools/list`
        del server, lanza `UnknownToolError` (el mapeo fino a Protocol Error
        lo hace la tarea 1.7).

        Con `deny`/`escalate_hitl`: devuelve `ToolExecutionRejected` de
        inmediato, sin tocar el transport.
        """
        effect = decision.effect
        if effect != "allow":
            return ToolExecutionRejected(tool_name=tool_name, effect=effect, reason=decision.reason)

        return anyio.run(self._execute_allowed, tool_name, arguments)

    async def _execute_allowed(self, tool_name: str, arguments: dict[str, Any]) -> ToolCallOutcome:
        async with McpToolSession(self._transport) as session:
            descriptors = await session.list_tools()
            descriptor = next((d for d in descriptors if d.name == tool_name), None)
            if descriptor is None:
                raise UnknownToolError(tool_name)
            return await session.call_tool(tool_name, arguments, descriptor)
