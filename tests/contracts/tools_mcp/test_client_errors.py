"""Tests de contrato: manejo de errores diferenciado (Protocol vs Tool Execution).

Cubre la Requirement "Manejo de errores diferenciado (Protocol vs Tool
Execution)" (`openspec/changes/c09-mcp-tools/specs/mcp-tools/spec.md`) y la
tarea 1.7: los dos mecanismos de error de la spec MCP 2025-11-25 se mapean a
tipos de resultado DISTINTOS del `ToolPort`, y un `isError: true` jamás se
confunde con un éxito.

- Protocol Error JSON-RPC (`McpError`, p. ej. `-32602`) → `ToolProtocolFailure`.
- Tool Execution Error (`CallToolResult.isError: true`) → `ToolExecutionFailure`.
- Éxito (`isError: false`) → `ToolCallOutcome` (tipo que por construcción no
  puede portar `isError: true`).

HALLAZGO documentado aquí (server real): el server de ejemplo FastMCP
(`example_server`) NO surfacea una Tool desconocida como Protocol Error
JSON-RPC. FastMCP (y el propio decorador `Server.call_tool` del SDK) envuelve
la excepción "Unknown tool" en un `CallToolResult(isError=True)`, de modo que
un `tools/call` de un `name` inexistente contra `example_server` devuelve
`isError: true` (→ `ToolExecutionFailure`), NO un `-32602`. Para ejercer el
camino genuino `McpError(-32602)` → `ToolProtocolFailure` por stdio se usa un
fixture propio (`fixtures/protocol_error_server.py`), un MCP Server de bajo
nivel *conforme a la spec* que sí responde el Protocol Error. Ambos
comportamientos quedan verificados abajo.

Sin `pytest-asyncio`: cada test síncrono ejecuta su cuerpo async con
`anyio.run(...)`, con timeout vía `anyio.fail_after(...)`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import anyio
from mcp.shared.exceptions import McpError
from mcp.types import CallToolResult, ErrorData

from resultarai.adapters.tools_mcp.client import McpToolClient
from resultarai.adapters.tools_mcp.session import (
    McpToolSession,
    ToolCallOutcome,
    ToolExecutionFailure,
    ToolProtocolFailure,
    parse_call_tool_result,
)
from resultarai.adapters.tools_mcp.transports import StdioTransportConfig
from resultarai.core.policy import PolicyDecision
from tests.contracts.tools_mcp.fixtures.canonical_responses import (
    CALL_RESULT_IS_ERROR,
    PROTOCOL_ERROR_UNKNOWN_TOOL,
)

_EXAMPLE_SERVER_MODULE = "resultarai.adapters.tools_mcp.example_server"
_PROTOCOL_ERROR_SERVER_MODULE = "tests.contracts.tools_mcp.fixtures.protocol_error_server"
_TIMEOUT_SECONDS = 10.0

# Raíz del repo: el fixture `protocol_error_server` se lanza como `-m tests...`,
# y `tests` (a diferencia del paquete instalado `resultarai`) solo es
# importable desde la raíz del repo, así que el subproceso corre desde ahí.
_REPO_ROOT = Path(__file__).resolve().parents[3]


def _example_server_transport(cwd: Path) -> StdioTransportConfig:
    return StdioTransportConfig(
        command=sys.executable, args=("-m", _EXAMPLE_SERVER_MODULE), cwd=str(cwd)
    )


def _protocol_error_server_transport() -> StdioTransportConfig:
    return StdioTransportConfig(
        command=sys.executable,
        args=("-m", _PROTOCOL_ERROR_SERVER_MODULE),
        cwd=str(_REPO_ROOT),
    )


def _allow_decision() -> PolicyDecision:
    return PolicyDecision(
        effect="allow",
        reason="lectura autorizada por policy de prueba",
        applied_policy="policy_test",
    )


class TestProtocolErrorUnknownTool:
    """Escenario: 'Protocol Error de Tool desconocida'."""

    def test_unknown_tool_over_stdio_maps_to_protocol_failure_minus_32602(self) -> None:
        """Server conforme a la spec: `tools/call` de un name desconocido → `-32602`.

        Se salta el chequeo local del listado invocando `ClientSession.call_tool`
        directamente (por debajo de `McpToolSession.call_tool`), como pide el
        escenario. El `McpError` resultante se mapea a `ToolProtocolFailure`.
        """

        async def _run() -> ToolProtocolFailure:
            with anyio.fail_after(_TIMEOUT_SECONDS):
                async with McpToolSession(_protocol_error_server_transport()) as session:
                    try:
                        # tools/call directo, SIN pasar por el listado local ni
                        # por la validación de descriptor de session.call_tool.
                        await session.session.call_tool("nombre_que_no_existe", {})
                    except McpError as exc:
                        return ToolProtocolFailure.from_mcp_error("nombre_que_no_existe", exc)
                    raise AssertionError("Se esperaba un McpError (Protocol Error)")

        failure = anyio.run(_run)

        # NO es un resultado válido: es un fallo de PROTOCOLO tipado, distinto
        # de un éxito y distinto de un Tool Execution Error.
        assert isinstance(failure, ToolProtocolFailure)
        assert not isinstance(failure, ToolCallOutcome | ToolExecutionFailure)
        assert failure.code == -32602
        assert failure.tool_name == "nombre_que_no_existe"
        assert "nombre_que_no_existe" in failure.message

    def test_fastmcp_example_server_reports_unknown_tool_as_execution_error(
        self, tmp_path: Path
    ) -> None:
        """HALLAZGO: el server de ejemplo FastMCP NO emite `-32602` por Tool desconocida.

        FastMCP envuelve "Unknown tool" en `CallToolResult(isError=True)`, así
        que un `tools/call` de un name inexistente contra `example_server`
        produce un `ToolExecutionFailure` (Tool Execution Error), no un
        `ToolProtocolFailure`. Se documenta con una aserción explícita.
        """

        async def _run() -> ToolCallOutcome | ToolExecutionFailure:
            with anyio.fail_after(_TIMEOUT_SECONDS):
                async with McpToolSession(_example_server_transport(tmp_path)) as session:
                    raw = await session.session.call_tool("nombre_que_no_existe", {})
                    return parse_call_tool_result("nombre_que_no_existe", raw)

        outcome = anyio.run(_run)

        # FastMCP => isError:true (NO Protocol Error): sale un ToolExecutionFailure.
        assert isinstance(outcome, ToolExecutionFailure)
        assert not isinstance(outcome, ToolProtocolFailure)
        assert "nombre_que_no_existe" in outcome.message


class TestToolExecutionErrorActionableFeedback:
    """Escenario: 'Tool Execution Error con feedback accionable'."""

    def test_calculate_invalid_expression_returns_execution_failure_not_success(
        self, tmp_path: Path
    ) -> None:
        """`calculate` con una expresión no soportada → `isError: true` conservado.

        La expresión es un string válido (pasa el `inputSchema`), llega al
        server y este la rechaza con `isError: true` y un mensaje accionable de
        negocio, que se conserva ÍNTEGRO para el modelo.
        """

        async def _run() -> ToolCallOutcome | ToolExecutionFailure:
            with anyio.fail_after(_TIMEOUT_SECONDS):
                async with McpToolSession(_example_server_transport(tmp_path)) as session:
                    descriptors = await session.list_tools()
                    calculate = next(d for d in descriptors if d.name == "calculate")
                    return await session.call_tool(
                        "calculate", {"expression": "__import__('os')"}, calculate
                    )

        outcome = anyio.run(_run)

        # Tool Execution Error: NUNCA un éxito (tipo distinto de ToolCallOutcome).
        assert isinstance(outcome, ToolExecutionFailure)
        assert not isinstance(outcome, ToolCallOutcome)
        assert outcome.tool_name == "calculate"
        # Feedback accionable conservado íntegro (mensaje de negocio del server).
        assert "no permitido" in outcome.message
        assert outcome.message == outcome.raw.content[0].text  # type: ignore[union-attr]


class TestPureMappingFromCanonicalResponses:
    """Mapeo puro (sin server ni red) con las respuestas JSON-RPC canónicas."""

    def test_call_result_is_error_maps_to_execution_failure(self) -> None:
        raw = CallToolResult(**CALL_RESULT_IS_ERROR["result"])

        outcome = parse_call_tool_result("calculate", raw)

        assert isinstance(outcome, ToolExecutionFailure)
        assert not isinstance(outcome, ToolCallOutcome)
        # El texto de negocio se conserva íntegro (no se trunca ni resume).
        expected_text = CALL_RESULT_IS_ERROR["result"]["content"][0]["text"]
        assert outcome.message == expected_text
        assert outcome.tool_name == "calculate"

    def test_protocol_error_unknown_tool_maps_to_protocol_failure(self) -> None:
        error_payload = PROTOCOL_ERROR_UNKNOWN_TOOL["error"]
        mcp_error = McpError(ErrorData(**error_payload))

        failure = ToolProtocolFailure.from_mcp_error("nonexistent_tool", mcp_error)

        assert isinstance(failure, ToolProtocolFailure)
        assert failure.code == -32602
        assert failure.code == error_payload["code"]
        assert failure.message == error_payload["message"]
        assert failure.tool_name == "nonexistent_tool"


class TestExecuteDistinguishesTheThreeCases:
    """`McpToolClient.execute` (camino ToolPort, decisión allow) separa los tres casos."""

    def test_allow_success_returns_tool_call_outcome(self, tmp_path: Path) -> None:
        client = McpToolClient(_example_server_transport(tmp_path))

        result = client.execute("echo", {"text": "hola"}, _allow_decision())

        assert isinstance(result, ToolCallOutcome)
        assert result.content == "hola"

    def test_allow_tool_execution_error_returns_execution_failure(self, tmp_path: Path) -> None:
        client = McpToolClient(_example_server_transport(tmp_path))

        result = client.execute("calculate", {"expression": "__import__('os')"}, _allow_decision())

        assert isinstance(result, ToolExecutionFailure)
        assert not isinstance(result, ToolCallOutcome)
        assert "no permitido" in result.message

    def test_allow_protocol_error_returns_protocol_failure(self) -> None:
        # `protocol_boom` SÍ aparece en el tools/list del fixture (pasa el
        # chequeo local del cliente), pero el server la rechaza con -32602 al
        # ejecutarla: el camino McpError → ToolProtocolFailure.
        client = McpToolClient(_protocol_error_server_transport())

        result = client.execute("protocol_boom", {}, _allow_decision())

        assert isinstance(result, ToolProtocolFailure)
        assert not isinstance(result, ToolCallOutcome | ToolExecutionFailure)
        assert result.code == -32602
        assert result.tool_name == "protocol_boom"
