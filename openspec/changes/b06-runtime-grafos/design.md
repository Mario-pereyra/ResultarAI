## Context

`a02-core-manifiestos` entrega los schemas y registries de los 6 manifiestos; `a03-core-gobernanza` entrega el Policy Gate puro, `AuditEvent` y los seis Ports (`LLMPort`, `ToolPort`, `TracePort`, `StatePort`, `PolicyPort`, `RetrievalPort`). Ninguno de los dos ejecuta nada: son contratos. Este change construye el primer runtime real —el graph template de respuesta directa del `default_chat`— que consume esos contratos desde `adapters/runtime_langgraph/`, el único módulo del repo donde vive LangGraph (regla de dependencia de `docs/02-arquitectura.md`, verificada por import-linter desde `a01`). `b04-persistencia-postgres` y `b05-gateway-modelos` pueden no estar archivados todavía cuando este change se implemente: por eso el runtime se apoya en dobles/fixtures de `StatePort` y `LLMPort` para sus propios tests, y consume los adapters reales cuando existan sin cambiar su propio contrato.

## Goals / Non-Goals

**Goals:**

- Ejecutar un turno completo del `default_chat` (recibir → routear → ejecutar grafo → responder) contra el graph template `default_chat_graph`, sin ninguna skill ni tool real.
- El Skill Router decide con el Routing Manifest y dejar razón legible + auditoría de cada decisión.
- El Policy Gate se evalúa en cada paso relevante (responder, activar skill, compaction), nunca solo al inicio de la sesión.
- La compaction al 80% de la ventana, una vez por sesión, en frontera de turno, append-only, con indicador.

**Non-Goals:**

- Ninguna skill real, ninguna tool, ningún graph de plan-then-execute (`c08`, `c09`).
- Ninguna API HTTP (`d13`).
- Ningún adapter Postgres ni LiteLLM reales conectados (`b04`, `b05`); se usan dobles/fixtures.
- Ninguna instrumentación real de Langfuse (`b07`); solo se emiten eventos vía `TracePort`.

## Decisions

1. **`core/routing` es puro; LangGraph vive solo en el adapter.** El `SkillRouter` es una función que recibe `(turn, RoutingManifest activo)` y devuelve una `RoutingDecision` (`action`, `target` opcional, `reason`) sin ningún import de LangGraph ni de ningún adapter. El adapter `runtime_langgraph` traduce esa decisión a una transición de grafo. Alternativa descartada: modelar el ruteo como un nodo LangGraph con lógica de decisión embebida — violaría la regla de dependencia (la lógica de negocio del ruteo quedaría atrapada en un framework y sería imposible de testear sin él).

2. **El grafo pide autorización al Policy Gate como un nodo explícito antes de cada paso relevante**, no como middleware implícito. Cada nodo relevante (responder, activar skill, compaction) construye un `ActionRequest` y llama a `PolicyPort.evaluate(...)` antes de continuar; el resultado decide la arista siguiente (`allow` → continuar, `deny` → nodo de respuesta de restricción, `escalate_hitl` → nodo de suspensión). Alternativa descartada: evaluar la política una sola vez al principio del turno — viola explícitamente la regla dura 4 y el principio "runtime authorization per step" de `docs/06-seguridad-gobernanza.md`.

3. **Compaction "una sola vez" se interpreta como una sola vez *por sesión*, no una vez por turno.** `design/FUNCIONALIDADES.md` §4 no detalla qué pasa si el contexto vuelve a crecer después de una primera compaction; se decide que el runtime marca la sesión como compactada (flag en el estado de sesión vía `StatePort`) y no vuelve a disparar la compaction para ella. Si el contexto sigue creciendo después, la sesión seguirá funcionando sin una segunda compaction dentro de este change — evitar compactar contenido ya compactado en cascada es más seguro que definir una política de compaction repetida sin especificación de producto. Revisar esta decisión si el product owner define un límite más allá del cual una sesión sin segunda compaction se vuelve inviable.

4. **La compaction se modela como un paso más del grafo, sujeto al Policy Gate**, igual que activar una skill o responder. Esto es coherente con "cada transición relevante pide decisión al gate" y deja la puerta abierta a que una policy futura restrinja compaction por tenant o por perfil de modelo sin tocar el runtime.

5. **El resumen de compaction se implementa como un nuevo mensaje/evento de sistema, nunca como una edición.** Reutiliza el mismo principio append-only / branch-never-rewrite que gobernará `messages` en `b04-persistencia-postgres`; este change no depende de que esa tabla exista todavía (usa `StatePort` con un adapter fixture), pero el contrato de comportamiento queda fijado ahora para que `b04` lo implemente sin reabrir el diseño.

6. **`LLMPort` y `TracePort` se consumen contra dobles en los tests de este change.** El runtime no asume ninguna implementación concreta: los contract tests de `adapters/runtime_langgraph` corren contra dobles de `LLMPort`/`PolicyPort`/`TracePort`/`StatePort` (definidos en `tests/contracts/`), de modo que conectar los adapters reales de `b04`/`b05`/`b07` no requiera cambiar el grafo, solo su composición en `app/`.

## Risks / Trade-offs

- [La decisión de "una sola vez por sesión" (decisión 3) puede no coincidir con lo que el product owner quiere cuando lo vea implementado] → Mitigación: queda documentada como decisión explícita y reversible; si cambia, es un ajuste acotado al nodo de compaction, no un rediseño del grafo.
- [Los dobles de `LLMPort`/`StatePort`/`TracePort` pueden ocultar comportamientos reales de los adapters de `b04`/`b05`/`b07` hasta que existan] → Mitigación: los contract tests de este change verifican el *contrato* del Port, no una implementación concreta; cuando los adapters reales lleguen, sus propios contract tests (en `b04`/`b05`/`b07`) deben pasar contra el mismo contrato.
- [Modelar la compaction como paso del grafo sujeto al Policy Gate añade una evaluación de policy en cada frontera de turno, incluso cuando no hay skill involucrada] → Mitigación: es intencional (regla dura 4); el costo es una evaluación de función pura adicional, no una llamada de red.

## Open Questions

- ¿Debe existir una policy explícita en el Policy Manifest de fábrica (`a02`) que cubra `operation_type: compaction`, o el Policy Gate debe tratarla como un tipo de operación `read` de bajo riesgo por defecto? Este change asume lo segundo (riesgo `low`, `allow` por policy de fábrica) hasta que `a02`/`a03` decidan lo contrario; queda para la revisión final del change confirmar que el Policy Manifest de fábrica cubre este caso sin caer en deny-by-default por omisión.
