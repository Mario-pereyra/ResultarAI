# 02 — Arquitectura Adoptada

> Última actualización: 2026-07-09
> Decisiones formales: ver [adr/](adr/). Términos: ver [03-glosario-dominio.md](03-glosario-dominio.md).

## El estilo en un párrafo

**Monolito modular en Python con núcleo hexagonal (Ports & Adapters), DDD estratégico y organización por vertical slices.** El núcleo (`core/`) contiene los manifiestos, registries, Policy Gate y reglas de routing — y **no importa ningún framework**. LangGraph, LiteLLM, Langfuse, MCP y Postgres son adapters reemplazables detrás de ports. Existen tres deployables, separados por física de red, no por moda: la plataforma core, la ERP Safe Query API y el Edge Connector Windows.

## Diagrama

```
                    ┌─────────────────────────────────────────────┐
                    │           PLATAFORMA CORE (deployable 1)     │
                    │                                             │
   Usuario ──HTTP──▶│  app/api (FastAPI)                          │
                    │      │                                      │
                    │      ▼                                      │
                    │  app/ (casos de uso)                        │
                    │      │                                      │
                    │  ┌───▼──────────── core/ ────────────────┐  │
                    │  │  manifests · registries · policy      │  │
                    │  │  routing · ports (Protocol)           │  │
                    │  │  (sin frameworks, funciones puras)    │  │
                    │  └───┬────────────────────────────────┬──┘  │
                    │      │ ports                          │     │
                    │  ┌───▼────────┐  ┌────────────┐  ┌────▼───┐ │
                    │  │ adapters/  │  │ adapters/  │  │adapters│ │
                    │  │ runtime_   │  │ llm_       │  │tracing_│ │
                    │  │ langgraph  │  │ litellm    │  │langfuse│ │
                    │  └───┬────────┘  └─────┬──────┘  └────────┘ │
                    │      │ adapters/tools_mcp · tools_openapi   │
                    └──────┼──────────────────────────────────────┘
                           │ HTTPS (red del cliente)
              ┌────────────▼─────────────┐   ┌──────────────────────┐
              │ ERP SAFE QUERY API       │   │ EDGE CONNECTOR       │
              │ (deployable 2, por       │   │ WINDOWS (deployable 3,│
              │ cliente, junto a         │   │ máquina del usuario, │
              │ Protheus)                │   │ usa su VPN activa)   │
              │ allowlist + plantillas   │   │ tool allowlist local │
              └────────────┬─────────────┘   └──────────┬───────────┘
                           ▼                            ▼
                    Protheus (AppServer/DBAccess/MS SQL del cliente)
```

## Bounded contexts

| Bounded context | Responsabilidad | Capa(s) del blueprint v2.4 |
|---|---|---|
| `scaffolding` | Manifiestos, registries, validación de schemas — **el núcleo del dominio** | 3, 4 |
| `orchestration` | Default Chat, Skill Router, graph templates | 4 |
| `governance` | Policy Gate, autorización runtime, HITL, audit log | 1, 11 |
| `tools` | Tool adapters: MCP, OpenAPI, ERP Safe Query API | 5 |
| `connectivity` | Edge Connector, detección de VPN | 6 |
| `gateway` | Binding LiteLLM, cache profiles, canonicalización de prompts | 9 |
| `observability` | Hooks Langfuse/OpenTelemetry, evidencia, costos | 13 |

## Regla de dependencia

La regla que sostiene todo lo demás. **Verificada con import-linter en CI**, no con disciplina (config en [05-estructura-y-convenciones.md](05-estructura-y-convenciones.md)):

1. `core/` no importa `adapters/` ni `app/` ni ningún framework (langgraph, litellm, langfuse, fastapi, httpx…). Solo stdlib + Pydantic.
2. `adapters/` importa `core/` (para implementar sus ports). Un adapter no importa otro adapter.
3. `app/` importa `core/` y compone adapters vía inyección. Nadie importa `app/`.
4. Los manifiestos YAML (`manifests/`) no son código: se cargan y validan contra los schemas de `core/manifests/`.

## Los 3 deployables (física de red, no microservicios)

| Deployable | Dónde corre | Por qué está separado |
|---|---|---|
| **Plataforma core** | Servidor de Resultar (o nube) | Es el producto: monolito modular único |
| **ERP Safe Query API** | Junto al Protheus de cada cliente | Debe alcanzar DBAccess/SQL del cliente; superficie de seguridad propia, allowlist por cliente |
| **Edge Connector Windows** | Máquina del usuario | Aprovecha la VPN activa del usuario (fase transitoria, blueprint patrón 10) |

Todo lo demás vive dentro del monolito. Extraer un servicio nuevo requiere un ADR que demuestre una restricción física u operativa real.

## Flujo de una petición (camino feliz del MVP)

1. El usuario escribe en el chat → `app/api` recibe y autentica.
2. El caso de uso arma el contexto y llama al **Default Chat** (graph template en `adapters/runtime_langgraph`).
3. El **Skill Router** (`core/routing`) decide: respuesta directa o activar una skill.
4. Si activa skill: el **Policy Gate** (`core/policy`) valida usuario, cliente, skill, tool y riesgo. Deny-by-default.
5. La skill invoca su tool vía el adapter correspondiente (`adapters/tools_openapi` → ERP Safe Query API).
6. Toda llamada a modelo pasa por `adapters/llm_litellm` (nunca un SDK de proveedor directo).
7. Cada paso emite trazas vía `adapters/tracing_langfuse`; las decisiones del Policy Gate y tool calls se registran en el audit log append-only.

## Qué NO es esta arquitectura

Anti-patrones evaluados y descartados con evidencia (detalle y fuentes en los ADRs):

- **Microservicios por capa del blueprint** → [ADR-0001](adr/0001-monolito-modular-hexagonal.md) y [ADR-0005](adr/0005-deployables-por-fisica-de-red.md)
- **DDD táctico completo** (aggregates, repositories, domain events por doquier) → [ADR-0002](adr/0002-ddd-estrategico-sin-tactico.md)
- **El esqueleto del código construido sobre un framework de agentes** → [ADR-0003](adr/0003-stack-langgraph-litellm-langfuse-mcp.md)
- **Lógica de agentes/skills/tools hardcodeada en el runtime** → [ADR-0004](adr/0004-manifiestos-declarativos-como-dominio.md)
- **Event-driven, CQRS, cell-based, swarms** → descartados por ahora; ver comparativa en ADR-0001 (consecuencias)
