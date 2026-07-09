## ADDED Requirements

### Requirement: Graph template de respuesta directa

El adapter `runtime_langgraph` SHALL exponer el graph template `default_chat_graph`, invocable por el nombre declarado en el campo `runtime.graph` del Agent Manifest de `default_chat` (`docs/04-manifiestos.md`), que ejecuta un turno completo sin invocar ninguna Tool. `core/routing` SHALL permanecer ajeno a LangGraph: solo conoce el nombre del graph template, nunca su implementación.

#### Scenario: Turno sin skill activada responde directo

- **WHEN** el Skill Router decide `answer_directly` para un turno del agente `default_chat`
- **THEN** el `default_chat_graph` invoca `LLMPort` para generar la respuesta y no invoca ningún `ToolPort`

#### Scenario: Grafo referenciado por nombre desde el manifiesto

- **WHEN** el Agent Registry carga el Agent Manifest de `default_chat` con `runtime.graph: default_chat_graph`
- **THEN** el adapter `runtime_langgraph` resuelve ese nombre a una instancia ejecutable del grafo, y `core/` no importa `langgraph` en ningún punto de la resolución

### Requirement: Ciclo de vida del turno trazable

El runtime SHALL ejecutar cada turno en las fases **recibir → routear → ejecutar grafo → responder**, emitiendo un evento trazable vía `TracePort` en cada transición de fase, identificado por un `turn_id` común.

#### Scenario: Turno completo emite trazas de las 4 fases

- **WHEN** un usuario envía un mensaje y el turno se completa exitosamente
- **THEN** `TracePort` recibe un evento por cada fase (recibir, routear, ejecutar grafo, responder) en ese orden, todos con el mismo `turn_id`

#### Scenario: Turno interrumpido no reporta fases posteriores a la interrupción

- **WHEN** el turno se detiene antes de completar el ciclo (por ejemplo, el Policy Gate escala a HITL en la fase "ejecutar grafo")
- **THEN** `TracePort` recibe eventos únicamente hasta la fase en que se detuvo, y ninguna fase posterior se reporta como completada

### Requirement: Policy Gate evaluado en cada paso relevante del grafo

Cada transición relevante del grafo (responder directo, activar skill, disparar compaction) SHALL construir un `ActionRequest` y consultarlo contra `PolicyPort` (contrato de `a03-core-gobernanza`) antes de ejecutar el paso. La `PolicyDecision` resultante (`allow | deny | escalate_hitl`) condiciona la transición siguiente y SIEMPRE se registra como `AuditEvent`, incluidas las decisiones `allow`.

#### Scenario: Policy Gate permite responder directo

- **WHEN** el turno se rutea a `answer_directly` y `PolicyPort` evalúa el `ActionRequest` correspondiente
- **THEN** la `PolicyDecision` es `allow`, el grafo continúa al nodo de respuesta y se emite un `AuditEvent` con efecto `allow`

#### Scenario: Policy Gate deniega el paso y el turno termina sin ejecutarlo

- **WHEN** `PolicyPort` devuelve `deny` para el `ActionRequest` de un paso del grafo
- **THEN** el grafo no ejecuta ese paso, responde al usuario declarando la restricción sin exponer detalles internos de la política, y se emite un `AuditEvent` con efecto `deny`

#### Scenario: Policy Gate escala a HITL y el turno queda en espera

- **WHEN** `PolicyPort` devuelve `escalate_hitl` para un paso del grafo
- **THEN** el grafo suspende la ejecución de ese paso, deja el turno en espera de aprobación humana (contrato de dominio; la tarjeta HITL operativa llega en `d17-hitl-aprobaciones`) y se emite un `AuditEvent` con efecto `escalate_hitl`

### Requirement: Default Chat nunca ejecuta tools directamente

El `default_chat_graph` SHALL no declarar ningún nodo que invoque `ToolPort`. La única vía hacia una Tool es la activación de una Skill (fuera de alcance de este change; llega en `c08-agent-skills`), conforme a la regla dura 3 y a la Regla de Oro de `docs/04-manifiestos.md`.

#### Scenario: Grafo de respuesta directa no tiene nodos de tool

- **WHEN** se inspecciona la definición de nodos del `default_chat_graph`
- **THEN** ningún nodo invoca `ToolPort`, y el contract test del adapter falla si se agrega un nodo que lo haga fuera de un punto de extensión de activación de skill
