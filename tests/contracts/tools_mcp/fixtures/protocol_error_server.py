"""Fixture: MCP Server que responde `tools/call` con un Protocol Error JSON-RPC.

Server mínimo por stdio, construido sobre el `Server` de bajo nivel del SDK
(`mcp.server.lowlevel`), cuyo handler de `tools/call` SIEMPRE lanza
`McpError(ErrorData(code=-32602, ...))` (INVALID_PARAMS). Representa un MCP
Server *conforme a la spec* que surfacea la "Tool desconocida" como un
**Protocol Error** JSON-RPC —el comportamiento que describe el Escenario
"Protocol Error de Tool desconocida" de
`openspec/changes/c09-mcp-tools/specs/mcp-tools/spec.md`.

Por qué un fixture propio y no el server de ejemplo (`example_server`): FastMCP
(y también el decorador `Server.call_tool` del SDK) **envuelve toda excepción
del handler de la Tool en un `CallToolResult(isError=True)`** (vía el
`_make_error_result` interno del SDK), por lo que su `tools/call` de una Tool
desconocida devuelve `isError: true`, NUNCA un error JSON-RPC. Para ejercer de
verdad el camino `McpError` → `ToolProtocolFailure`
por stdio hace falta registrar el handler de `CallToolRequest` directamente
(saltándose ese wrapper) y lanzar el `McpError`, que `_handle_request` del SDK
convierte en la respuesta de error JSON-RPC hacia el cliente.

El server declara la capability `tools` y publica una Tool `protocol_boom` en
`tools/list`, de modo que también sirve para el camino del `McpToolClient`
(que lista antes de invocar): la Tool pasa el chequeo local y es el server
quien la rechaza con `-32602` al ejecutarla.
"""

from __future__ import annotations

import anyio
import mcp.types as types
from mcp.server.lowlevel import NotificationOptions, Server
from mcp.server.stdio import stdio_server
from mcp.shared.exceptions import McpError

_SERVER_NAME = "protocol_error_test_server"

# Tool publicada en tools/list: existe para que el chequeo local del cliente la
# encuentre; el server la rechaza igualmente al invocarla (Protocol Error).
_PROTOCOL_BOOM_TOOL = types.Tool(
    name="protocol_boom",
    description="Siempre responde tools/call con un Protocol Error JSON-RPC (-32602).",
    inputSchema={"type": "object", "properties": {}},
)


async def _list_tools(_req: types.ListToolsRequest) -> types.ServerResult:
    return types.ServerResult(types.ListToolsResult(tools=[_PROTOCOL_BOOM_TOOL]))


async def _call_tool_raising_protocol_error(req: types.CallToolRequest) -> types.ServerResult:
    """Lanza un `McpError` INVALID_PARAMS (-32602) para CUALQUIER `tools/call`.

    Registrado directamente en `request_handlers` para saltarse el wrapper del
    decorador `Server.call_tool`, que si no convertiría esta excepción en un
    `CallToolResult(isError=True)`. Así el cliente recibe un Protocol Error
    JSON-RPC genuino.
    """
    raise McpError(
        types.ErrorData(
            code=types.INVALID_PARAMS,
            message=f"Unknown tool: {req.params.name!r}",
        )
    )


def _build_server() -> Server:
    server: Server = Server(_SERVER_NAME)
    server.request_handlers[types.ListToolsRequest] = _list_tools
    server.request_handlers[types.CallToolRequest] = _call_tool_raising_protocol_error
    return server


async def _serve() -> None:
    server = _build_server()
    init_options = server.create_initialization_options(NotificationOptions())
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, init_options)


if __name__ == "__main__":
    anyio.run(_serve)
