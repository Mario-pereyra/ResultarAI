## Why

`design/FUNCIONALIDADES.md` §7 (decisión D6) y `design/VISTAS/04-workflows.md` fijan a los Workflows como un **tipo de ítem propio del producto, en sección separada del catálogo de agentes**: procesos deterministas que se configuran con formulario y se ejecutan sin chat. El roadmap (`docs/07-roadmap.md`, fila `e22`, "hecho cuando") exige que el workflow de ejemplo de fábrica corra de punta a punta con una pausa HITL. Hoy existen todas las piezas de las que depende —Policy Gate y `escalate_hitl` (`a03`), runtime con Policy Gate por paso (`b06`), cliente MCP con Tool de escritura simulada de ejemplo (`c09`), Tarjeta HITL (`d17`), notificaciones (`d12`) y cuotas (`d16`)— pero nada las orquesta como un proceso de pasos fijos con formulario tipado. Sin este change, `ADR-0010 §workflows`/decisión D6 del design no tiene motor ni superficie de producto.

## What Changes

- Se define el **modelo de dominio de un Workflow** en `core/orchestration/`: `WorkflowDefinition` versionada e inmutable una vez publicada (pasos fijos, orden fijo, inputs tipados, archivos esperados con tipo/posición/presupuesto fijados por la propia definición), sin manifiesto YAML ni builder visual — se define por código y se publica vía **registro** (`WorkflowRegistry`), igual de código que los manifiestos son de datos.
- Se define el **contrato de Paso**: exactamente tres tipos permitidos —llamada LLM, Tool (vía Skill/registro de `c09`), pausa HITL— con máquina de estados pura (`pendiente → en curso → completado | fallido | esperando aprobación`) y de Corrida (`configurando → en ejecución → (esperando aprobación ⇄ en ejecución) → completada | fallida | cancelada`).
- Se implementa el **listado de workflows** (vista 15): workflows publicados filtrados por la matriz workflow×rol (misma lógica de visibilidad que `d15-catalogo-agentes`, default Técnico+Admin), con qué produce, duración/costo estimado (Técnico/Admin), requisitos e historial reciente propio; capa técnica (modelo/Tools por paso) visible solo Técnico/Admin.
- Se implementa el **formulario tipado de ejecución** (vista 16): inputs declarados por la versión activa de la definición, validados antes de ejecutar (CTA deshabilitado con motivo visible), incluidos los archivos esperados (tipo, tamaño y posición de extracción fijados por el workflow — reutiliza el pipeline de extracción de `d14-attachments`); crea una Corrida con parámetros congelados.
- Se implementa la **ejecución en vivo** (vista 17): pasos con estado en vivo y streaming de progreso por WebSocket/SSE; un paso de escritura pausa la Corrida y muestra la **misma Tarjeta HITL de `d17`** (mismas reglas: expiración = rechazo auditado, segunda aprobación en irreversibles); la Corrida sigue en el servidor si la vista se cierra.
- Se implementa el **resultado descargable** (vista 18): artefacto final (xlsx/md) generado server-side y asociado a la Corrida, con trazabilidad (quién, cuándo, inputs, costo si Técnico/Admin).
- Se implementa el **historial** (vista 19): Corridas propias consultables (inputs, estado, resultado, costo); Admin ve todas; **re-ejecutar** precarga el formulario con los mismos inputs y crea una Corrida nueva (nunca sobrescribe la anterior); **cancelación** auditada — los pasos ya completados quedan registrados, nada se revierte solo.
- Se integra **cuota** (`d16-cuotas-liberaciones`): cada paso de tipo llamada LLM evalúa la cuota antes de emitirse, con el mismo estado `QUOTA` accionable que el chat.
- Se integra **trazas por Corrida** (`b07-observabilidad`): cada Corrida y cada Paso emiten eventos vía `TracePort`, reconstruibles como una traza completa por ejecución.
- Se integra **notificaciones** (`d12-notificaciones`): al terminar una Corrida se emite el tipo ya registrado (`workflow_finalizado`/`workflow_fallido`/`workflow_cancelado`) hacia el dueño de la Corrida.
- Se publica el **workflow de ejemplo de fábrica** genérico (sin ERP): "Generar informe a partir de un adjunto" — paso 1 lectura del adjunto (extracción vía `d14`), paso 2 llamada LLM (resumen/informe), paso 3 Tool de "escritura" simulada del MCP Server de ejemplo (`c09`) que dispara la pausa HITL; demuestra el ciclo completo formulario → pasos en vivo → pausa HITL → resultado → historial.

## Capabilities

### New Capabilities

- `workflows`: modelo de dominio determinista (definición versionada + registro por código, contrato de Paso, máquina de estados de Paso/Corrida), listado y ficha por matriz workflow×rol, formulario tipado con archivos esperados, ejecución en vivo con streaming y pausa HITL (misma tarjeta de `d17`), resultado descargable, historial con re-ejecución y cancelación auditada, evaluación de cuota por paso LLM, trazas por Corrida, notificaciones de finalización y el workflow de ejemplo de fábrica.

### Modified Capabilities

*(ninguna — `hitl-approvals` (`d17`), `notifications` (`d12`), `quotas` (`d16`), `observability-tracing` (`b07`), `mcp-tools`/`tool-registry-binding` (`c09`) y `agent-visibility` (`d15`) solo se consumen: este change no cambia sus requirements)*

## No-objetivos

- **Sin builder visual de workflows**: exclusión explícita del design (§7, "no hay builder visual — definición por código y registro"). Crear o editar una `WorkflowDefinition` es cambiar código y pasar por PR, nunca una consola.
- **Sin workflows con escrituras ERP reales**: la única Tool de escritura que un workflow puede invocar en esta etapa es la Tool de escritura simulada del MCP Server de ejemplo (`c09`); el bridge Protheus y los workflows de validación reales (informe GAP, checklist XLSX) son Etapa P.
- **Sin scheduling ni cron**: toda Corrida nace de una acción explícita del usuario vía formulario; no hay ejecución programada ni disparadores externos.
- **Sin comparación de Corridas ("diff" de hallazgos)**: es específica de los workflows de validación de la Etapa P; el historial de este change lista y filtra Corridas, no las compara.
- **Sin selector cliente/ambiente ni bridge**: pertenece a la Etapa P; los inputs de este change son genéricos (texto, número, selección, archivo), sin contexto Protheus.
- **Sin persistencia propia nueva más allá del esquema de Corridas/Pasos**: usa la infraestructura de `b04-persistencia-postgres` (append-only) sin rediseñarla.

## Bounded context afectado

`orchestration` (`docs/02-arquitectura.md`: Default Chat, Skill Router, graph templates — este change añade el motor de Workflows deterministas como segundo mecanismo de orquestación, sin LLM decidiendo el orden), en tres capas: **core** (`resultarai/core/orchestration/workflows/`: `WorkflowDefinition`, `WorkflowStep`, `WorkflowRegistry`, máquina de estados pura de Paso/Corrida, sin frameworks); **app** (`resultarai/app/`: casos de uso de formulario/ejecución/cancelación/historial, endpoints, integración con `PolicyPort`/`LLMPort`/`ToolPort`/`TracePort` vía adapters ya existentes); **frontend** (vistas 15–19 de `design/VISTAS/04-workflows.md`).

## Impact

- `resultarai/core/orchestration/workflows/`: `WorkflowDefinition`/`WorkflowStep`/`WorkflowRegistry`, máquina de estados de Paso y Corrida (funciones puras, tests en `tests/core/`), y la `WorkflowDefinition` de fábrica del ejemplo (código, no YAML).
- `resultarai/app/use_cases/workflows/` y `resultarai/app/api/`: validación de formulario, creación/streaming/cancelación/re-ejecución de Corridas, integración con Policy Gate por paso, cuota por paso LLM, emisión de trazas y notificaciones.
- `resultarai/adapters/persistence_postgres/`: tablas de Corrida y Paso (append-only, migración Alembic sobre `b04`).
- `frontend/`: vistas 15 (lista), 16 (formulario), 17 (ejecución en vivo), 18 (resultado), 19 (historial) de `design/VISTAS/04-workflows.md`.
- Depende de: `a03-core-gobernanza` (`PolicyPort`, `escalate_hitl`), `b04-persistencia-postgres` (append-only), `b05-gateway-modelos` (tarifas para costo estimado/real), `b06-runtime-grafos` (Policy Gate por paso), `b07-observabilidad` (`TracePort`), `c09-mcp-tools` (Tool de escritura simulada del MCP Server de ejemplo), `d12-notificaciones` (tipos `workflow_finalizado`/`workflow_fallido`/`workflow_cancelado`), `d14-attachments` (extracción de archivos esperados), `d15-catalogo-agentes` (contrato de visibilidad por rol, reutilizado), `d16-cuotas-liberaciones` (evaluación pre-llamada), `d17-hitl-aprobaciones` (Tarjeta HITL reutilizada tal cual).
- Referencia de diseño: `design/FUNCIONALIDADES.md` §7 (Workflows, decisión D6) y `design/VISTAS/04-workflows.md` (vistas 15–19, modelo conceptual §0.2, máquina de estados §0.3), fuentes normativas de este change.
