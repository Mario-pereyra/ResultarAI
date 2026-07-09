# ADR-0007 — Frontend Next.js + assistant-ui en monorepo

- **Estado:** aceptado (2026-07-09)

## Contexto

El pivote 2026-07-09 ([docs/07-roadmap.md](../07-roadmap.md)) especifica el producto completo por adelantado, con el slice `d10-design-system-shell` arrancando en paralelo con la Etapa B. El paquete de diseño (`design/`) ya trae 44 vistas con mockup construidas sobre Next.js + assistant-ui (intento 2026-06, entonces con backend Node/Mastra). Al adoptar Python + FastAPI + LangGraph + LiteLLM como backend ([ADR-0003](0003-stack-langgraph-litellm-langfuse-mcp.md)), quedaba por decidir: (a) si el frontend se conserva o se re-especifica desde cero, y (b) si vive en el mismo repositorio que el backend o en uno separado.

## Decisión

1. **Conservar Next.js + assistant-ui** como stack de frontend. `design/` es la fuente normativa de producto y UX (44 vistas, flujos E2E, design system dual-brand, anexo de attachments); re-especificar la UI desde cero tiraría ese trabajo sin una razón técnica que lo justifique — el cambio de backend no invalida las decisiones de UI.
2. **Monorepo:** el frontend se scaffoldea en `frontend/` dentro de este mismo repositorio (change `d10-design-system-shell`), no en un repositorio separado.
3. El backend expone contratos versionados (OpenAPI/SSE) que `frontend/` consume como cliente; `core/` sigue sin conocer la existencia del frontend (regla dura 1 intacta — la frontera hexagonal es de dominio, no de repositorio).

## Alternativas consideradas

1. **Repositorio separado para el frontend** — rechazada: un solo repo simplifica el flujo OpenSpec (un change puede tocar contrato API y UI a la vez sin coordinar dos repos), el versionado conjunto de los contratos API↔UI (un PR, un diff, un historial) y el trabajo de agentes en segundo plano (Claude Code opera sobre un único árbol de trabajo sin sincronizar clones).
2. **Re-especificar la UI en otro stack** (p. ej. Vue, Angular, SPA propia) — rechazada: no hay motivo técnico para descartar Next.js + assistant-ui; `design/` ya está construido sobre ese stack y assistant-ui da componentes de chat (streaming, threads, tool calls colapsables) que el roadmap necesita desde `d13-chat-conversacion`.
3. **Monorepo con herramienta de workspaces dedicada (Turborepo, Nx)** — pospuesta: con un solo paquete de frontend y un backend Python (ecosistemas de build distintos, sin paquetes JS compartidos entre ambos) el costo de una herramienta de monorepo JS no se justifica todavía; reevaluar si aparecen múltiples paquetes JS/TS.

## Consecuencias

- (+) Un solo change de OpenSpec puede especificar y versionar contrato + UI juntos, con trazabilidad end-to-end requisito → change → código.
- (+) Los agentes de código trabajan sobre un único árbol; no hay que mantener sincronizados dos repos ni dos flujos de CI independientes para algo que cambia junto.
- (+) El trabajo de diseño ya invertido en `design/` (44 vistas, design system, anexo de attachments) se aprovecha sin re-litigar decisiones de UX.
- (−) El repo mezcla dos ecosistemas de dependencias (Python/uv y Node/pnpm o npm) → mitigado: CI corre pipelines independientes por carpeta (`resultarai/` vs `frontend/`), sin que uno bloquee al otro salvo en los contratos compartidos.
- (−) Cambiar de stack de frontend en el futuro exigiría un ADR nuevo que reemplace este, no solo un refactor de carpeta.

## Fuentes

- `design/` — paquete de diseño UX/UI normativo del producto (44 vistas, flujos E2E, design system, anexo de attachments).
- assistant-ui — componentes de chat para asistentes con streaming, threads y tool calls, integrables sobre Next.js — https://www.assistant-ui.com/
- Next.js — App Router, server components — https://nextjs.org/docs
- `docs/07-roadmap.md`, tabla "Cambios adoptados respecto del paquete de diseño" y change `d10-design-system-shell`.
