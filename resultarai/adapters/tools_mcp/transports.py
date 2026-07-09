"""Configuración de transport MCP y apertura del transport del SDK correcto.

Modela los dos transports estándar de la spec MCP revisión 2025-11-25
(`openspec/changes/c09-mcp-tools/specs/mcp-tools/spec.md`, Requirement
"Transports stdio y Streamable HTTP"):

- `StdioTransportConfig`: el cliente lanza el MCP Server como subproceso e
  intercambia mensajes JSON-RPC newline-delimited por `stdin`/`stdout`. El
  `stderr` del subproceso lo gestiona el SDK (`mcp.client.stdio.stdio_client`,
  parámetro `errlog`, por defecto `sys.stderr`): se trata como logging, NUNCA
  como condición de error del protocolo — el JSON-RPC viaja solo por
  `stdin`/`stdout`.
- `StreamableHttpTransportConfig`: un único endpoint MCP remoto por HTTP. El
  SDK (`mcp.client.streamable_http.streamable_http_client`) gestiona
  automáticamente los headers `MCP-Protocol-Version` y `MCP-Session-Id` en
  cada request posterior al `initialize` (una vez que el server asigna
  `Mcp-Session-Id`, el transport lo recuerda y lo reenvía; verificado en
  `compliance-mcp-2025-11-25.md`, punto 5) — este módulo no necesita
  gestionarlos a mano.

Elección de símbolo para Streamable HTTP: `mcp==1.28.1` expone dos funciones
para este transport. `streamablehttp_client` está marcada `@deprecated("Use
streamable_http_client instead.")` en el SDK; `streamable_http_client` es la
no deprecada (misma funcionalidad, API más simple: recibe un
`httpx.AsyncClient` opcional en vez de parámetros sueltos de headers/timeout).
Este módulo usa `streamable_http_client` a propósito para no emitir
`DeprecationWarning` en cada conexión.
"""

from __future__ import annotations

import contextlib
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from typing import assert_never

from anyio.streams.memory import MemoryObjectReceiveStream, MemoryObjectSendStream
from mcp import StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.message import SessionMessage

__all__ = [
    "StdioTransportConfig",
    "StreamableHttpTransportConfig",
    "TransportConfig",
    "open_transport",
]


@dataclass(frozen=True, slots=True)
class StdioTransportConfig:
    """Configuración para lanzar un MCP Server local como subproceso por stdio."""

    command: str
    args: tuple[str, ...] = field(default_factory=tuple)
    env: dict[str, str] | None = None
    cwd: str | None = None


@dataclass(frozen=True, slots=True)
class StreamableHttpTransportConfig:
    """Configuración para conectar a un MCP Server remoto por Streamable HTTP."""

    url: str


type TransportConfig = StdioTransportConfig | StreamableHttpTransportConfig

type ReadStream = MemoryObjectReceiveStream[SessionMessage | Exception]
type WriteStream = MemoryObjectSendStream[SessionMessage]


@contextlib.asynccontextmanager
async def open_transport(config: TransportConfig) -> AsyncIterator[tuple[ReadStream, WriteStream]]:
    """Abre el context manager del SDK que corresponde al tipo de `config`.

    Hace yield del par `(read_stream, write_stream)` que consume
    `mcp.ClientSession`. No expone el `GetSessionIdCallback` de Streamable
    HTTP: el SDK ya propaga `MCP-Session-Id` internamente sin intervención
    del llamador (ver docstring del módulo).
    """
    if isinstance(config, StdioTransportConfig):
        params = StdioServerParameters(
            command=config.command,
            args=list(config.args),
            env=config.env,
            cwd=config.cwd,
        )
        async with stdio_client(params) as (read_stream, write_stream):
            yield read_stream, write_stream
    elif isinstance(config, StreamableHttpTransportConfig):
        async with streamable_http_client(config.url) as (
            read_stream,
            write_stream,
            _get_session_id,
        ):
            yield read_stream, write_stream
    else:  # pragma: no cover - exhaustividad de TransportConfig
        assert_never(config)
