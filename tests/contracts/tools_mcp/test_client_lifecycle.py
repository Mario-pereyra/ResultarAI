"""Tests de contrato: lifecycle MCP (`initialize` + negociación de capacidades).

Cubre la Requirement "Cliente MCP conforme a la spec MCP revisión 2025-11-25
detrás del ToolPort" (`openspec/changes/c09-mcp-tools/specs/mcp-tools/spec.md`):

- "Conexión e initialize con negociación de capacidades": `McpToolSession`
  completa el handshake contra el server de ejemplo por stdio y solo un
  server que declare la capability `tools` deja la sesión lista para operar.
- El check de la capability `tools` (`ensure_tools_capability`) se testea de
  forma unitaria, sin server real, construyendo un `InitializeResult` con
  tipos del SDK.

El escenario "El cliente MCP no vive en core" se verifica con `uv run
lint-imports` (parte de la suite de calidad del change), no con un test
pytest — ver `openspec/changes/c09-mcp-tools/compliance-mcp-2025-11-25.md`.

Sin `pytest-asyncio`: cada test síncrono ejecuta su cuerpo async con
`anyio.run(...)`, con timeout vía `anyio.fail_after(...)`.
"""

from __future__ import annotations

import sys
from pathlib import Path

import anyio
import pytest
from mcp.types import (
    LATEST_PROTOCOL_VERSION,
    Implementation,
    InitializeResult,
    ServerCapabilities,
    ToolsCapability,
)

from resultarai.adapters.tools_mcp.errors import McpCapabilityError
from resultarai.adapters.tools_mcp.session import McpToolSession, ensure_tools_capability
from resultarai.adapters.tools_mcp.transports import StdioTransportConfig

_SERVER_MODULE = "resultarai.adapters.tools_mcp.example_server"
_TIMEOUT_SECONDS = 10.0


def _stdio_transport(cwd: Path) -> StdioTransportConfig:
    return StdioTransportConfig(command=sys.executable, args=("-m", _SERVER_MODULE), cwd=str(cwd))


class TestInitializeNegotiatesCapabilitiesAgainstExampleServer:
    """Escenario: 'Conexión e initialize con negociación de capacidades' (server real)."""

    def test_session_opens_and_is_ready_to_list_tools(self, tmp_path: Path) -> None:
        async def _run() -> tuple[str, ...]:
            with anyio.fail_after(_TIMEOUT_SECONDS):
                async with McpToolSession(_stdio_transport(tmp_path)) as session:
                    descriptors = await session.list_tools()
                    return tuple(d.name for d in descriptors)

        names = anyio.run(_run)
        assert "echo" in names
        assert "record_note" in names

    def test_accessing_session_outside_async_with_raises(self, tmp_path: Path) -> None:
        session = McpToolSession(_stdio_transport(tmp_path))
        with pytest.raises(RuntimeError):
            _ = session.session


class TestToolsCapabilityIsRequired:
    """Escenario: el cliente solo queda listo para operar si el server declara `tools`."""

    def test_ensure_tools_capability_raises_when_capability_missing(self) -> None:
        init_result = InitializeResult(
            protocolVersion=LATEST_PROTOCOL_VERSION,
            capabilities=ServerCapabilities(tools=None),
            serverInfo=Implementation(name="server-sin-tools", version="0.0.1"),
        )

        with pytest.raises(McpCapabilityError):
            ensure_tools_capability(init_result)

    def test_ensure_tools_capability_passes_when_capability_present(self) -> None:
        init_result = InitializeResult(
            protocolVersion=LATEST_PROTOCOL_VERSION,
            capabilities=ServerCapabilities(tools=ToolsCapability()),
            serverInfo=Implementation(name="server-con-tools", version="0.0.1"),
        )

        ensure_tools_capability(init_result)  # no debe lanzar
