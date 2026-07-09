# 04 — Manifiestos: los 6 Contratos Declarativos

> Última actualización: 2026-07-09
> Base: blueprint §2.4.6 (Agentic Scaffolding Framework). Términos: [03-glosario-dominio.md](03-glosario-dominio.md).

Los manifiestos son **el núcleo del dominio** ([ADR-0004](adr/0004-manifiestos-declarativos-como-dominio.md)): agregar o cambiar un agente, skill o tool es editar YAML versionado, no tocar el runtime.

**Pivote 2026-07-09 (ver [07-roadmap.md](07-roadmap.md)):** las skills y las tools se apoyan en **contratos oficiales externos** y los manifiestos aportan la **capa de gobernanza** que esas specs no cubren:

- **Skill Manifest** → **envoltorio de gobernanza** de un paquete conforme a la spec oficial **Agent Skills** (agentskills.io: carpeta con `SKILL.md` + frontmatter `name`/`description`, progressive disclosure, `allowed-tools`). El manifiesto **referencia** el paquete (ruta/id + versión) y añade lo que la spec no define: riesgo, políticas, visibilidad por rol, plan-then-execute y las tools permitidas del Tool Registry. No copia el contenido del `SKILL.md`.
- **Tool Manifest** → **referencia** una tool de un **MCP server** conforme a la spec oficial **MCP** (revisión `2025-11-25`, fijada por el change `c09`). El manifiesto añade la gobernanza: clasificación lectura/escritura, nivel de riesgo, allowlist, binding con el Tool Registry — **fija por versión** (cambiarla exige un PR).

Los otros 4 manifiestos (Agent, Policy, Routing, Eval) no cambian de esencia; los ejemplos se ajustan al conjunto de fábrica genérico (agente default sin nombre comercial + 1 skill, 1 tool MCP, 1 policy, 1 routing y 1 eval de ejemplo). La personalización Protheus/ERP es Etapa P.

## Regla de oro

```
Correcto:   Default Chat → Skill aprobada → Tools permitidas → Policy Gate → Ejecución
Incorrecto: Default Chat → cualquier tool directa → ejecución sin skill ni política
```

El Default Chat declara `can_execute_tools_directly: false` y `tool_access_policy.mode: deny_by_default`. Siempre.

## Ciclo de vida de un manifiesto

```
draft ──▶ validado (CI) ──▶ active ──▶ deprecated
```

- **draft**: existe en Git, no se carga al runtime.
- **validado**: pasa el schema Pydantic + reglas cruzadas (las tools que una skill declara existen y están activas; las skills que un agente habilita existen).
- **active**: cargado por los registries y disponible.
- **deprecated**: visible en el registry pero no invocable; se conserva por trazabilidad.

**Dónde viven:** `manifests/{agents,skills,tools,policies,routing,evals}/*.yaml` en Git. **Cómo se validan:** schemas Pydantic en `core/manifests/`, ejecutados en CI en cada PR y al arrancar la aplicación (fail-fast).

## Los 6 contratos

### 1. Agent Manifest — `manifests/agents/`

Define un agente: propósito, runtime, skills habilitadas, límites, observabilidad y eval placeholder.

Campos obligatorios: `id`, `name`, `type`, `status`, `version`, `runtime.framework`, `runtime.graph`, `capabilities`, `enabled_skills`, `tool_access_policy`, `observability`, `evals`.

```yaml
id: default_chat
name: Chat por Defecto        # sin nombre comercial (pivote): agente de fábrica genérico
type: default_orchestrator
status: active
version: 1.0.0                 # semver; el kill switch es cambiar status, no borrar el manifiesto

runtime:
  framework: langgraph
  graph: default_chat_graph

capabilities:
  can_answer_general_questions: true
  can_use_skills: true
  can_delegate_to_agents: false   # true cuando existan agentes especializados
  can_execute_tools_directly: false

enabled_skills:
  - example_skill               # cada skill referenciada existe como Skill active (validación cruzada, a02)

tool_access_policy:
  mode: deny_by_default
  allow_only_via_skills: true

limits:
  max_steps_per_task: 10
  max_cost_usd_per_task: 0.50

observability:
  provider: langfuse
  trace_all_interactions: true
  log_skill_selection: true
  log_tool_calls: true
  log_model_calls: true
  log_costs: true

evals:
  status: placeholder
  template: agent_eval_template
```

### 2. Skill Manifest — `manifests/skills/`

**Envoltorio de gobernanza** de un paquete conforme a la spec oficial **Agent Skills** (agentskills.io). El paquete real —carpeta con `SKILL.md` + frontmatter `name`/`description`, progressive disclosure, `allowed-tools`— **no vive en el YAML**: el manifiesto solo lo **referencia** (id/ruta + versión) y añade la capa que la spec no cubre. El descubrimiento y parseo real del paquete es del change `c08`; aquí solo se referencia por identificador.

**Qué aporta el manifiesto (gobernanza), no la spec:**

- **plan-then-execute** (`execution.graph`) — obligatorio para skills que tocan el ERP (regla dura 7).
- **tools permitidas del Tool Registry** (`tools`) — allowlist explícita; subconjunto gobernado de los `allowed-tools` del `SKILL.md`.
- **visibilidad por rol** (`visibility.roles`).
- **riesgo** (`risk.level`) y **política de salida** (`output_policy`).
- Las **policies** se enlazan desde el Policy Manifest vía `applies_to.skills` (no se duplican aquí).

Campos obligatorios: `id`, `name`, `status`, `version`, `description`, `skill_package`, `execution`, `tools`, `output_policy`, `evals`. Opcionales de gobernanza: `visibility`, `risk`, `retrieval` (ver "Puerta abierta: retrieval").

**MUST NOT:** duplicar instrucciones o ejemplos del `SKILL.md` (el strict mode del schema, a02, rechaza campos no declarados en el envoltorio).

```yaml
id: example_skill
name: Utilidades de Ejemplo
status: active
version: 1.0.0

description: >
  Skill de ejemplo de fábrica: envuelve un paquete Agent Skill (SKILL.md) con
  utilidades genéricas y expone, con gobernanza, sus tools permitidas del Tool Registry.

skill_package:
  spec: agent_skills                    # spec oficial (agentskills.io)
  ref: example_utils                    # identificador del paquete SKILL.md (se referencia, no se copia)
  path: skills/example_utils/SKILL.md   # progressive disclosure: el cuerpo vive en el paquete
  version: 1.0.0                        # versión del paquete Agent Skill referenciado

execution:
  mode: read_only
  graph: default_skill_graph            # plan_then_execute_graph es OBLIGATORIO para skills que tocan el ERP (ver 06)
  requires_human_approval: false

visibility:
  roles: [admin, tecnico, funcional]    # capa de gobernanza que la spec Agent Skills no cubre

risk:
  level: low

tools:                                  # allowlist del Tool Registry (subconjunto gobernado de allowed-tools del SKILL.md)
  - example_echo

output_policy:
  summarize_results: true
  mask_sensitive_fields: true
  max_rows: 20

evals:
  status: placeholder
  template: skill_eval_template
```

> **Skills que tocan el ERP (Etapa P):** además de lo anterior, `execution.mode: read_only` **exige** `execution.graph: plan_then_execute_graph` (plan validado antes de ejecutar, regla dura 7); el schema de `a02` lo verifica por invariante.

### 3. Tool Manifest — `manifests/tools/`

**Referencia** una tool de un **MCP server** (spec oficial **MCP**, revisión `2025-11-25` fijada por `c09`) y añade la gobernanza: clasificación lectura/escritura (`risk.operation_type`), nivel de riesgo (`risk.level`), permisos, seguridad, auditoría y el binding con el Tool Registry. **La clasificación y el riesgo son fijos por `version`:** cambiarlos exige una nueva versión (un PR), nunca una mutación en runtime. La conexión real al MCP server es del change `c09`; aquí solo se referencia por identificador.

Campos obligatorios: `id`, `name`, `status`, `version`, `type`, `adapter`, definición del binding (`mcp` u `openapi`), `risk`, `permissions`, `security`, `audit`, `evals`.

> El binding **`mcp`** es el de fábrica (server de ejemplo, utilidades). El binding **`openapi`** se reserva para la **ERP Safe Query API** (Etapa P), que expone plantillas con allowlist, nunca SQL libre (regla dura 5).

```yaml
id: example_echo
name: Echo de Ejemplo
status: active
version: 1.0.0

type: mcp_tool
adapter: mcp

mcp:
  server: example_utils_server      # identificador del MCP server (registrado por c09), no una URL cruda
  tool_name: echo                   # nombre de la tool dentro del server (spec oficial MCP)
  spec_revision: "2025-11-25"       # revisión de la spec MCP fijada por c09; cambiarla = PR
  endpoint_ref: example_mcp_endpoint  # resuelto en runtime, nunca hardcodeado

risk:
  level: low
  operation_type: read              # clasificación fija por version (cambiarla = nueva version = PR)

permissions:
  mode: read_only
  requires_human_approval: false

security:
  allow_sql_freeform: false         # regla dura 5: jamás SQL libre; el schema (a02) lo rechaza si es true
  allow_dynamic_table_access: false
  mask_sensitive_fields: true

audit:
  log_request: true
  log_response_summary: true
  log_user: true
  log_tenant: true

evals:
  status: placeholder
  template: tool_eval_template
```

### 4. Policy Manifest — `manifests/policies/`

Reglas de ejecución que el Policy Gate evalúa. Deny-by-default: lo no permitido explícitamente está bloqueado.

```yaml
id: example_read_only_policy
status: active
version: 1.0.0

applies_to:
  skills: [example_skill]

rules:
  - effect: allow
    when:
      operation_type: read
  - effect: escalate_hitl
    when:
      risk_level: high
  # todo lo demás: deny (implícito) — deny-by-default
```

> En la Etapa P, las policies del ERP añaden condiciones de multi-tenant (p. ej. `tenant_in: [...]`) para acotar por cliente autorizado; la semántica deny-by-default no cambia.

### 5. Routing Manifest — `manifests/routing/`

Reglas del Skill Router: cuándo responder directo, activar skill o delegar.

```yaml
id: default_chat_routing
status: active
version: 1.0.0

rules:
  - intent: example_task       # consultas que resuelve la skill de ejemplo
    action: activate_skill
    target: example_skill
  - intent: general_question
    action: answer_directly
  - intent: unknown
    action: answer_directly
    note: nunca inventar acceso a datos; declarar que no se tiene la capacidad
```

### 6. Eval Template Manifest — `manifests/evals/`

Placeholder obligatorio por diseño (blueprint, principio 16): reserva el espacio de evaluación sin exigir datasets reales todavía.

```yaml
id: skill_eval_template
status: placeholder
version: 1.0.0

target_kind: skill
metrics_planned:
  - task_completion_rate
  - tool_call_accuracy
  - groundedness_score
dataset: null          # se define cuando existan casos reales
```

## Puerta abierta: retrieval (RAG)

RAG queda como **puerta abierta** ([07-roadmap.md](07-roadmap.md), pivote punto 5): `RetrievalPort` + campos de manifiesto + adapter nulo, **sin implementar**. Los manifiestos que pueden consumir recuperación de conocimiento (p. ej. Skill Manifest) exponen un campo **opcional** `retrieval`:

- **Ausente** → ningún comportamiento de recuperación se activa (es lo normal en el conjunto de fábrica).
- **Presente** → es solo **metadato declarativo**: reserva el contrato para cuando exista `RetrievalPort` (diferido a `a03`; la implementación real de RAG es Etapa P). No invoca ningún adapter.

```yaml
# bloque opcional dentro de un Skill Manifest — declarativo, no ejecuta nada
retrieval:
  enabled: false                # cuando llegue RAG (Etapa P): true + fuente indexada
  source: null                  # id de la colección/índice; null mientras no exista RetrievalPort
```

El strict mode del schema (`a02`) valida el sub-schema de `retrieval` y rechaza claves desconocidas, pero ningún manifiesto de fábrica exige un `RetrievalPort`.

## Reglas obligatorias (resumen del blueprint §2.4.6, adoptadas)

1. Todo agente, skill y tool tiene manifiesto versionado; sin manifiesto no existe.
2. Todo manifiesto se valida contra schema antes de cargarse (CI + arranque).
3. Tools con deny-by-default y mínimo privilegio.
4. Cada skill declara explícitamente sus tools; cada agente sus skills.
5. El eval placeholder existe desde el día uno aunque esté vacío.
6. Toda ejecución se traza (Langfuse/OpenTelemetry); toda llamada a modelo pasa por LiteLLM; toda tool externa pasa por MCP (spec oficial, revisión fija por versión), OpenAPI/ERP Safe Query API o conector aprobado.
7. Las skills envuelven paquetes de la spec oficial **Agent Skills** (`SKILL.md`) y las tools referencian **MCP servers** de la spec oficial **MCP**; el manifiesto aporta la gobernanza (riesgo, políticas, visibilidad, allowlist, plan-then-execute), no duplica el contrato oficial.
