## Why

`a02-core-manifiestos` y `a03-core-gobernanza` dejan los contratos (manifiestos, Policy Gate, Ports) pero nada los ejecuta todavía: sin un runtime real, el Default Chat no puede recibir un turno, decidir si responde directo o activa una skill, ni dejar traza de esa decisión. Este change construye el primer runtime ejecutable —el graph template de respuesta directa— con el Skill Router y el Policy Gate evaluados en cada paso, y la regla de compaction al 80% que evita que una sesión larga rompa la ventana de contexto. Es el habilitador directo de `c08-agent-skills` (que añadirá el graph de tool call) y de `b07-observabilidad` (que instrumentará las trazas que este change ya emite vía `TracePort`).

## What Changes

- Se crea el bounded context `orchestration` en `resultarai/core/` (routing puro: decisión del Skill Router, sin I/O) y el adapter `resultarai/adapters/runtime_langgraph/` (único lugar del repo donde vive LangGraph, conforme a la regla de dependencia).
- Se define el **graph template de respuesta directa** (`default_chat_graph`, referenciado por nombre desde el Agent Manifest de `default_chat`, campo `runtime.graph` de `docs/04-manifiestos.md`): el turno entra, se rutea, se responde y se traza — sin activar ninguna skill ni tool real todavía.
- Se implementa el **Skill Router** (`core/routing`, bounded context `orchestration`): decide, usando el Routing Manifest de `a02`, si el turno se responde directo o activa una skill; toda decisión de ruteo se registra como `AuditEvent` (contrato de `a03`) vía `PolicyPort`/`TracePort`.
- El **Policy Gate se evalúa en cada paso relevante del grafo** (regla dura 4): antes de responder, antes de activar una skill y en la frontera de compaction, el grafo construye un `ActionRequest` y consulta `PolicyPort`; la `PolicyDecision` (`allow | deny | escalate_hitl`) condiciona la transición siguiente.
- Se implementa la **compaction al 80% de la ventana de contexto**: se evalúa en frontera de turno (nunca a mitad de turno), ocurre **una sola vez** por umbral cruzado, resume el contenido compactado sin reescribir mensajes previos (append-only, coherente con branch-never-rewrite de `b04`) y emite un indicador consumible por la UI (`d13-chat-conversacion`); el usuario puede repedir contenido compactado como mensaje nuevo.
- Se define el **ciclo de vida del turno** recibir → routear → ejecutar grafo → responder, con eventos trazables vía `TracePort` en cada transición (consumidos realmente por `b07-observabilidad`; aquí solo se emiten).

## Capabilities

### New Capabilities

- `agent-runtime`: ejecución del graph template de respuesta directa, ciclo de vida del turno (recibir → routear → ejecutar grafo → responder) y evaluación del Policy Gate en cada paso relevante del grafo.
- `skill-router`: decisión de routing por Routing Manifest (responder directo vs. activar skill), razones legibles de la decisión y su auditoría.
- `context-compaction`: regla de compaction al 80% de la ventana de contexto, aplicada una sola vez por umbral cruzado, en frontera de turno, con indicador emitido y contenido re-pedible como mensaje nuevo.

### Modified Capabilities

*(ninguna — `openspec/specs/` está vacío; no existen specs previas)*

## No-objetivos

- **Sin skills reales**: no se activa ninguna skill de negocio ni se ejecuta su lógica; el Skill Router decide y el grafo deja el punto de extensión listo, pero la activación real de skills (Agent Skills spec, SKILL.md) llega en `c08-agent-skills`.
- **Sin tools**: ninguna tool se invoca desde este change; el Default Chat sigue sin ejecutar tools directamente (regla dura 3) y el graph template de tool call / plan-then-execute llega también en `c08`/`c09`.
- **Sin API HTTP**: no se expone ningún endpoint FastAPI para invocar el runtime; `app/api` y el transporte HTTP/WS los define `d13-chat-conversacion`. Este change se verifica invocando el grafo directamente desde tests.
- **Sin persistencia real de sesiones**: el runtime asume un `StatePort` ya definido (`a03`) pero no implementa su adapter Postgres (`b04-persistencia-postgres`, que puede llegar en paralelo o después); aquí se usa un adapter de estado en memoria/fixture solo para tests.
- **Sin adapter LLM real conectado**: la llamada a modelo pasa por `LLMPort` (contrato de `a03`); el binding a LiteLLM real, perfiles de modelo, cascada de fallback y marcador de escalación son de `b05-gateway-modelos`. Aquí se usa un `LLMPort` doble/fixture para no depender de red.
- **Sin observabilidad real**: se emiten eventos vía `TracePort`, pero el adapter Langfuse que los consume y los hace reconstruibles es `b07-observabilidad`.

## Bounded context afectado

`orchestration` (nuevo, en `resultarai/core/routing/` — Default Chat, Skill Router, graph templates, según `docs/02-arquitectura.md`) y `resultarai/adapters/runtime_langgraph/` (único punto del repo con `import langgraph`, conforme a la regla de dependencia de `docs/02-arquitectura.md` e import-linter de `a01`). El adapter consume los Ports de `governance` (`PolicyPort`), `gateway` (`LLMPort`, vía doble en este change) y `observability` (`TracePort`, vía doble en este change) definidos en `a03`, sin importarlos como frameworks.

## Impact

- Nuevo código en `resultarai/core/routing/`: `SkillRouter` puro, sin I/O, sin frameworks.
- Nuevo código en `resultarai/adapters/runtime_langgraph/`: `default_chat_graph`, nodos del ciclo del turno, integración con `PolicyPort`/`LLMPort`/`TracePort`/`StatePort`.
- `manifests/routing/`: el Routing Manifest de fábrica de `a02` pasa a ser consumido en runtime (antes solo validado).
- `tests/core/`: tests puros del Skill Router (sin red).
- `tests/contracts/`: contract test del adapter `runtime_langgraph` contra `LLMPort`/`PolicyPort`/`TracePort`/`StatePort` con dobles.
- Referencia del blueprint: §2.4.4 Priorización P0 "Agentic Scaffolding Framework" (Runtime Authorization ya cubierto por `a03`; este change entrega la ejecución del grafo que lo invoca en cada paso).
