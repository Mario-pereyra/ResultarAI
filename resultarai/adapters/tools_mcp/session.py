"""Sesión MCP tipada: lifecycle, descubrimiento (`tools/list`) e invocación (`tools/call`).

`McpToolSession` es un async context manager que envuelve cualquier
`TransportConfig` (`transports.py`) + `mcp.ClientSession`: en `__aenter__`
abre el transport, crea la `ClientSession`, hace `initialize()` (el SDK
negocia capacidades y envía `notifications/initialized`) y exige la
capability `tools` (`ensure_tools_capability`); si el server no la declara,
cierra todo y lanza `McpCapabilityError` (Escenario "Conexión e initialize
con negociación de capacidades").

`paginate_tool_descriptors` implementa la paginación de `tools/list`
(`cursor`/`nextCursor`) como una función pura que recibe un `ToolLister`
asíncrono — así se testea con las respuestas canónicas de los fixtures sin
levantar un MCP Server real (Escenario "Listado completo con paginación").
`McpToolSession.list_tools` es solo el adaptador que conecta esa función con
la `ClientSession` real.
"""

from __future__ import annotations

import contextlib
from collections.abc import Awaitable, Callable, Mapping, Sequence
from dataclasses import dataclass
from types import TracebackType
from typing import Any, NotRequired, Self, TypedDict

# `jsonschema` no publica un marcador `py.typed`; no hay stubs propios en el
# proyecto (no se añaden dependencias nuevas a pyproject.toml solo para
# tipado) y por eso el import se ignora explícitamente para mypy --strict.
import jsonschema  # type: ignore[import-untyped]
from mcp import ClientSession
from mcp.types import CallToolResult, InitializeResult, PaginatedRequestParams, TextContent

from resultarai.adapters.tools_mcp.descriptors import ToolDescriptor, parse_tool_descriptor
from resultarai.adapters.tools_mcp.errors import McpCapabilityError, ToolArgumentValidationError
from resultarai.adapters.tools_mcp.transports import TransportConfig, open_transport

__all__ = [
    "McpToolSession",
    "ToolCallOutcome",
    "ToolLister",
    "ToolsPage",
    "ensure_tools_capability",
    "paginate_tool_descriptors",
]


class ToolsPage(TypedDict):
    """Una página de `tools/list`: lo mínimo que necesita el paginador.

    Shape idéntico al `result` de un mensaje JSON-RPC `tools/list` (ver
    `tests/contracts/tools_mcp/fixtures/canonical_responses.py`), para poder
    usar esas constantes directamente como páginas en los tests.
    """

    tools: Sequence[Any]
    nextCursor: NotRequired[str | None]


type ToolLister = Callable[[str | None], Awaitable[ToolsPage]]


async def paginate_tool_descriptors(lister: ToolLister) -> tuple[ToolDescriptor, ...]:
    """Recorre todas las páginas de `tools/list` siguiendo `cursor`/`nextCursor`.

    `lister` es cualquier callable asíncrono `cursor -> página`; no depende de
    una `ClientSession` real, lo que permite testear la paginación completa
    con un stub sobre las respuestas canónicas de los fixtures. Cada Tool
    cruda se parsea con `parse_tool_descriptor`; las que no tengan un
    `inputSchema` válido se descartan en silencio (Escenario "Descriptor sin
    inputSchema válido rechazado").
    """
    descriptors: list[ToolDescriptor] = []
    cursor: str | None = None
    while True:
        page = await lister(cursor)
        for raw_tool in page["tools"]:
            descriptor = parse_tool_descriptor(raw_tool)
            if descriptor is not None:
                descriptors.append(descriptor)
        next_cursor = page.get("nextCursor")
        if not next_cursor:
            break
        cursor = next_cursor
    return tuple(descriptors)


def ensure_tools_capability(init_result: InitializeResult) -> None:
    """Verifica que el server declaró la capability `tools` en su `InitializeResult`.

    El cliente MUST quedar listo para operar solo si el server declara esta
    capability (Escenario "Conexión e initialize con negociación de
    capacidades"); si no, lanza `McpCapabilityError`.
    """
    if init_result.capabilities.tools is None:
        raise McpCapabilityError(
            "El MCP Server no declaró la capability 'tools' en su InitializeResult "
            "(capabilities.tools es None); el cliente MCP no puede listar ni invocar Tools."
        )


@dataclass(frozen=True, slots=True)
class ToolCallOutcome:
    """Resultado tipado y ya parseado de una invocación `tools/call`.

    - `content`: texto plano de todos los bloques `TextContent` del
      `CallToolResult`, concatenados con saltos de línea. Otros tipos de
      bloque (imagen, audio, resource, resource_link) no aportan a `content`
      pero siguen accesibles en `raw.content`.
    - `structured_content`: `structuredContent` del `CallToolResult` tal
      cual. Cuando el descriptor invocado declara `outputSchema`, el SDK
      (`mcp==1.28.1`) ya valida `structuredContent` contra ese schema dentro
      de `ClientSession.call_tool` (`_validate_tool_result`, verificado en
      `compliance-mcp-2025-11-25.md` punto 3) antes de devolver el resultado;
      este tipo no repite esa validación.
    - `is_error`: `isError` del `CallToolResult`. Un `is_error=True` es un
      Tool Execution Error (spec §Error Handling), NUNCA un éxito — la tarea
      1.7 refina el modelo de error encima de este campo.
    - `raw`: el `CallToolResult` original del SDK, por si algún consumidor
      necesita el detalle completo (otros tipos de bloque, `_meta`, etc.).
    """

    content: str
    structured_content: dict[str, Any] | None
    is_error: bool
    raw: CallToolResult


def _parse_call_tool_result(result: CallToolResult) -> ToolCallOutcome:
    """Parsea un `CallToolResult` del SDK en un `ToolCallOutcome`."""
    text_parts = [block.text for block in result.content if isinstance(block, TextContent)]
    return ToolCallOutcome(
        content="\n".join(text_parts),
        structured_content=result.structuredContent,
        is_error=result.isError,
        raw=result,
    )


def _validate_arguments_or_raise(
    name: str,
    arguments: Mapping[str, Any],
    descriptor: ToolDescriptor,
) -> None:
    """Valida `arguments` contra `descriptor.input_schema` ANTES de emitir `tools/call`.

    Si la validación falla, lanza `ToolArgumentValidationError` con un
    mensaje accionable (Tool, ruta del campo, motivo) y el llamador NUNCA
    llega a invocar `ClientSession.call_tool` (Escenario "Argumentos que no
    cumplen el inputSchema no se envían").
    """
    try:
        jsonschema.validate(instance=dict(arguments), schema=descriptor.input_schema)
    except jsonschema.exceptions.ValidationError as exc:
        raise ToolArgumentValidationError(
            tool_name=name,
            message=(
                f"Los argumentos para la Tool {name!r} no cumplen su inputSchema "
                f"en la ruta {list(exc.path)!r}: {exc.message}."
            ),
        ) from exc


class McpToolSession:
    """Async context manager sobre un transport MCP + `mcp.ClientSession`.

    Uso:

        async with McpToolSession(transport_config) as session:
            descriptors = await session.list_tools()
            outcome = await session.call_tool(name, arguments, descriptor)

    Reutilizable por el executor gobernado de la sección 2 de este change:
    `McpToolClient` (`client.py`) la usa internamente, pero también se expone
    aquí como API async pública.
    """

    def __init__(self, transport: TransportConfig) -> None:
        self._transport_config = transport
        self._exit_stack: contextlib.AsyncExitStack | None = None
        self._session: ClientSession | None = None

    async def __aenter__(self) -> Self:
        exit_stack = contextlib.AsyncExitStack()
        try:
            read_stream, write_stream = await exit_stack.enter_async_context(
                open_transport(self._transport_config)
            )
            session = await exit_stack.enter_async_context(ClientSession(read_stream, write_stream))
            init_result = await session.initialize()
            ensure_tools_capability(init_result)
        except BaseException:
            await exit_stack.aclose()
            raise

        self._exit_stack = exit_stack
        self._session = session
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if self._exit_stack is not None:
            await self._exit_stack.aclose()
        self._exit_stack = None
        self._session = None

    @property
    def session(self) -> ClientSession:
        """La `mcp.ClientSession` subyacente ya inicializada.

        Lanza `RuntimeError` si se accede fuera de un bloque `async with`.
        """
        if self._session is None:
            raise RuntimeError("McpToolSession no está abierta: úsala dentro de 'async with'.")
        return self._session

    async def list_tools(self) -> tuple[ToolDescriptor, ...]:
        """Descubre todas las Tools del server, recorriendo la paginación completa."""

        async def _lister(cursor: str | None) -> ToolsPage:
            result = await self.session.list_tools(params=PaginatedRequestParams(cursor=cursor))
            return {"tools": result.tools, "nextCursor": result.nextCursor}

        return await paginate_tool_descriptors(_lister)

    async def call_tool(
        self,
        name: str,
        arguments: dict[str, Any],
        descriptor: ToolDescriptor,
    ) -> ToolCallOutcome:
        """Invoca `tools/call` tras validar `arguments` contra `descriptor.input_schema`."""
        _validate_arguments_or_raise(name, arguments, descriptor)
        result = await self.session.call_tool(name, arguments)
        return _parse_call_tool_result(result)
