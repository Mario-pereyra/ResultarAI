# Tasks — c09-mcp-tools

## 1. Cliente MCP (adapters/tools_mcp) conforme a la spec 2025-11-25

- [x] 1.1 Verificación de compliance con la spec MCP revisión 2025-11-25: fijar el pin del SDK oficial de MCP para Python en `pyproject.toml` y documentar (checklist en el PR) que lifecycle, `tools/list`, `tools/call`, transports y modelo de errores cumplen la revisión fijada, marcando cualquier desvío del SDK. Verificación: checklist de compliance completa y `uv sync` en verde. `[modelo: opus]`
- [x] 1.2 Adapter del cliente MCP que implementa el `ToolPort` (`a03`): lifecycle `initialize` + negociación de capacidades + `notifications/initialized`; requiere la capability `tools`. Verificación: test de conexión contra un MCP Server de prueba y `uv run lint-imports` con "core sin frameworks" en KEPT (escenario "El cliente MCP no vive en core"). `[modelo: sonnet]`
- [x] 1.3 Descubrimiento de Tools: `tools/list` con paginación (`cursor`/`nextCursor`) recorriendo todas las páginas; mapeo a descriptores tipados con `name`/`description`/`inputSchema`/`outputSchema`; descarte de `inputSchema` inválido. Verificación: tests de "Listado completo con paginación" y "Descriptor sin inputSchema válido rechazado". `[modelo: sonnet]`
- [x] 1.4 Invocación tipada: `tools/call` con validación de `arguments` contra `inputSchema`; parseo de `CallToolResult` (`content`/`structuredContent`/`isError`) y validación de `structuredContent` contra `outputSchema`. Verificación: tests de "Invocación de lectura autorizada devuelve resultado tipado" y "Argumentos que no cumplen el inputSchema no se envían". `[modelo: sonnet]`
- [x] 1.5 Transport stdio: lanzar el MCP Server como subproceso, intercambio JSON-RPC newline-delimited por `stdin`/`stdout`, `stderr` tratado como logging. Verificación: test del escenario "MCP Server local por stdio" contra el server de ejemplo. `[modelo: sonnet]`
- [x] 1.6 Transport Streamable HTTP: endpoint único POST + GET/SSE; headers `MCP-Protocol-Version` y `MCP-Session-Id` en cada request tras `initialize`; aceptar `application/json` y `text/event-stream`. Verificación: test del escenario "MCP Server remoto por Streamable HTTP" contra un server de prueba HTTP mínimo. `[modelo: sonnet]`
- [x] 1.7 Manejo de errores diferenciado: mapear Protocol Errors (JSON-RPC, p. ej. `-32602`) y Tool Execution Errors (`isError: true`) a resultados tipados distintos del `ToolPort`, sin confundir `isError: true` con éxito. Verificación: tests de "Protocol Error de Tool desconocida" y "Tool Execution Error con feedback accionable". `[modelo: opus]`

## 2. Binding con el Tool Registry y ejecución gobernada

- [x] 2.1 Binding `ToolManifest` → (MCP Server + `tool_name`) sobre el `ToolRegistry` (`a02`): solo Tools de un `ToolManifest` `active` existen; una Tool del server sin manifiesto activo no es invocable ni consulta al Policy Gate. Verificación: tests de "Tool del server sin ToolManifest activo no existe" y "Tool con ToolManifest activo sí es invocable". `[modelo: opus]`
- [x] 2.2 Clasificación autoritativa e inmutable: `operation_type` y `risk.level` se leen del manifiesto por `version`; las `annotations` del server se ignoran (no confiables); no hay reclasificación en runtime. Verificación: tests de "El binding resuelve server y tool_name desde el manifiesto", "La clasificación no se puede cambiar en runtime" y "Las annotations del server no alteran la clasificación". `[modelo: opus]`
- [x] 2.3 Validación cruzada del binding: al pasar a `active`, verificar que el `tool_name` del manifiesto existe en el `tools/list` del server. Verificación: test de "tool_name inexistente en el server invalida el binding". `[modelo: sonnet]`
- [x] 2.4 Ejecución gobernada: consultar el Policy Gate antes de cada `tools/call`; lectura→`allow` (si Policy permite) / deny-by-default; escritura→`escalate_hitl` SIEMPRE sin emitir `tools/call` (evento en espera); emitir un `AuditEvent` por cada decisión. Verificación: tests de "Lectura permitida se ejecuta y se audita", "Lectura sin Policy que la permita se bloquea", "Escritura escala a HITL siempre y no se ejecuta" y "La tool de lectura del server de ejemplo corre end-to-end". `[modelo: opus]`

## 3. Tool calls visibles

- [x] 3.1 Contrato de datos de la Tool call visible como proyección del `AuditEvent`: nombre de Tool, argumentos, resultado truncado (con marca) y duración; colapsable/expandible (ref `design/FUNCIONALIDADES.md` §4). Verificación: tests de "Cada invocación produce un registro visible colapsable" y "Truncado del resultado en el registro visible". `[modelo: sonnet]`
- [x] 3.2 Capa por rol y estado de gobernanza en el registro visible: Funcional=lenguaje simple sin parámetros completos; Técnico/Admin=parámetros completos; escritura escalada = "en espera de aprobación", lectura `allow` = "ejecutada" (ref §4 y §12). Verificación: tests de "Funcional ve lenguaje simple", "Técnico y Admin ven parámetros completos", "Escritura escalada se muestra en espera de aprobación" y "Lectura permitida se muestra como ejecutada". `[modelo: sonnet]`

## 4. MCP Server de ejemplo de fábrica y manifiestos

- [x] 4.1 MCP Server de ejemplo de utilidades ejecutable por stdio con Tools de lectura (fecha/hora, cálculo, echo), cada una con `inputSchema` válido; sin tocar el ERP. Verificación: test de "El server de ejemplo expone lectura y escritura simulada" (parte lectura). `[modelo: sonnet]`
- [x] 4.2 Tool de "escritura" simulada en el server de ejemplo (sin efecto real) para ejercer el camino `escalate_hitl`. Verificación: test de "La escritura simulada no produce efecto real". `[modelo: sonnet]`
- [x] 4.3 `ToolManifest` de fábrica en `manifests/tools/` que bindean el server de ejemplo (1 lectura + 1 escritura simulada) con clasificación fija por `version` (`operation_type`, `risk.level`); validación contra el schema de `a02`. Verificación: los manifiestos validan en CI y pasan la validación cruzada (`tool_name` existe en el server). `[modelo: haiku]`
- [x] 4.4 Fixtures de prueba: MCP Server de prueba (stdio y HTTP) y respuestas JSON-RPC canónicas (paginación, `isError`, Protocol Error) para los tests del cliente, sin red externa. Verificación: los fixtures cargan y los tests de la sección 1 corren en verde offline. `[modelo: haiku]`

## 5. Cierre

- [ ] 5.1 Review final del change: conformidad con la spec MCP 2025-11-25, clasificación inmutable en runtime, toda invocación por Policy Gate + `AuditEvent`, cero lógica MCP en `core/` (import-linter KEPT) y coherencia specs↔tasks. Verificación: checklist del reviewer en el PR con los 5 comandos de calidad en verde. `[modelo: opus]`
