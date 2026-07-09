# 02 — Arquitectura Adoptada

> Última actualización: 2026-07-09
> Decisiones formales: ver [adr/](adr/). Términos: ver [03-glosario-dominio.md](03-glosario-dominio.md).
> Fuente normativa de producto y UX: ver [`design/`](../design/) — 44 vistas con mockup, flujos E2E, mapa funcional y design system, con los ajustes de la tabla de pivote en [07-roadmap.md](07-roadmap.md). Este documento (`docs/`) manda en arquitectura; ante cualquier contradicción de estilo/estructura técnica, `docs/` prevalece sobre `design/`.

## El estilo en un párrafo

**Monolito modular en Python con núcleo hexagonal (Ports & Adapters), DDD estratégico y organización por vertical slices.** El núcleo (`core/`) contiene los manifiestos, registries, Policy Gate y reglas de routing — y **no importa ningún framework**. LangGraph, LiteLLM, Langfuse, MCP y Postgres son adapters reemplazables detrás de ports. El frontend (Next.js + assistant-ui, `frontend/`) se sirve junto a la plataforma core, dentro del mismo monorepo — no es un deployable separado (ver más abajo). Existen tres deployables, separados por física de red, no por moda: la plataforma core, la ERP Safe Query API y el Edge Connector Windows.

## Diagrama

```
                    ┌─────────────────────────────────────────────┐
                    │           PLATAFORMA CORE (deployable 1)     │
                    │                                             │
                    │  frontend/ (Next.js + assistant-ui)         │
   Usuario ──HTTP──▶│      │                                      │
                    │      ▼                                      │
                    │  app/api (FastAPI)                          │
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

El usuario habla con `frontend/` (Next.js + assistant-ui); el frontend llama a `app/api` — nunca a `core/` ni a los adapters directamente. El frontend se scaffoldea en el change `d10-design-system-shell`; la decisión formal (por qué Next.js + assistant-ui, por qué monorepo con la plataforma core y no deployable propio) queda en ADR-0007.

## Bounded contexts

| Bounded context | Responsabilidad | Capa(s) del blueprint v2.4 |
|---|---|---|
| `scaffolding` | Manifiestos, registries, validación de schemas — **el núcleo del dominio** | 3, 4 |
| `orchestration` | Default Chat, Skill Router, graph templates | 4 |
| `governance` | Policy Gate, autorización runtime, mecanismo HITL (`requires_human_approval`), audit log | 1, 11 |
| `tools` | Tool adapters: MCP, OpenAPI, ERP Safe Query API | 5 |
| `connectivity` | Edge Connector, detección de VPN | 6 |
| `gateway` | Binding LiteLLM, cache profiles, canonicalización de prompts | 9 |
| `observability` | Hooks Langfuse/OpenTelemetry, evidencia, costos | 13 |
| `identity` | Sesiones firmadas con revocación, roles Admin/Técnico/Funcional, TOTP, acuerdo de uso auditado, alta de usuarios/grupos | — (producto, pivote 2026-07-09; `d11`) |
| `quotas` | Cuotas jerárquicas global→grupo→usuario→sesión evaluadas antes de cada llamada, solicitudes y liberaciones auditadas | — (producto, pivote 2026-07-09; `d16`) |
| `approvals` | Producto de aprobaciones sobre el mecanismo HITL de `governance`: cola, tarjeta de aprobación, comentario obligatorio, 4-ojos en irreversibles | — (producto, pivote 2026-07-09; `d17`) |
| `attachments` | Validación e ingesta de adjuntos, extracción por tipo, sanitización anti-injection, escaneo N2/N3, retención | — (producto, pivote 2026-07-09; `d14`) |
| `notifications` | Centro de notificaciones in-app: campana, no-leídas, deep links, filtrado por rol/ownership | — (producto, pivote 2026-07-09; `d12`) |
| `workflows` | Motor de workflows deterministas: pasos fijos por versión, pausa HITL, historial y re-ejecución auditada | — (producto, pivote 2026-07-09; `e22`) |

Los contextos nuevos no están en el blueprint v2.4 (documento de referencia del ERP): nacen del pivote 2026-07-09 hacia el producto completo "de fábrica" (ver [07-roadmap.md](07-roadmap.md)) y su especificación detallada vive en el change de OpenSpec correspondiente, no en este documento.

## Regla de dependencia

La regla que sostiene todo lo demás. **Verificada con import-linter en CI**, no con disciplina (config en [05-estructura-y-convenciones.md](05-estructura-y-convenciones.md)):

1. `core/` no importa `adapters/` ni `app/` ni ningún framework (langgraph, litellm, langfuse, fastapi, httpx…). Solo stdlib + Pydantic, más PyYAML como parser de los manifiestos (formato de datos, no framework).
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

1. El usuario escribe en el chat en `frontend/` (Next.js + assistant-ui) → llama a `app/api`, que recibe y autentica.
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
