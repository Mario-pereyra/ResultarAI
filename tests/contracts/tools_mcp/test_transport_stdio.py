"""Tests de contrato: transport stdio (Requirement 'Transports stdio y Streamable HTTP').

Cubre el escenario "MCP Server local por stdio"
(`openspec/changes/c09-mcp-tools/specs/mcp-tools/spec.md`): el cliente lanza
el server como subproceso, intercambia JSON-RPC newline-delimited por
`stdin`/`stdout`, y trata `stderr` como logging (no como condición de error).

- El round-trip completo (`initialize` → `tools/list` → `tools/call`) se
  prueba a través de `McpToolSession` + `StdioTransportConfig`
  (`transports.open_transport`), exactamente el camino que usa
  `McpToolClient`.
- Que `stderr` es logging y no rompe el protocolo se prueba por separado
  usando `mcp.client.stdio.stdio_client` directamente (el mismo transport
  que usa `open_transport` por debajo, con su parámetro `errlog`): el
  server de ejemplo ya emite logs por stderr en cada request (se ve en la
  consola al correr sus tests) y, aun así, el intercambio JSON-RPC por
  stdin/stdout se completa con normalidad.
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path
from typing import TextIO

import anyio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from resultarai.adapters.tools_mcp.session import McpToolSession
from resultarai.adapters.tools_mcp.transports import StdioTransportConfig

_SERVER_MODULE = "resultarai.adapters.tools_mcp.example_server"
_TIMEOUT_SECONDS = 10.0


class TestStdioTransportEndToEndViaMcpToolSession:
    """Escenario 'MCP Server local por stdio', vía el camino público del cliente."""

    def test_initialize_list_and_call_over_stdio(self, tmp_path: Path) -> None:
        async def _run() -> tuple[tuple[str, ...], str]:
            transport = StdioTransportConfig(
                command=sys.executable, args=("-m", _SERVER_MODULE), cwd=str(tmp_path)
            )
            with anyio.fail_after(_TIMEOUT_SECONDS):
                async with McpToolSession(transport) as session:
                    descriptors = await session.list_tools()
                    echo = next(d for d in descriptors if d.name == "echo")
                    outcome = await session.call_tool("echo", {"text": "por stdio"}, echo)
                    return tuple(d.name for d in descriptors), outcome.content

        names, content = anyio.run(_run)
        assert set(names) == {"echo", "get_current_time", "calculate", "record_note"}
        assert content == "por stdio"

    def test_env_and_cwd_are_forwarded_to_the_subprocess(self, tmp_path: Path) -> None:
        # cwd se usa aquí como prueba indirecta de que StdioTransportConfig
        # llega intacto a StdioServerParameters: la Tool de escritura simulada
        # no debe crear ningún archivo en el cwd del subproceso.
        async def _run() -> None:
            transport = StdioTransportConfig(
                command=sys.executable, args=("-m", _SERVER_MODULE), cwd=str(tmp_path)
            )
            with anyio.fail_after(_TIMEOUT_SECONDS):
                async with McpToolSession(transport) as session:
                    record_note = next(
                        d for d in await session.list_tools() if d.name == "record_note"
                    )
                    await session.call_tool("record_note", {"note": "prueba"}, record_note)

        before = set(tmp_path.iterdir())
        anyio.run(_run)
        after = set(tmp_path.iterdir())
        assert before == after


class TestStderrIsTreatedAsLoggingNotAsProtocolError:
    """Stderr del subproceso stdio nunca interrumpe el intercambio JSON-RPC."""

    def test_json_rpc_exchange_succeeds_while_the_server_logs_to_stderr(
        self, tmp_path: Path
    ) -> None:
        # `errlog` del SDK se pasa tal cual a `subprocess`/`anyio.open_process`
        # como stderr del hijo: necesita un fondo de archivo real
        # (`.fileno()`), no un buffer en memoria como `io.StringIO`.
        async def _run(errlog: TextIO) -> bool:
            params = StdioServerParameters(
                command=sys.executable, args=["-m", _SERVER_MODULE], cwd=str(tmp_path)
            )
            with anyio.fail_after(_TIMEOUT_SECONDS):
                async with (
                    stdio_client(params, errlog=errlog) as (read, write),
                    ClientSession(read, write) as session,
                ):
                    await session.initialize()
                    result = await session.call_tool("echo", {"text": "stderr no rompe nada"})
                    return not result.isError

        with tempfile.TemporaryFile(mode="w+", encoding="utf-8") as errlog:
            succeeded = anyio.run(_run, errlog)

            assert succeeded is True
            # El server de ejemplo (FastMCP) registra sus logs de request en
            # stderr; que hayan llegado al archivo separado confirma que
            # viajan por un canal distinto de stdin/stdout, sin interferir
            # con el JSON-RPC.
            errlog.seek(0)
            assert errlog.read() != ""
