# ADR-0003 — Stack agentic (LangGraph, LiteLLM, Langfuse, MCP) solo como adapters

- **Estado:** aceptado (2026-07-09)

## Contexto

El blueprint v2.4 (§2.4.6) recomienda LangGraph (runtime de grafos), LiteLLM (gateway de modelos), Langfuse (observabilidad/prompt management), MCP + OpenAPI 3.1 (contratos de tools) y Pydantic (schemas). El riesgo identificado: el ecosistema agentic rota de frameworks cada 12-18 meses, y la crítica dominante de la industria a los frameworks de agentes es que abstraen demasiado y ocultan prompts/respuestas reales.

## Decisión

Adoptar el stack del blueprint **confinado a adapters**:

| Necesidad | Herramienta | Vive en |
|---|---|---|
| Runtime de grafos/agentes | LangGraph | `adapters/runtime_langgraph/` |
| Gateway de modelos (obligatorio) | LiteLLM | `adapters/llm_litellm/` |
| Trazas, prompts, costos | Langfuse + OpenTelemetry | `adapters/tracing_langfuse/` |
| Contrato de tools | MCP / OpenAPI 3.1 | `adapters/tools_mcp/`, `adapters/tools_openapi/` |
| Schemas y validación | Pydantic v2 | `core/manifests/` (única librería permitida en core) |

Reglas: toda llamada a modelo pasa por LiteLLM (nunca SDKs de proveedor directos); toda ejecución se traza; el import de estas librerías fuera de su adapter es violación de frontera detectada por import-linter.

Además, se adopta **Plan-then-Execute** como graph template obligatorio para skills que tocan el ERP (ver [06-seguridad-gobernanza.md](../06-seguridad-gobernanza.md)): el plan se valida contra el Policy Gate antes de ejecutar, mitigando prompt injection.

## Alternativas consideradas

1. **Construir el esqueleto SOBRE LangGraph** (grafos como estructura del código) — rechazada: acopla el proyecto al framework más volátil de la pila.
2. **Sin framework: llamadas directas al API + loops propios** — viable (es la recomendación base de Anthropic) pero se pierde estado durable, HITL y checkpoints que LangGraph ya resuelve; el confinamiento a adapter da lo mejor de ambos.
3. **Otros orquestadores (CrewAI, AutoGen, OpenAI Agents SDK)** — rechazados: menor madurez para flujos gobernados con HITL, o lock-in a un proveedor de modelos.
4. **Gateway propio en lugar de LiteLLM** — rechazada: reinventar routing, fallback, budgets y cache profiles que LiteLLM ya provee y el blueprint exige medir.

## Consecuencias

- (+) Reemplazar cualquier pieza del stack = reescribir un adapter, con contract test que define el comportamiento esperado.
- (+) Los prompts y tool schemas quedan visibles y versionados (Stable Prompt Builder / canonicalización sobre LiteLLM, blueprint patrón 9).
- (−) Capa de indirection extra (ports) → aceptada como costo del desacople.

## Fuentes

- Anthropic, "Building Effective Agents" (patrones simples y componibles antes que frameworks) — https://www.anthropic.com/research/building-effective-agents
- Anthropic, multi-agent research system (orchestrator-workers en producción) — https://www.anthropic.com/engineering/multi-agent-research-system
- SAP, Plan-then-Execute como patrón de IA agentic responsable — https://community.sap.com/t5/security-and-compliance-blog-posts/plan-then-execute-an-architectural-pattern-for-responsible-agentic-ai/ba-p/14239753
- AWS Prescriptive Guidance, LangChain/LangGraph — https://docs.aws.amazon.com/prescriptive-guidance/latest/agentic-ai-frameworks/langchain-langgraph.html
- Blueprint v2.4, §2.4.6 y Patrón 12 — [referencia local](../referencias/arquitectura_plataformas_ia_internas_v2_4_agentic_scaffolding.md)
