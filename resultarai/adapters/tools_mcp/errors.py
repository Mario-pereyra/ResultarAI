"""Errores tipados del cliente MCP (`adapters/tools_mcp`).

Cubren los fallos de las tareas 1.2-1.6: capability `tools` ausente,
argumentos que no cumplen el `inputSchema`, y `tool_name` inexistente en el
`tools/list` del server conectado. Estas excepciones modelan "no se llegó a
llamar al server" (fallos LOCALes, previos a `tools/call`).

El caso "el server SÍ respondió con un error" es distinto y NO se modela como
excepción sino como resultado tipado del `ToolPort` (tarea 1.7, Requirement
"Manejo de errores diferenciado" en
`openspec/changes/c09-mcp-tools/specs/mcp-tools/spec.md`): `session.py` define
`ToolExecutionFailure` (`CallToolResult.isError: true`) y `ToolProtocolFailure`
(error JSON-RPC `McpError`, p. ej. `-32602`). `UnknownToolError` de aquí sigue
siendo el chequeo LOCAL (la Tool no está en el `tools/list`), previo a emitir
la petición; el rechazo server-side de un `name` con `-32602` lo captura el
camino `ToolProtocolFailure`.
"""

from __future__ import annotations

__all__ = [
    "McpCapabilityError",
    "McpToolClientError",
    "ToolArgumentValidationError",
    "UnknownToolError",
]


class McpToolClientError(Exception):
    """Base de las excepciones tipadas del cliente MCP."""


class McpCapabilityError(McpToolClientError):
    """El MCP Server no declaró una capability requerida (p. ej. `tools`) en el `InitializeResult`.

    Escenario "Conexión e initialize con negociación de capacidades": el
    cliente se niega a operar (no lista ni invoca Tools) si el server no
    ofrece la capability `tools`.
    """


class ToolArgumentValidationError(McpToolClientError):
    """Los `arguments` de una invocación no cumplen el `inputSchema` del descriptor.

    Se lanza ANTES de emitir `tools/call`: el cliente nunca llama al server
    con argumentos que ya sabe inválidos (Escenario "Argumentos que no
    cumplen el inputSchema no se envían").
    """

    def __init__(self, tool_name: str, message: str) -> None:
        self.tool_name = tool_name
        super().__init__(message)


class UnknownToolError(McpToolClientError):
    """`tool_name` no aparece en el `tools/list` del server conectado.

    El cliente detecta esta ausencia ANTES de intentar `tools/call` (tras
    listar las Tools disponibles), así que nunca llega a emitir la request. El
    mapeo de este caso a un Protocol Error JSON-RPC (`-32602`, "Tool
    desconocida") propiamente dicho lo hace la tarea 1.7.
    """

    def __init__(self, tool_name: str) -> None:
        self.tool_name = tool_name
        super().__init__(
            f"La Tool {tool_name!r} no existe en el tools/list del MCP Server conectado."
        )
