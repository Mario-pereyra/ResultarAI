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
from mcp.shared.exceptions import McpError
from mcp.types import CallToolResult, InitializeResult, PaginatedRequestParams, TextContent

from resultarai.adapters.tools_mcp.descriptors import ToolDescriptor, parse_tool_descriptor
from resultarai.adapters.tools_mcp.errors import McpCapabilityError, ToolArgumentValidationError
from resultarai.adapters.tools_mcp.transports import TransportConfig, open_transport

__all__ = [
    "McpToolSession",
    "ToolCallOutcome",
    "ToolExecutionFailure",
    "ToolLister",
    "ToolProtocolFailure",
    "ToolsPage",
    "ensure_tools_capability",
    "paginate_tool_descriptors",
    "parse_call_tool_result",
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
    """Resultado tipado de una invocación `tools/call` **exitosa** (`isError: false`).

    Un `ToolCallOutcome` representa SIEMPRE un éxito: no tiene campo `is_error`,
    así que por construcción NUNCA puede confundirse con un Tool Execution
    Error. El caso `isError: true` es un tipo distinto (`ToolExecutionFailure`)
    y el fallo de protocolo JSON-RPC es otro más (`ToolProtocolFailure`);
    `parse_call_tool_result` decide cuál emitir según `CallToolResult.isError`
    (Requirement "Manejo de errores diferenciado", tarea 1.7).

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
    - `raw`: el `CallToolResult` original del SDK, por si algún consumidor
      necesita el detalle completo (otros tipos de bloque, `_meta`, etc.).
    """

    content: str
    structured_content: dict[str, Any] | None
    raw: CallToolResult


@dataclass(frozen=True, slots=True)
class ToolExecutionFailure:
    """Tool Execution Error: la Tool se ejecutó y devolvió `CallToolResult` con `isError: true`.

    Es un fallo *de la Tool*, no del protocolo: el `tools/call` llegó al server
    y volvió con un resultado, solo que ese resultado señala que la ejecución
    falló (spec §Tool Execution Errors). NUNCA es un éxito — es un tipo
    distinto de `ToolCallOutcome`, de modo que confundirlos es imposible
    (Escenario "Tool Execution Error con feedback accionable").

    - `message`: el texto accionable del `content` (bloques `TextContent`
      concatenados), conservado ÍNTEGRO para que el modelo pueda reaccionar
      —no se trunca ni se resume aquí.
    - `structured_content`: `structuredContent` del resultado si el server lo
      incluyó junto al error, tal cual.
    - `raw`: el `CallToolResult` crudo del SDK (con `isError=True`), para la
      capa de auditoría de la sección 2.
    """

    tool_name: str
    message: str
    structured_content: dict[str, Any] | None
    raw: CallToolResult


@dataclass(frozen=True, slots=True)
class ToolProtocolFailure:
    """Protocol Error JSON-RPC: el server respondió `tools/call` con un error de protocolo.

    Mecanismo de error DISTINTO del Tool Execution Error: aquí la petición
    misma falló a nivel JSON-RPC (Tool desconocida, request mal formado, error
    interno del server), el SDK lo señala lanzando `mcp.shared.exceptions.
    McpError` (con `ErrorData: code/message`) en vez de devolver un
    `CallToolResult`. No hay resultado de Tool que exponer, solo el `code`
    JSON-RPC (p. ej. `-32602` = INVALID_PARAMS) y el `message` del server
    (Escenario "Protocol Error de Tool desconocida").

    `code`/`message` quedan disponibles para que la capa de auditoría de la
    sección 2 los registre en el `AuditEvent`.
    """

    tool_name: str
    code: int
    message: str

    @classmethod
    def from_mcp_error(cls, tool_name: str, error: McpError) -> ToolProtocolFailure:
        """Construye el fallo tipado desde el `McpError` (JSON-RPC) del SDK."""
        return cls(tool_name=tool_name, code=error.error.code, message=error.error.message)


def parse_call_tool_result(
    tool_name: str, result: CallToolResult
) -> ToolCallOutcome | ToolExecutionFailure:
    """Parsea un `CallToolResult` del SDK en el tipo tipado que corresponde.

    Función pura (sin server ni red): mapea el resultado a `ToolCallOutcome`
    cuando `isError` es falso, o a `ToolExecutionFailure` cuando es verdadero.
    El `isError: true` NUNCA se confunde con un éxito: es un tipo de retorno
    distinto (Requirement "Manejo de errores diferenciado"). Los Protocol
    Errors JSON-RPC no llegan aquí: el SDK los lanza como `McpError` antes de
    producir un `CallToolResult`.
    """
    text = "\n".join(block.text for block in result.content if isinstance(block, TextContent))
    if result.isError:
        return ToolExecutionFailure(
            tool_name=tool_name,
            message=text,
            structured_content=result.structuredContent,
            raw=result,
        )
    return ToolCallOutcome(
        content=text,
        structured_content=result.structuredContent,
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
    ) -> ToolCallOutcome | ToolExecutionFailure:
        """Invoca `tools/call` tras validar `arguments` contra `descriptor.input_schema`.

        Devuelve `ToolCallOutcome` en el éxito o `ToolExecutionFailure` cuando
        el server responde con `isError: true` (Tool Execution Error). Los
        Protocol Errors JSON-RPC (`McpError`) NO se capturan aquí: se dejan
        propagar como excepción —son fallos de la petición, no resultados de la
        Tool— y el `McpToolClient` (frontera del `ToolPort`) los mapea a
        `ToolProtocolFailure`. Así la sesión refleja fielmente el modelo de
        error dual del SDK (excepción vs `isError`).
        """
        _validate_arguments_or_raise(name, arguments, descriptor)
        result = await self.session.call_tool(name, arguments)
        return parse_call_tool_result(name, result)
