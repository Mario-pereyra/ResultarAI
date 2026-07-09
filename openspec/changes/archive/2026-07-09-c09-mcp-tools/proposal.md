# Proposal — c09-mcp-tools

## Why

La regla dura 3 del proyecto exige que las Tools solo se ejecuten vía Skills y que el Default Chat nunca las invoque directamente; la regla dura 6 exige que toda Tool tenga manifiesto versionado. `a02-core-manifiestos` definió el `ToolManifest` (referencia a un MCP Server + `tool_name` + clasificación) y el `ToolRegistry`; `a03-core-gobernanza` definió el `ToolPort`, el Policy Gate y el `AuditEvent`. Falta el eslabón que hace que esos contratos ejecuten algo real: un cliente MCP que se conecte a servers, descubra e invoque Tools conforme a la spec oficial, gobernado por el Policy Gate y auditado. Sin él, la Etapa C queda a medias (`c08-agent-skills` activa Skills que no tienen cómo tocar una Tool) y la personalización Protheus de la Etapa P no tiene sobre qué apoyarse.

## What Changes

- Se añade el **cliente MCP** en `adapters/tools_mcp`, detrás del `ToolPort` de `a03`, conforme a la spec oficial MCP **revisión 2025-11-25**: negociación de capacidades e `initialize` (lifecycle), descubrimiento de Tools (`tools/list` con paginación), invocación tipada (`tools/call` con `inputSchema`/`outputSchema`, `content`/`structuredContent`/`isError`) y los dos transports estándar **stdio** y **Streamable HTTP**.
- Se añade el **manejo de errores diferenciado** de la spec: Protocol Errors (errores JSON-RPC: Tool desconocida, request mal formado, error de server) frente a Tool Execution Errors (resultado con `isError: true`), mapeados al resultado del `ToolPort` y ambos auditados.
- Se añade el **binding con el Tool Registry** (`a02`): solo las Tools declaradas en un `ToolManifest` activo existen para el runtime; el manifiesto fija MCP Server + `tool_name` + clasificación `operation_type` (lectura/escritura) + `risk.level`, **inmutable en runtime** (cambiarla = nueva `version` = PR). Las `annotations` que provee el MCP Server se tratan como no confiables (spec MCP §Tool Safety) y **no** alteran la clasificación del manifiesto.
- Se añade la **ejecución gobernada**: toda invocación se autoriza en el Policy Gate antes de emitir `tools/call` (lecturas → `allow` directo cuando la Policy lo permite; escrituras → `escalate_hitl` SIEMPRE, la Tarjeta HITL llega en `d17` y aquí el evento queda en espera sin efecto real) y toda invocación emite un `AuditEvent`.
- Se añade el contrato de **Tool calls visibles**: cada invocación produce un registro para que la UI la muestre colapsada/expandible (Tool, argumentos, resultado truncado, duración), con capa por rol (lenguaje simple para Funcional; parámetros completos para Técnico/Admin), conforme a `design/FUNCIONALIDADES.md` §4.
- Se añade un **MCP Server de ejemplo de fábrica**: server sencillo de utilidades (fecha/hora, cálculo, echo) con al menos 1 Tool de lectura y 1 Tool de "escritura" simulada (para ejercer el camino `escalate_hitl` sin efecto real); sirve de plantilla para los servers reales de la Etapa P. Sus `ToolManifest` de fábrica lo bindean con clasificación fija.

## Capabilities

### New Capabilities

- `mcp-tools`: cliente MCP conforme a la spec MCP revisión 2025-11-25 detrás del `ToolPort` (lifecycle e `initialize`, `tools/list`, `tools/call` con schemas tipados), transports stdio y Streamable HTTP, manejo de errores diferenciado (Protocol vs Tool Execution) y el MCP Server de ejemplo de fábrica.
- `tool-registry-binding`: binding `ToolManifest` → (MCP Server + `tool_name`); regla "solo lo declarado en un manifiesto activo existe"; clasificación `operation_type` + `risk.level` autoritativa desde el manifiesto e inmutable en runtime; ejecución gobernada por el Policy Gate (lectura→`allow`, escritura→`escalate_hitl` SIEMPRE) con emisión de `AuditEvent`.
- `tool-call-visibility`: contrato de datos de la Tool call visible (Tool, argumentos, resultado truncado, duración; colapsada/expandible) con capa por rol (Funcional / Técnico / Admin), derivado de la invocación y su `AuditEvent`.

### Modified Capabilities

*(ninguna — `openspec/specs/` está vacío; este change no modifica requirements existentes. Consume `ToolManifest`/`ToolRegistry` de `a02` y `ToolPort`/`PolicyGate`/`AuditEvent` de `a03`, que aún no están sincronizados a `specs/`.)*

## No-objetivos

- **Sin UI de Tarjetas HITL** (`d17-hitl-aprobaciones`): las escrituras producen un `escalate_hitl` y su evento queda en espera; aquí no hay tarjeta, cola, expiración ni segunda aprobación operativa. Solo el contrato del evento en espera.
- **Sin consola de permisos ni Registro de tools de administración** (`d20-gobernanza-plataforma`): no hay pantalla de clasificación/permisos por rol/agente ni kill-switch de UI. La clasificación vive en el `ToolManifest`.
- **Sin bridge Protheus / ERP Safe Query API** (Etapa P): el MCP Server de ejemplo es genérico de utilidades y no toca ERP; el binding Protheus se define después sobre esta plataforma.
- **Sin persistencia del `AuditEvent`** (`b04-persistencia-postgres`): aquí solo se emite el contrato del evento; su store append-only llega después.
- **Sin otras features del cliente MCP**: solo Tools. Quedan fuera Resources, Prompts y las client features de la spec (Sampling, Roots, Elicitation) — no se ofrecen a los servers.
- **Sin RAG**: no se toca `RetrievalPort` ni su adapter nulo.
- **El cliente MCP no vive en `core/`**: `core/` sigue sin importar frameworks; MCP vive solo en `adapters/tools_mcp` detrás del `ToolPort`.

## Bounded context afectado

`tools` (blueprint v2.4 capa 5: Tool adapters — MCP, OpenAPI, ERP Safe Query API), materializado en `adapters/tools_mcp`. Consume el `ToolPort` de `core/ports/` (`a03`) sin redefinirlo y el `ToolManifest`/`ToolRegistry` de `core/manifests/` (`a02`). La ejecución gobernada consume el `PolicyGate` y el `AuditEvent` del bounded context `governance` (`a03`). No se añade lógica a `core/`.

## Impact

- Nuevo código de adapter en `resultarai/adapters/tools_mcp/`: cliente MCP (lifecycle, `tools/list`, `tools/call`), transports stdio y Streamable HTTP, mapeo de errores y el binding con el `ToolRegistry`.
- `manifests/tools/`: `ToolManifest` de fábrica que bindean el MCP Server de ejemplo (1 lectura + 1 escritura simulada) con clasificación fija por `version`.
- MCP Server de ejemplo de fábrica (utilidades) como paquete propio ejecutable por stdio, plantilla para la Etapa P.
- `tests/contracts/` y `tests/`: tests del cliente contra un MCP Server de prueba (sin red externa), del binding y de la ejecución gobernada (Policy Gate + `AuditEvent`).
- Dependencias: `a02-core-manifiestos` (`ToolManifest`, `ToolRegistry`), `a03-core-gobernanza` (`ToolPort`, `PolicyGate`, `AuditEvent`, niveles de riesgo), `b06-runtime-grafos` (Policy Gate evaluado por paso) y `c08-agent-skills` (las Tools se invocan vía Skill, regla dura 3). Nueva dependencia externa: SDK oficial de MCP para Python en `adapters/` (versión fijada al implementar).
- Referencia del blueprint: §2.4.6 (Agentic Scaffolding Framework, principio 6 — toda Tool externa pasa por MCP, OpenAPI/ERP Safe Query API o conector aprobado) y §2.4.4 prioridad P0 (Runtime Authorization) para la ejecución gobernada.
