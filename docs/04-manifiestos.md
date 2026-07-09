# 04 — Manifiestos: los 6 Contratos Declarativos

> Última actualización: 2026-07-09
> Base: blueprint §2.4.6 (Agentic Scaffolding Framework). Términos: [03-glosario-dominio.md](03-glosario-dominio.md).

Los manifiestos son **el núcleo del dominio** ([ADR-0004](adr/0004-manifiestos-declarativos-como-dominio.md)): agregar o cambiar un agente, skill o tool es editar YAML versionado, no tocar el runtime.

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

Campos obligatorios: `id`, `name`, `type`, `status`, `runtime.framework`, `runtime.graph`, `capabilities`, `enabled_skills`, `tool_access_policy`, `observability`, `evals`.

```yaml
id: default_chat
name: Chat Principal
type: default_orchestrator
status: active

runtime:
  framework: langgraph
  graph: default_chat_graph

capabilities:
  can_answer_general_questions: true
  can_use_skills: true
  can_delegate_to_agents: false   # true cuando existan agentes especializados
  can_execute_tools_directly: false

enabled_skills:
  - erp_query_skill

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

Define una capacidad: intención, tools requeridas, modo de ejecución, política de salida.

Campos obligatorios: `id`, `name`, `status`, `description`, `execution`, `tools`, `output_policy`, `evals`.

```yaml
id: erp_query_skill
name: Consulta ERP
status: active

description: >
  Consulta información read-only del ERP Protheus de un tenant autorizado
  mediante la ERP Safe Query API.

execution:
  mode: read_only
  graph: plan_then_execute_graph   # obligatorio para skills que tocan ERP (ver 06)
  requires_human_approval: false

tools:
  - consultar_cliente
  - consultar_parametro_sx6

output_policy:
  summarize_results: true
  mask_sensitive_fields: true
  max_rows: 20

evals:
  status: placeholder
  template: skill_eval_template
```

### 3. Tool Manifest — `manifests/tools/`

Define una operación técnica concreta y su adapter.

Campos obligatorios: `id`, `name`, `status`, `type`, `adapter`, definición del binding (`mcp` u `openapi`), `risk`, `permissions`, `security`, `audit`.

```yaml
id: consultar_cliente
name: Consultar Cliente
status: active

type: openapi_tool
adapter: openapi_rest

openapi:
  operation_id: getClienteByCodigo
  method: GET
  path: /api/v1/clientes/{codigo_cliente}
  base_url_ref: erp_safe_query_api   # resuelto por tenant en runtime

risk:
  level: low
  operation_type: read

permissions:
  mode: read_only
  requires_human_approval: false

security:
  allow_sql_freeform: false
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
id: erp_read_only_policy
status: active

applies_to:
  skills: [erp_query_skill]

rules:
  - effect: allow
    when:
      operation_type: read
      tenant_in: [totalpec, union, resultar]   # tenants habilitados
  - effect: escalate_hitl
    when:
      risk_level: high
  # todo lo demás: deny (implícito)
```

### 5. Routing Manifest — `manifests/routing/`

Reglas del Skill Router: cuándo responder directo, activar skill o delegar.

```yaml
id: default_chat_routing
status: active

rules:
  - intent: erp_query          # consultas sobre datos del ERP
    action: activate_skill
    target: erp_query_skill
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

target_kind: skill
metrics_planned:
  - task_completion_rate
  - tool_call_accuracy
  - groundedness_score
dataset: null          # se define cuando existan casos reales
```

## Reglas obligatorias (resumen del blueprint §2.4.6, adoptadas)

1. Todo agente, skill y tool tiene manifiesto versionado; sin manifiesto no existe.
2. Todo manifiesto se valida contra schema antes de cargarse (CI + arranque).
3. Tools con deny-by-default y mínimo privilegio.
4. Cada skill declara explícitamente sus tools; cada agente sus skills.
5. El eval placeholder existe desde el día uno aunque esté vacío.
6. Toda ejecución se traza (Langfuse/OpenTelemetry); toda llamada a modelo pasa por LiteLLM; toda tool externa pasa por MCP, OpenAPI/ERP Safe Query API o conector aprobado.
