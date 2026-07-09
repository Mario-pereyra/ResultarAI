"""Tests de contrato: transport Streamable HTTP (Requirement 'Transports stdio y Streamable HTTP').

Cubre el escenario "MCP Server remoto por Streamable HTTP"
(`openspec/changes/c09-mcp-tools/specs/mcp-tools/spec.md`) contra
`run_http_test_server()` de los fixtures (server de prueba mínimo,
stateful, sin red externa): `initialize` + `tools/list` + `tools/call ping`
a través de `McpToolSession` con `StreamableHttpTransportConfig`.

El server de prueba es stateful (`fixtures/http_test_server.py`): que las
requests posteriores al `initialize` (`tools/list`, luego `tools/call`)
funcionen sobre la misma sesión es, en sí, la prueba de que el cliente
propaga correctamente el `MCP-Session-Id` que el server asignó — un server
stateful rechazaría cualquier request sin ese header una vez abierta la
sesión. El SDK (`mcp==1.28.1`) gestiona ese header automáticamente (ver
`transports.py` y `compliance-mcp-2025-11-25.md`, punto 5).
"""

from __future__ import annotations

import anyio

from resultarai.adapters.tools_mcp.session import McpToolSession
from resultarai.adapters.tools_mcp.transports import StreamableHttpTransportConfig
from tests.contracts.tools_mcp.fixtures.http_test_server import run_http_test_server

_TIMEOUT_SECONDS = 10.0


class TestStreamableHttpTransportEndToEnd:
    """Escenario 'MCP Server remoto por Streamable HTTP'."""

    def test_initialize_list_and_call_ping_reuse_the_same_session(self) -> None:
        async def _run() -> tuple[tuple[str, ...], str, bool]:
            with run_http_test_server() as base_url:
                with anyio.fail_after(_TIMEOUT_SECONDS):
                    async with McpToolSession(
                        StreamableHttpTransportConfig(url=base_url)
                    ) as session:
                        descriptors = await session.list_tools()
                        ping = next(d for d in descriptors if d.name == "ping")
                        # Segunda request sobre la MISMA sesión ya inicializada:
                        # si el Session-Id no se propagara, el server stateful
                        # de prueba la rechazaría.
                        outcome = await session.call_tool("ping", {}, ping)
                        return tuple(d.name for d in descriptors), outcome.content, outcome.is_error

        names, content, is_error = anyio.run(_run)

        assert names == ("ping",)
        assert content == "pong"
        assert is_error is False
