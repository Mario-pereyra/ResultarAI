"""Tests de contrato: invocación tipada de Tools (`tools/call`).

Cubre la Requirement "Invocación tipada de Tools vía tools/call"
(`openspec/changes/c09-mcp-tools/specs/mcp-tools/spec.md`):

- "Invocación de lectura autorizada devuelve resultado tipado": `echo` y
  `calculate` del server de ejemplo (por stdio) devuelven un
  `ToolCallOutcome` (el tipo de éxito, que por construcción no puede ser un
  `isError: true`), con `content` correcto y `structured_content` no vacío
  (FastMCP genera `outputSchema`/`structuredContent` incluso para Tools que
  devuelven texto plano).
- "Argumentos que no cumplen el inputSchema no se envían": una invocación con
  argumentos inválidos lanza `ToolArgumentValidationError` ANTES de tocar
  `ClientSession.call_tool` — se prueba con un spy que falla el test si
  `tools/call` llega a emitirse.

Sin `pytest-asyncio`: cada test síncrono ejecuta su cuerpo async con
`anyio.run(...)`, con timeout vía `anyio.fail_after(...)`.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import anyio
import pytest

from resultarai.adapters.tools_mcp.descriptors import ToolDescriptor
from resultarai.adapters.tools_mcp.errors import ToolArgumentValidationError
from resultarai.adapters.tools_mcp.session import McpToolSession, ToolCallOutcome
from resultarai.adapters.tools_mcp.transports import StdioTransportConfig

_SERVER_MODULE = "resultarai.adapters.tools_mcp.example_server"
_TIMEOUT_SECONDS = 10.0


def _stdio_transport(cwd: Path) -> StdioTransportConfig:
    return StdioTransportConfig(command=sys.executable, args=("-m", _SERVER_MODULE), cwd=str(cwd))


async def _descriptor_for(session: McpToolSession, name: str) -> ToolDescriptor:
    descriptors = await session.list_tools()
    return next(d for d in descriptors if d.name == name)


class TestAuthorizedReadInvocationReturnsTypedOutcome:
    """Escenario: 'Invocación de lectura autorizada devuelve resultado tipado'."""

    def test_echo_returns_content_and_structured_content(self, tmp_path: Path) -> None:
        async def _run() -> Any:
            with anyio.fail_after(_TIMEOUT_SECONDS):
                async with McpToolSession(_stdio_transport(tmp_path)) as session:
                    echo = await _descriptor_for(session, "echo")
                    return await session.call_tool("echo", {"text": "hola mundo"}, echo)

        outcome = anyio.run(_run)

        # El tipo de éxito `ToolCallOutcome` no puede representar `isError:true`
        # (aserción más fuerte que el antiguo `is_error is False`).
        assert isinstance(outcome, ToolCallOutcome)
        assert outcome.content == "hola mundo"
        # El descriptor de `echo` declara outputSchema (FastMCP lo genera); el
        # SDK ya valida structuredContent contra ese schema dentro de
        # call_tool (verificado en compliance-mcp-2025-11-25.md, punto 3).
        assert outcome.structured_content == {"result": "hola mundo"}

    def test_calculate_evaluates_expression_with_precedence(self, tmp_path: Path) -> None:
        async def _run() -> Any:
            with anyio.fail_after(_TIMEOUT_SECONDS):
                async with McpToolSession(_stdio_transport(tmp_path)) as session:
                    calculate = await _descriptor_for(session, "calculate")
                    return await session.call_tool("calculate", {"expression": "2+2*3"}, calculate)

        outcome = anyio.run(_run)

        assert isinstance(outcome, ToolCallOutcome)
        assert outcome.content == "8"


class TestArgumentsNotMatchingInputSchemaAreNeverSent:
    """Escenario: 'Argumentos que no cumplen el inputSchema no se envían'."""

    def test_missing_required_argument_raises_before_calling_the_server(
        self, tmp_path: Path
    ) -> None:
        async def _run() -> None:
            with anyio.fail_after(_TIMEOUT_SECONDS):
                async with McpToolSession(_stdio_transport(tmp_path)) as session:
                    echo = await _descriptor_for(session, "echo")

                    call_tool_was_invoked = False

                    async def _spy_call_tool(*args: Any, **kwargs: Any) -> Any:
                        nonlocal call_tool_was_invoked
                        call_tool_was_invoked = True
                        raise AssertionError(
                            "tools/call no debía emitirse con argumentos inválidos"
                        )

                    # Espía sobre la ClientSession real y ya conectada: si la
                    # validación previa falla como debe, este spy nunca corre.
                    session.session.call_tool = _spy_call_tool  # type: ignore[method-assign]

                    with pytest.raises(ToolArgumentValidationError) as exc_info:
                        await session.call_tool("echo", {}, echo)

                    assert call_tool_was_invoked is False
                    assert "echo" in str(exc_info.value)

        anyio.run(_run)

    def test_wrong_argument_type_raises_with_actionable_message(self, tmp_path: Path) -> None:
        async def _run() -> None:
            with anyio.fail_after(_TIMEOUT_SECONDS):
                async with McpToolSession(_stdio_transport(tmp_path)) as session:
                    calculate = await _descriptor_for(session, "calculate")

                    with pytest.raises(ToolArgumentValidationError) as exc_info:
                        # "expression" debe ser string, no un número.
                        await session.call_tool("calculate", {"expression": 123}, calculate)

                    message = str(exc_info.value)
                    assert "calculate" in message
                    assert "inputSchema" in message

        anyio.run(_run)
