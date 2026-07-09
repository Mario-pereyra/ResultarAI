# mcp-tools — Delta Spec (c09-mcp-tools)

## ADDED Requirements

### Requirement: Cliente MCP conforme a la spec MCP revisión 2025-11-25 detrás del ToolPort

El sistema SHALL implementar en `adapters/tools_mcp` un cliente MCP conforme a la spec oficial MCP **revisión 2025-11-25**, que implemente el `ToolPort` definido en `core/ports/` (`a03`). El cliente MUST realizar el lifecycle de la spec —`initialize` con negociación de capacidades y la notificación `notifications/initialized`— antes de listar o invocar Tools. El cliente MUST vivir solo en `adapters/`: `core/` no lo importa (regla de dependencia de `docs/02-arquitectura.md`).

#### Scenario: Conexión e initialize con negociación de capacidades

- **WHEN** el cliente MCP se conecta a un MCP Server y envía `initialize`
- **THEN** completa el handshake (recibe `InitializeResult` con la capability `tools`, envía `notifications/initialized`) y queda listo para operar solo si el server declara la capability `tools`

#### Scenario: El cliente MCP no vive en core

- **WHEN** se ejecuta `uv run lint-imports` tras añadir el cliente MCP
- **THEN** el contrato "core sin frameworks" reporta KEPT y el exit code es 0 (MCP vive solo en `adapters/tools_mcp` detrás del `ToolPort`)

### Requirement: Descubrimiento de Tools vía tools/list con paginación

El cliente MCP SHALL descubrir las Tools de un MCP Server mediante `tools/list`, y MUST soportar la paginación de la spec (parámetro `cursor` y campo `nextCursor`) recorriendo todas las páginas. Cada descriptor de Tool MUST exponer `name`, `description`, `inputSchema` y, cuando el server lo provea, `outputSchema`.

#### Scenario: Listado completo con paginación

- **WHEN** un MCP Server devuelve su catálogo de Tools en varias páginas con `nextCursor`
- **THEN** el cliente recorre todas las páginas siguiendo el `cursor` hasta agotarlas y expone el conjunto completo de descriptores tipados

#### Scenario: Descriptor sin inputSchema válido rechazado

- **WHEN** un descriptor de Tool trae un `inputSchema` que no es un objeto JSON Schema válido (p. ej. `null`)
- **THEN** el cliente lo marca como no utilizable y no lo ofrece para invocación

### Requirement: Invocación tipada de Tools vía tools/call

El cliente MCP SHALL invocar Tools con `tools/call` enviando `name` y `arguments`, validando los `arguments` contra el `inputSchema` del descriptor antes de emitir la llamada. El cliente MUST parsear el `CallToolResult` distinguiendo `content` (no estructurado), `structuredContent` (estructurado) e `isError`, y —cuando el descriptor declare `outputSchema`— MUST validar el `structuredContent` contra ese schema. Toda invocación de Tool se realiza vía una Skill (regla dura 3); el Default Chat nunca invoca directamente.

#### Scenario: Invocación de lectura autorizada devuelve resultado tipado

- **WHEN** una Skill invoca una Tool de lectura cuyo `ToolManifest` está activo y el Policy Gate devuelve `allow`
- **THEN** el cliente emite `tools/call`, recibe un `CallToolResult` con `isError: false` y expone `content` y, si aplica, `structuredContent` validado contra el `outputSchema`

#### Scenario: Argumentos que no cumplen el inputSchema no se envían

- **WHEN** el Policy Gate devolvió `allow` para una Tool de lectura pero los `arguments` provistos no cumplen su `inputSchema`
- **THEN** el cliente NO emite `tools/call`, devuelve un fallo de validación accionable y el intento queda registrado en un `AuditEvent`

### Requirement: Transports stdio y Streamable HTTP

El cliente MCP SHALL soportar los dos transports estándar de la spec 2025-11-25: **stdio** (el cliente lanza el MCP Server como subproceso e intercambia mensajes JSON-RPC delimitados por saltos de línea por `stdin`/`stdout`, sin newlines embebidos) y **Streamable HTTP** (un único MCP endpoint con POST y GET/SSE). En Streamable HTTP el cliente MUST incluir el header `MCP-Protocol-Version` en cada request tras el `initialize` y MUST propagar el `MCP-Session-Id` cuando el server lo asigne.

#### Scenario: MCP Server local por stdio

- **WHEN** el cliente se configura con un MCP Server por transport stdio
- **THEN** lanza el server como subproceso, intercambia mensajes JSON-RPC newline-delimited por `stdin`/`stdout` y trata `stderr` como logging (no como condición de error)

#### Scenario: MCP Server remoto por Streamable HTTP

- **WHEN** el cliente se configura con un MCP Server por transport Streamable HTTP que asigna `MCP-Session-Id` en el `InitializeResult`
- **THEN** el cliente incluye `MCP-Protocol-Version` y `MCP-Session-Id` en todas las requests siguientes y acepta tanto respuestas `application/json` como streams `text/event-stream`

### Requirement: Manejo de errores diferenciado (Protocol vs Tool Execution)

El cliente MCP SHALL distinguir los dos mecanismos de error de la spec: **Protocol Errors** (errores JSON-RPC: Tool desconocida, request mal formado, error de server — p. ej. código `-32602`) y **Tool Execution Errors** (resultado con `isError: true`). Ambos MUST mapearse a un resultado tipado del `ToolPort` y ambos MUST quedar registrados en un `AuditEvent`; el cliente MUST NOT confundir un `isError: true` con un éxito.

#### Scenario: Protocol Error de Tool desconocida

- **WHEN** una Skill (con Policy Gate `allow`) invoca por `tools/call` un `name` que el server no expone y el server responde con un error JSON-RPC (`-32602`)
- **THEN** el cliente lo mapea a un fallo de Protocol del `ToolPort`, no lo trata como resultado válido y emite un `AuditEvent` con la decisión `allow` y el error observado

#### Scenario: Tool Execution Error con feedback accionable

- **WHEN** una Tool autorizada (Policy Gate `allow`) se ejecuta y el server devuelve un `CallToolResult` con `isError: true` y un mensaje de error de negocio
- **THEN** el cliente expone ese resultado como error de ejecución (no como éxito), conserva el mensaje accionable para el modelo y emite un `AuditEvent`

### Requirement: MCP Server de ejemplo de fábrica

El change SHALL incluir un MCP Server de ejemplo de fábrica: un server sencillo de utilidades ejecutable por transport stdio, con al menos una Tool de lectura (p. ej. fecha/hora, cálculo o echo) y al menos una Tool de "escritura" simulada sin efecto real, destinada a ejercer el camino `escalate_hitl`. El server MUST servir de plantilla para los MCP Servers reales de la Etapa P y MUST NOT tocar el ERP ni la ERP Safe Query API.

#### Scenario: El server de ejemplo expone lectura y escritura simulada

- **WHEN** el cliente hace `tools/list` contra el MCP Server de ejemplo
- **THEN** el catálogo incluye al menos una Tool clasificable como lectura y al menos una Tool de escritura simulada, cada una con su `inputSchema` válido

#### Scenario: La escritura simulada no produce efecto real

- **WHEN** se invoca la Tool de escritura simulada del server de ejemplo (tras el tratamiento de gobernanza correspondiente)
- **THEN** el server no altera ningún sistema externo (efecto simulado) y sirve solo para probar el camino de gobernanza de escrituras
