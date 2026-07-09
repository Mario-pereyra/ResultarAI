# Design — c09-mcp-tools

## Context

`a02-core-manifiestos` entregó el `ToolManifest` (referencia a un MCP Server + `tool_name` + clasificación) y el `ToolRegistry`; `a03-core-gobernanza` entregó el `ToolPort` (`typing.Protocol`), el Policy Gate y el `AuditEvent`; `c08-agent-skills` activa Skills que son la única vía a las Tools (regla dura 3). Este change materializa el eslabón de ejecución: un cliente MCP real detrás del `ToolPort`, conforme a la spec oficial MCP, gobernado y auditado.

**Revisión de la spec fijada:** MCP **2025-11-25** (la más reciente; el schema normativo es `schema/2025-11-25/schema.ts`). Coincide con la revisión anticipada en `docs/07-roadmap.md`; queda confirmada como la vigente. Puntos de la spec que este change usa literalmente: lifecycle `initialize` + `notifications/initialized` con negociación de capacidades; `tools/list` con paginación (`cursor`/`nextCursor`); `tools/call` con `inputSchema`/`outputSchema` (JSON Schema 2020-12 por defecto), `content`/`structuredContent`/`isError`; transports **stdio** y **Streamable HTTP** (endpoint único, headers `MCP-Protocol-Version` y `MCP-Session-Id`); doble mecanismo de error (Protocol Errors JSON-RPC vs Tool Execution Errors `isError: true`); y §Tool Safety (annotations no confiables salvo server de confianza; HITL como principio de la propia spec).

## Goals / Non-Goals

**Goals:**

- Cliente MCP conforme a la spec 2025-11-25 detrás del `ToolPort`, con los dos transports estándar.
- Binding con el `ToolRegistry` donde la clasificación lectura/escritura + riesgo es autoritativa e inmutable en runtime.
- Ejecución gobernada: Policy Gate antes de cada `tools/call` (lectura→`allow`, escritura→`escalate_hitl` SIEMPRE) y `AuditEvent` por decisión.
- Contrato de Tool call visible por rol (proyección del `AuditEvent`).
- MCP Server de ejemplo de fábrica como plantilla para la Etapa P.

**Non-Goals:**

- UI de Tarjetas HITL (`d17`), consola/Registro de tools de administración (`d20`), bridge Protheus/ERP (Etapa P), persistencia del `AuditEvent` (`b04`).
- Resources, Prompts y client features MCP (Sampling, Roots, Elicitation): solo Tools.
- RAG / `RetrievalPort`.

## Decisions

1. **El cliente MCP vive solo en `adapters/tools_mcp`, detrás del `ToolPort`.** `core/` no importa MCP ni el SDK (verificado por import-linter). Alternativa descartada: exponer tipos MCP en `core/` — rompería la regla de dependencia dura 1.

2. **SDK oficial de MCP para Python** (paquete `mcp`) como dependencia de `adapters/`, en vez de reimplementar JSON-RPC/transports a mano. Alternativa descartada: cliente artesanal — reintroduce superficie de bugs de protocolo que la spec ya resuelve. La versión exacta se fija (pin) al implementar (`apply`), coherente con la nota del roadmap "verificar la última al implementar"; si el SDK no cubriera algún detalle de 2025-11-25, se marca en la tarea de compliance.

3. **La clasificación autoritativa es la del `ToolManifest`, no la del server.** La spec (§Tool Safety) declara las `annotations` del server como no confiables salvo server de confianza; por regla dura del proyecto, `operation_type` y `risk.level` los fija el manifiesto por `version` (cambio = PR). El cliente nunca deriva la clasificación de las `annotations`. Esto es defensa en profundidad: un server comprometido no puede rebajarse a "solo lectura".

4. **Escrituras → `escalate_hitl` SIEMPRE, independiente de la Policy.** Aunque una Policy concediera `allow`, `operation_type: write` fuerza `escalate_hitl` y el cliente no emite `tools/call`. Coherente con `docs/06` (critical = escritura → HITL obligatorio) y con "escrituras JAMÁS sin aprobación" (`d17`). Aquí el evento queda en espera; la Tarjeta operativa es `d17`. Alternativa descartada: dejar que la Policy autorice escrituras — contradice la regla del proyecto.

5. **Solo lo declarado existe (deny-by-default a nivel de registro).** Una Tool que el server publique pero sin `ToolManifest` activo no es invocable y ni siquiera llega al Policy Gate. La validación cruzada `tool_name ∈ tools/list` se corre al pasar el manifiesto a `active` (ciclo `draft → validated → active`), coherente con `a02`.

6. **La Tool call visible es una proyección del `AuditEvent`, no una fuente de verdad paralela.** El `AuditEvent` (append-only, `a03`) es la verdad; el registro visible se deriva de él y de la invocación, y la capa por rol es solo presentación (Funcional: lenguaje simple; Técnico/Admin: parámetros completos), conforme a `design/FUNCIONALIDADES.md` §4 y §12. Evita divergencia entre lo mostrado y lo auditado.

7. **El server de ejemplo corre por stdio** (subproceso local), el transport que la spec recomienda soportar siempre; la Tool de escritura es simulada (sin efecto real) para ejercer el camino `escalate_hitl` sin riesgo. Streamable HTTP queda cubierto por el cliente y probado con un server de prueba, pensando en los servers remotos de la Etapa P.

## Risks / Trade-offs

- [El SDK oficial podría ir por detrás de la revisión 2025-11-25 en algún detalle] → Mitigación: la tarea de compliance (opus) verifica punto por punto contra la spec fijada y documenta cualquier desvío; el pin de versión se decide con esa verificación.
- [Streamable HTTP añade complejidad (sesiones, SSE, reconexión) que el server de ejemplo no ejercita] → Mitigación: el cliente se prueba contra un server de prueba HTTP mínimo; los servers remotos reales llegan en la Etapa P y validarán el camino completo.
- [Doble fuente de clasificación (manifiesto vs annotations del server) puede confundir a implementadores] → Mitigación: la spec de `tool-registry-binding` fija explícitamente que las annotations se ignoran; hay un escenario dedicado.
- [Acoplamiento con contratos aún no sincronizados a `specs/` (`ToolPort`, `PolicyGate`, `AuditEvent` de `a03`; `ToolRegistry` de `a02`)] → Mitigación: este change los consume por interfaz ya especificada en los proposals/specs de `a02`/`a03`; no los redefine.

## Migration Plan

Change aditivo: no hay datos ni API previa que migrar. El cliente MCP y el server de ejemplo se añaden como código nuevo en `adapters/` y los `ToolManifest` de fábrica en `manifests/tools/`. Rollback = revertir el PR y quitar los manifiestos del server de ejemplo (kill switch por `status`, sin apagar la plataforma). No requiere despliegue especial (Docker/Compose llega en `e24`).

## Open Questions

*(ninguna bloqueante — la revisión MCP queda fijada en 2025-11-25 y el pin del SDK se resuelve en la tarea de compliance del `apply`.)*
