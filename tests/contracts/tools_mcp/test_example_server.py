"""Tests de contrato: MCP Server de ejemplo de fábrica (`example_utilities_server`).

Cubre los dos escenarios de la Requirement "MCP Server de ejemplo de fábrica"
(`openspec/changes/c09-mcp-tools/specs/mcp-tools/spec.md`):

- "El server de ejemplo expone lectura y escritura simulada": `tools/list`
  expone las 4 Tools, cada una con `inputSchema` válido, incluida al menos
  una de lectura (`echo`) y la escritura simulada (`record_note`).
- "La escritura simulada no produce efecto real": invocar `record_note` no
  crea ni modifica ningún archivo del directorio de trabajo del subproceso.

Además incluye un smoke test de los fixtures de la tarea 4.4 (payloads
JSON-RPC canónicos y el server de prueba Streamable HTTP).

Sin `pytest-asyncio` (no está en las dependencias del repo): cada test
síncrono ejecuta su cuerpo async con `anyio.run(...)`, con timeouts vía
`anyio.fail_after(...)` para no colgar la suite si algo queda pendiente.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamablehttp_client
from mcp.types import CallToolResult, ListToolsResult, TextContent, Tool

from tests.contracts.tools_mcp.fixtures import canonical_responses
from tests.contracts.tools_mcp.fixtures.http_test_server import run_http_test_server

_SERVER_MODULE = "resultarai.adapters.tools_mcp.example_server"
_TIMEOUT_SECONDS = 10.0
_EXPECTED_TOOL_NAMES = {"echo", "get_current_time", "calculate", "record_note"}


def _stdio_params(cwd: Path) -> StdioServerParameters:
    """Parámetros para lanzar el server de ejemplo como subproceso stdio.

    `cwd` fija el directorio de trabajo del subproceso a un `tmp_path` de
    test, para poder verificar que la escritura simulada no crea archivos.
    """
    return StdioServerParameters(
        command=sys.executable,
        args=["-m", _SERVER_MODULE],
        cwd=str(cwd),
    )


async def _list_tools(cwd: Path) -> list[Tool]:
    """Conecta por stdio, hace el handshake y devuelve el catálogo de Tools."""
    async with (
        stdio_client(_stdio_params(cwd)) as (read, write),
        ClientSession(read, write) as session,
    ):
        with anyio.fail_after(_TIMEOUT_SECONDS):
            await session.initialize()
            result: ListToolsResult = await session.list_tools()
        return result.tools


async def _call_tool(cwd: Path, name: str, arguments: dict[str, Any]) -> CallToolResult:
    """Conecta por stdio, hace el handshake e invoca una Tool por `tools/call`."""
    async with (
        stdio_client(_stdio_params(cwd)) as (read, write),
        ClientSession(read, write) as session,
    ):
        with anyio.fail_after(_TIMEOUT_SECONDS):
            await session.initialize()
            return await session.call_tool(name, arguments)


def _text_of(result: CallToolResult) -> str:
    """Extrae el texto del primer bloque `TextContent` de un CallToolResult."""
    block = result.content[0]
    assert isinstance(block, TextContent)
    return block.text


class TestServerExposesReadAndSimulatedWrite:
    """Escenario: 'El server de ejemplo expone lectura y escritura simulada'."""

    def test_tools_list_exposes_exactly_the_four_tools(self, tmp_path: Path) -> None:
        tools = anyio.run(_list_tools, tmp_path)
        names = {tool.name for tool in tools}
        assert names == _EXPECTED_TOOL_NAMES

    def test_each_tool_has_a_valid_object_input_schema(self, tmp_path: Path) -> None:
        tools = anyio.run(_list_tools, tmp_path)
        assert tools  # al menos una Tool
        for tool in tools:
            assert isinstance(tool.inputSchema, dict)
            assert tool.inputSchema.get("type") == "object"

    def test_includes_a_read_tool_and_the_simulated_write_tool(self, tmp_path: Path) -> None:
        tools = anyio.run(_list_tools, tmp_path)
        names = {tool.name for tool in tools}
        # Lectura: echo (bindeada por manifests/tools/example_echo.yaml).
        assert "echo" in names
        # Escritura simulada: ejerce el camino escalate_hitl.
        assert "record_note" in names

    def test_echo_returns_the_received_text(self, tmp_path: Path) -> None:
        result = anyio.run(_call_tool, tmp_path, "echo", {"text": "hola mundo"})
        assert result.isError is False
        assert _text_of(result) == "hola mundo"

    def test_calculate_evaluates_simple_arithmetic_with_precedence(self, tmp_path: Path) -> None:
        result = anyio.run(_call_tool, tmp_path, "calculate", {"expression": "2+2*3"})
        assert result.isError is False
        assert _text_of(result) == "8"

    def test_calculate_rejects_unsafe_expression_as_tool_execution_error(
        self, tmp_path: Path
    ) -> None:
        # No eval()/exec(): una expresión no aritmética se rechaza con isError,
        # nunca se ejecuta como código.
        result = anyio.run(
            _call_tool, tmp_path, "calculate", {"expression": "__import__('os').system('id')"}
        )
        assert result.isError is True


class TestSimulatedWriteHasNoRealEffect:
    """Escenario: 'La escritura simulada no produce efecto real'."""

    def test_record_note_marks_response_as_simulated_without_filesystem_effect(
        self, tmp_path: Path
    ) -> None:
        before = set(tmp_path.iterdir())

        result = anyio.run(_call_tool, tmp_path, "record_note", {"note": "nota de prueba"})

        after = set(tmp_path.iterdir())
        assert result.isError is False
        text = _text_of(result)
        assert "simulado" in text
        assert "sin efecto real" in text
        assert "nota de prueba" in text
        # El directorio de trabajo del subproceso queda intacto: sin efecto real.
        assert before == after


class TestFixturesSmoke:
    """Smoke test de los fixtures de la tarea 4.4: cargan y el server HTTP responde."""

    def test_canonical_responses_load_with_expected_shape(self) -> None:
        page_1 = canonical_responses.TOOLS_LIST_PAGE_1["result"]
        page_2 = canonical_responses.TOOLS_LIST_PAGE_2["result"]
        assert page_1["nextCursor"] == "page-2"
        assert "nextCursor" not in page_2
        assert len(page_1["tools"]) == 2
        assert len(page_2["tools"]) == 1

        assert canonical_responses.TOOL_DESCRIPTOR_INVALID_INPUT_SCHEMA["inputSchema"] is None

        output_schema = canonical_responses.TOOL_DESCRIPTOR_WITH_OUTPUT_SCHEMA["outputSchema"]
        structured = canonical_responses.CALL_RESULT_STRUCTURED["result"]["structuredContent"]
        assert set(structured) == set(output_schema["required"])

        assert canonical_responses.CALL_RESULT_IS_ERROR["result"]["isError"] is True
        assert canonical_responses.PROTOCOL_ERROR_UNKNOWN_TOOL["error"]["code"] == -32602

    def test_http_test_server_starts_and_answers_initialize(self) -> None:
        async def _initialize_over_http() -> None:
            with run_http_test_server() as base_url:
                with anyio.fail_after(_TIMEOUT_SECONDS):
                    async with (
                        streamablehttp_client(base_url) as (read, write, _get_session_id),
                        ClientSession(read, write) as session,
                    ):
                        result = await session.initialize()
                        assert result.capabilities.tools is not None

                        tools_result = await session.list_tools()
                        names = {tool.name for tool in tools_result.tools}
                        assert names == {"ping"}

        anyio.run(_initialize_over_http)
