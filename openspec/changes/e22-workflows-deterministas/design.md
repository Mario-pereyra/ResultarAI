## Context

`design/FUNCIONALIDADES.md` §7 (decisión D6) y `design/VISTAS/04-workflows.md` normalizan los Workflows como un módulo propio, separado del catálogo de agentes: formulario tipado en vez de chat, pasos fijos por versión en vez de razonamiento libre del LLM sobre qué hacer. Para cuando este change se implemente, ya existen (archivados o con interfaz especificada): `a03-core-gobernanza` (Policy Gate, `escalate_hitl`, `AuditEvent`), `b06-runtime-grafos` (Policy Gate evaluado por paso), `c09-mcp-tools` (Tool Registry + MCP Server de ejemplo con una Tool de escritura simulada), `d12-notificaciones` (contrato de emisión + tipos ya registrados para workflows), `d14-attachments` (pipeline de extracción), `d15-catalogo-agentes` (contrato de visibilidad agente×rol, reutilizable), `d16-cuotas-liberaciones` (evaluación de cuota pre-llamada) y `d17-hitl-aprobaciones` (Tarjeta HITL operativa). Este change es, en esencia, un **orquestador de segundo tipo**: mientras el Default Chat decide con un LLM qué hacer a continuación, un Workflow no decide nada en runtime — el orden ya está fijado en código desde que se publicó la versión.

Los mockups y `design/VISTAS/04-workflows.md` usan como ejemplo un workflow de validación Protheus (informe GAP, checklist XLSX, selector cliente/ambiente). Por el pivote (`docs/07-roadmap.md`), ese ejemplo es Etapa P: este change adapta los mismos patrones de UI/estado a un **ejemplo genérico sin ERP** y deja fuera los elementos específicos de Protheus (bridge, cliente/ambiente, comparación de hallazgos).

## Goals / Non-Goals

**Goals:**

- Motor determinista de Workflows (definición + registro por código, sin manifiesto YAML, sin builder visual) con máquina de estados pura para Paso y Corrida.
- Slice vertical completo (backend + UI) de las 5 vistas del módulo, adaptadas a un dominio genérico.
- Reutilización estricta de piezas ya construidas: Tarjeta HITL (`d17`), cuota (`d16`), notificaciones (`d12`), trazas (`b07`), Tool Registry (`c09`) — este change no reimplementa ninguna de ellas.
- Workflow de ejemplo de fábrica que ejercita el ciclo completo, incluida una pausa HITL real (sobre la Tool simulada de `c09`).

**Non-Goals:**

- Builder visual, definición de workflows por YAML o por configuración de instancia.
- Cualquier escritura real a un sistema externo (ERP u otro): la única "escritura" posible en esta etapa es la Tool simulada de `c09`.
- Scheduling/cron, comparación de Corridas ("diff" de hallazgos), selector cliente/ambiente: todo Etapa P.

## Decisions

1. **Paquete `core/orchestration/workflows/` nuevo.** `docs/05-estructura-y-convenciones.md` no lista hoy un subpaquete de `core/` para workflows (el árbol documentado data de antes de que `b06` creara `core/routing/` para el Skill Router y de que `d16`/`d17` crearan `core/governance/`). Igual que esos changes, `e22` extiende el árbol documentado con un subpaquete nuevo bajo el bounded context `orchestration` (`docs/02-arquitectura.md`), separado de `core/routing/` porque resuelve un problema distinto: el Skill Router decide con reglas sobre intención de turno; `core/orchestration/workflows/` no decide nada, solo aplica una secuencia fija. Alternativa descartada: meter los Workflows dentro de `core/routing/` — se rechaza porque mezclaría dos modelos mentales distintos (design §0.1) también a nivel de código.
2. **`WorkflowDefinition` es un objeto Python inmutable (`frozen=True` en Pydantic), no un YAML.** A diferencia de los 6 manifiestos (`docs/04-manifiestos.md`), un Workflow no es contenido editable por un Admin sin tocar código: sus pasos invocan `LLMPort`/`ToolPort` con lógica de ensamblado de prompt/payload que sí es código. El `WorkflowRegistry` (análogo a `AgentRegistry`/`SkillRegistry`) construye su catálogo a partir de las `WorkflowDefinition` importadas explícitamente al arrancar la aplicación (patrón de registro explícito, no descubrimiento por filesystem) — evita "manifiestos fantasma" y mantiene fail-fast si una definición referencia una Tool inexistente.
3. **Corrida y Paso como tablas append-only propias (`workflow_runs`, `workflow_steps`), sobre la infraestructura de `b04-persistencia-postgres`.** Cada transición de estado inserta una fila nueva (o un evento) en vez de hacer `UPDATE` sobre el estado anterior, consistente con el principio append-only/branch-never-rewrite adoptado en el pivote. El estado "actual" de una Corrida es una proyección (última transición), no una columna mutable arbitraria.
4. **El streaming de progreso reutiliza el mismo mecanismo de transporte en vivo que `d13-chat-conversacion` (SSE/WSS), no uno propio.** Alternativa descartada: polling — se rechaza por latencia percibida y porque `design/VISTAS/04-workflows.md` §0.6 exige reconexión transparente con la Corrida viva en servidor, patrón que el chat ya resuelve.
5. **La pausa HITL de un paso de escritura NO crea un tipo de Solicitud de aprobación nuevo.** El paso construye el mismo `ActionRequest` que cualquier Tool de escritura y lo pasa por el mismo Policy Gate; cuando la decisión es `escalate_hitl`, `e22` solo guarda la referencia (id de Solicitud) en el Paso y espera el evento de resolución de `d17-hitl-aprobaciones` — nunca renderiza su propia tarjeta. Esto es lo que garantiza "misma tarjeta, mismas reglas" sin duplicar expiración ni 4-ojos.
6. **Los inputs y archivos esperados del formulario se validan con el schema Pydantic embebido en la `WorkflowDefinition`.** El formulario del frontend es genérico (renderiza campos a partir de un schema serializado), no una plantilla hardcodeada por workflow — así el workflow de ejemplo y futuros workflows (Etapa P) comparten el mismo renderer.
7. **El workflow de ejemplo de fábrica usa la Tool de escritura simulada que ya crea `c09-mcp-tools`.** Se descarta crear una Tool nueva solo para el ejemplo: reutilizar la de `c09` evita duplicar superficie de MCP Server y deja la clasificación lectura/escritura/riesgo donde ya vive (fija por versión, `c09`).

## Modelo conceptual y estados (referencia local — no reemplaza el glosario)

Adaptado de `design/VISTAS/04-workflows.md` §0.2/§0.3, ajustado a la nomenclatura de esta capacidad:

| Concepto (ES) | Nombre en código | Identidad |
|---|---|---|
| Workflow (definición) | `WorkflowDefinition` | `slug` + `version`, p. ej. `informe-adjunto@1.0` |
| Corrida | `WorkflowRun` | `WF-AAAA-NNNN` |
| Paso | `WorkflowStep` | índice `n de N` dentro de la Corrida |

**Estado de Corrida:** `configurando → en ejecución → (esperando aprobación ⇄ en ejecución) → completada | fallida | cancelada`.
**Estado de Paso:** `pendiente → en curso → completado | fallido | esperando aprobación`.

Estos dos términos (**Corrida**, **Paso**) y **Workflow** no están todavía en `docs/03-glosario-dominio.md`; se documentan como pendientes de incorporar (ver nota final del change).

## Risks / Trade-offs

- [Confundir Workflow con Agente en la navegación] → Mitigación: sección de sidebar propia (decisión D6 del design), nunca mezclada con el catálogo; contrato de visibilidad reutilizado de `d15` pero aplicado a una entidad distinta.
- [El renderer genérico de formulario no cubre un tipo de input futuro de Etapa P] → Mitigación: el schema de inputs es extensible por tipo declarado; agregar un tipo nuevo es un PR al renderer + a la `WorkflowDefinition`, sin tocar el motor de estados.
- [Doble fuente de verdad entre el estado de la Corrida y el estado de la Solicitud de aprobación de `d17`] → Mitigación: `e22` no guarda su propia copia del estado de aprobación; solo referencia el id y reacciona al evento de resolución que emite `d17`.
- [Streaming interrumpido pierde eventos intermedios] → Mitigación: la resincronización al reconectar trae el estado completo actual de todos los pasos (no un diff), igual que `d13`.
- [El ejemplo de fábrica se vuelve el único caso probado y no generaliza a Etapa P] → Mitigación: el contrato de Paso (3 tipos) y el schema de inputs/archivos esperados están diseñados para workflows con más pasos y más inputs sin cambiar el motor; el ejemplo es deliberadamente mínimo (3 pasos) para demostrar el ciclo, no el límite del modelo.

## Open Questions

*(ninguna — las decisiones quedan tomadas arriba; el detalle de generación del artefacto xlsx/md server-side y el detalle de columnas de Postgres son implementación, no diseño abierto)*
