# Checklist de compliance — MCP revisión 2025-11-25 vs SDK oficial `mcp==1.28.1`

**Change:** `c09-mcp-tools` · **Tarea:** 1.1 (compliance de la spec MCP).
**Revisión de la spec fijada:** MCP **2025-11-25** (la más reciente; confirmada como `current` en modelcontextprotocol.io/specification/versioning).
**SDK fijado (pin):** `mcp==1.28.1` en `[project].dependencies` de `pyproject.toml` (última estable en PyPI; la `2.0.0` está solo en beta y **no** se usa).
**Verificación del pin de protocolo del SDK:**

```
>>> import mcp.types as t
>>> t.LATEST_PROTOCOL_VERSION
'2025-11-25'
>>> from mcp.client.session import SUPPORTED_PROTOCOL_VERSIONS
>>> SUPPORTED_PROTOCOL_VERSIONS
['2024-11-05', '2025-03-26', '2025-06-18', '2025-11-25']
```

El SDK 1.28.1 declara `2025-11-25` como `LATEST_PROTOCOL_VERSION` y la incluye en `SUPPORTED_PROTOCOL_VERSIONS`. **El SDK está al día con la revisión fijada: no hay desfase de versión de protocolo.**

> Nota de defensa en profundidad: la constante `DEFAULT_NEGOTIATED_VERSION` del SDK es `2025-03-26` (fallback para transports HTTP legacy sin header de versión), pero el `ClientSession.initialize()` envía siempre `protocolVersion=LATEST_PROTOCOL_VERSION` (2025-11-25) en la petición `initialize`. El default legacy no afecta a nuestra negociación cliente→servidor.

---

## Tabla de compliance

| # | Punto de la spec 2025-11-25 | Cobertura en el SDK 1.28.1 (clase / módulo concreto) | Estado |
|---|---|---|---|
| 1 | **Lifecycle: `initialize` + negociación de capacidades + `notifications/initialized`** | `mcp.client.session.ClientSession.initialize()` envía `InitializeRequest` con `protocolVersion=LATEST_PROTOCOL_VERSION` (2025-11-25), `clientInfo` (`Implementation`) y `capabilities` (`ClientCapabilities`: `sampling`, `elicitation`, `roots`, `tasks`, `experimental`); recibe `InitializeResult` (`protocolVersion`, `capabilities`=`ServerCapabilities` con `tools`/`prompts`/`resources`/`logging`/`completions`/`tasks`, `serverInfo`, `instructions`); valida `result.protocolVersion in SUPPORTED_PROTOCOL_VERSIONS` (si no, `RuntimeError`); y emite `ClientNotification(InitializedNotification())` = `notifications/initialized`. Capacidades del servidor consultables luego con `get_server_capabilities()`. | **Cumple** |
| 2 | **`tools/list` con paginación (`cursor` / `nextCursor`)** | `ClientSession.list_tools(cursor: str | None = None, *, params: PaginatedRequestParams | None = None) -> ListToolsResult`. `PaginatedRequestParams` expone `cursor`; `ListToolsResult` expone `nextCursor` y `tools: list[Tool]`. El bucle de paginación se conduce pasando el `nextCursor` recibido como `cursor` de la siguiente llamada. | **Cumple** |
| 3 | **`tools/call` con `inputSchema` / `outputSchema` y resultado `content` / `structuredContent` / `isError`** | `ClientSession.call_tool(name, arguments, ...) -> CallToolResult`. `Tool` declara `inputSchema: dict[str, Any]` (obligatorio) y `outputSchema: dict[str, Any] | None` (JSON Schema 2020-12). `CallToolResult` expone `content: list[TextContent | ImageContent | AudioContent | ResourceLink | EmbeddedResource]`, `structuredContent: dict[str, Any] | None` e `isError: bool` (default `False`). | **Cumple** |
| 4 | **Transport stdio** (subproceso local) | `mcp.client.stdio.stdio_client(...)` + `StdioServerParameters` (`command`, `args`, `env`, `cwd`, `encoding`, `encoding_error_handler`). Incluye gestión de entorno por defecto (`get_default_environment`) y terminación de árbol de procesos POSIX/Windows. | **Cumple** |
| 5 | **Transport Streamable HTTP** (endpoint único, headers `MCP-Protocol-Version` y `MCP-Session-Id`) | `mcp.client.streamable_http.streamablehttp_client(...)` + `StreamableHTTPTransport`. Constantes de header: `MCP_PROTOCOL_VERSION = "mcp-protocol-version"`, `MCP_SESSION_ID = "mcp-session-id"`, `LAST_EVENT_ID = "last-event-id"` (reanudación SSE), `ACCEPT`/`CONTENT_TYPE` con `application/json` + `text/event-stream`. Soporta SSE (`aconnect_sse`, `ServerSentEvent`), reconexión (`DEFAULT_RECONNECTION_DELAY_MS`, `MAX_RECONNECTION_ATTEMPTS`) y `GetSessionIdCallback`. | **Cumple** |
| 6 | **Modelo de error doble: Protocol Errors (JSON-RPC) vs Tool Execution Errors (`isError: true`)** | Protocol Errors: `mcp.shared.exceptions.McpError` (subclase de `Exception`) porta `ErrorData` (`code`, `message`, `data`); códigos JSON-RPC estándar en `mcp.types`: `PARSE_ERROR=-32700`, `INVALID_REQUEST=-32600`, `METHOD_NOT_FOUND=-32601`, `INVALID_PARAMS=-32602`, `INTERNAL_ERROR=-32603`. Tool Execution Errors: `CallToolResult.isError=True` con el detalle del fallo en `content` (no lanza excepción). Ambos mecanismos están claramente separados en el SDK. | **Cumple** |
| 7 | **§Tool Safety — `annotations` no confiables salvo server de confianza** | El SDK modela `Tool.annotations` = `ToolAnnotations` (`readOnlyHint`, `destructiveHint`, `idempotentHint`, `openWorldHint`) como campos **descriptivos** sin valor de seguridad forzado. **Decisión del proyecto (Decision 3 del `design.md`): la clasificación autoritativa vive en el `ToolManifest`** (`operation_type`, `risk.level` por `version`); el cliente MCP **nunca** deriva la clasificación de las `annotations` del server. Esto es defensa en profundidad: un server comprometido no puede rebajarse a "solo lectura". | **Cumple** (por diseño del proyecto; el SDK aporta el tipo, la autoridad la fija el manifiesto) |

---

## Desvíos del SDK respecto a la revisión 2025-11-25

**Ninguno.** El SDK `mcp==1.28.1` cubre íntegramente los puntos usados por este change:

- `LATEST_PROTOCOL_VERSION == "2025-11-25"` y esa revisión está en `SUPPORTED_PROTOCOL_VERSIONS`: no hay desfase de versión.
- Lifecycle, `tools/list` con paginación, `tools/call` con `inputSchema`/`outputSchema`/`content`/`structuredContent`/`isError`, ambos transports (stdio y Streamable HTTP con los headers `mcp-protocol-version`/`mcp-session-id`) y el modelo de error dual JSON-RPC vs `isError` están presentes con las clases/módulos indicados.

**Aclaraciones (no son desvíos):**

1. **`DEFAULT_NEGOTIATED_VERSION = "2025-03-26"`** en `mcp.types`: es solo el fallback de negociación para transports HTTP que no envían header de versión; el cliente inicia siempre con `2025-11-25`. Sin impacto en el compliance.
2. **`ToolAnnotations` como campo del SDK**: la spec las declara no confiables. No es un desvío del SDK sino un principio de la propia spec; lo mitigamos con la Decision 3 (autoridad en el `ToolManifest`), reforzando la postura de seguridad más allá de lo que ofrece el SDK.
3. **Alcance intencionadamente reducido** (Non-Goals del change): Resources, Prompts y client features (Sampling, Roots, Elicitation) existen en el SDK pero **no** se usan en `c09`; solo Tools. No afecta al compliance del subconjunto Tools.

---

## Estado de la verificación

| Comando | Resultado |
|---|---|
| `uv sync` (con `mcp==1.28.1`) | Verde — `+ mcp==1.28.1` instalado (122 paquetes resueltos). |
| `uv run lint-imports` | 3 contratos KEPT, 0 broken. La regla "El nucleo no conoce el mundo exterior" ahora incluye `mcp` en `forbidden_modules` (core no puede importar el SDK MCP). |
| `uv run pytest` | 274 passed (al momento de la tarea 1.1; al cierre del change: 339 passed). |
| `uv run ruff check .` | All checks passed. |
| `uv run ruff format --check .` | 124 files already formatted (al cierre del change: 153). |
