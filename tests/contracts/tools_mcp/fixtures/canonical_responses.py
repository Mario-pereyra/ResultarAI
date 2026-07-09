"""Payloads JSON-RPC canónicos de la spec MCP revisión 2025-11-25.

Estas constantes representan mensajes/resultados JSON-RPC tal como los
recibiría el cliente MCP desde un MCP Server real, para usarlos en tests
unitarios del cliente (`adapters/tools_mcp`) sin depender de un server ni de
red externa. Cada payload sigue el shape exacto de la spec 2025-11-25
(`https://modelcontextprotocol.io/specification/2025-11-25`):

- `TOOLS_LIST_PAGE_1` / `TOOLS_LIST_PAGE_2`: dos páginas de `tools/list`
  encadenadas por `cursor`/`nextCursor`, para el escenario "Listado completo
  con paginación".
- `TOOL_DESCRIPTOR_INVALID_INPUT_SCHEMA`: descriptor de Tool con
  `inputSchema: null`, para el escenario "Descriptor sin inputSchema válido
  rechazado".
- `TOOL_DESCRIPTOR_WITH_OUTPUT_SCHEMA` + `CALL_RESULT_STRUCTURED`: un
  descriptor con `outputSchema` y el `CallToolResult` correspondiente con
  `structuredContent` conforme a ese schema.
- `CALL_RESULT_IS_ERROR`: `CallToolResult` con `isError: true` y un mensaje
  de negocio accionable (Tool Execution Error, no Protocol Error).
- `PROTOCOL_ERROR_UNKNOWN_TOOL`: error JSON-RPC (`-32602`) de Tool
  desconocida (Protocol Error).
"""

from __future__ import annotations

from typing import Any, Final

# --- tools/list con paginación ---------------------------------------------

TOOLS_LIST_PAGE_1: Final[dict[str, Any]] = {
    "jsonrpc": "2.0",
    "id": 1,
    "result": {
        "tools": [
            {
                "name": "echo",
                "description": "Devuelve exactamente el texto recibido.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                },
            },
            {
                "name": "get_current_time",
                "description": "Fecha y hora actual en ISO 8601 para el timezone dado.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"timezone": {"type": "string", "default": "UTC"}},
                },
            },
        ],
        "nextCursor": "page-2",
    },
}

TOOLS_LIST_PAGE_2: Final[dict[str, Any]] = {
    "jsonrpc": "2.0",
    "id": 2,
    "result": {
        "tools": [
            {
                "name": "calculate",
                "description": "Evalúa una expresión aritmética simple de forma segura.",
                "inputSchema": {
                    "type": "object",
                    "properties": {"expression": {"type": "string"}},
                    "required": ["expression"],
                },
            },
        ],
        # Última página: sin nextCursor, la paginación termina.
    },
}

# --- Descriptor con inputSchema inválido ------------------------------------

TOOL_DESCRIPTOR_INVALID_INPUT_SCHEMA: Final[dict[str, Any]] = {
    "name": "broken_tool",
    "description": "Descriptor inválido: inputSchema es null en vez de un JSON Schema objeto.",
    "inputSchema": None,
}

# --- Descriptor + resultado con outputSchema / structuredContent -----------

TOOL_DESCRIPTOR_WITH_OUTPUT_SCHEMA: Final[dict[str, Any]] = {
    "name": "get_current_time",
    "description": "Fecha y hora actual en ISO 8601 para el timezone dado.",
    "inputSchema": {
        "type": "object",
        "properties": {"timezone": {"type": "string", "default": "UTC"}},
    },
    "outputSchema": {
        "type": "object",
        "properties": {"iso_timestamp": {"type": "string"}},
        "required": ["iso_timestamp"],
    },
}

CALL_RESULT_STRUCTURED: Final[dict[str, Any]] = {
    "jsonrpc": "2.0",
    "id": 3,
    "result": {
        "content": [
            {"type": "text", "text": "2026-07-09T00:00:00+00:00"},
        ],
        "structuredContent": {"iso_timestamp": "2026-07-09T00:00:00+00:00"},
        "isError": False,
    },
}

# --- Tool Execution Error (isError: true) -----------------------------------

CALL_RESULT_IS_ERROR: Final[dict[str, Any]] = {
    "jsonrpc": "2.0",
    "id": 4,
    "result": {
        "content": [
            {
                "type": "text",
                "text": (
                    "Expresión aritmética inválida: '2+'. Usa solo números, paréntesis "
                    "y los operadores + - * / // % **."
                ),
            },
        ],
        "isError": True,
    },
}

# --- Protocol Error: Tool desconocida (JSON-RPC -32602) ---------------------

PROTOCOL_ERROR_UNKNOWN_TOOL: Final[dict[str, Any]] = {
    "jsonrpc": "2.0",
    "id": 5,
    "error": {
        "code": -32602,
        "message": "Unknown tool: 'nonexistent_tool'",
    },
}
