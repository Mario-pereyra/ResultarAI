# 01 — Visión y Alcance

> Última actualización: 2026-07-09

## Qué es ResultarAI

ResultarAI es la **plataforma interna de IA de Resultar Soluciones**, partner oficial de TOTVS en Bolivia. Es un chat gobernado (Default Chat) que puede responder consultas, activar capacidades aprobadas (skills), ejecutar workflows deterministas y —cuando exista un caso real— delegar a agentes especializados, para consultar sistemas internos y de clientes (empezando por el ERP Protheus) de forma **segura, trazable y sin acceso directo a bases de datos**.

El problema que resuelve: hoy el conocimiento operativo (consultas al ERP, parámetros SX6, estados de pedidos, documentación TOTVS) requiere acceso manual, conocimiento técnico de Protheus o escalamiento a consultores. ResultarAI lo expone a través de un chat con permisos, políticas y auditoría.

## Usuarios objetivo

1. **Fábrica de software (juniors)** — consultas técnicas de Protheus, diagnóstico asistido, consulta de diccionarios y parámetros.
2. **Consultores (seniors y semi-seniors)** — consultas rápidas al ERP de clientes sin abrir SQL ni SmartClient.
3. **Consultoras funcionales** — verificación de datos de negocio y estados de procesos durante análisis.

Estos perfiles operan la plataforma bajo tres roles (Admin, Técnico, Funcional), cada uno con su propia capa de visibilidad sobre una única UI ([docs/07-roadmap.md](07-roadmap.md), changes `d10`/`d11`).

## Alcance: producto completo "de fábrica" + personalización

**Pivote 2026-07-09 (decisión del product owner):** el alcance es **especificar y construir el producto completo por adelantado**, en dos grandes bloques ejecutados change por change (detalle completo, orden y criterios "hecho cuando" en [07-roadmap.md](07-roadmap.md); no se duplican aquí):

1. **Etapas A–E — plataforma genérica "de fábrica".** El Default Chat sin nombre, con contenido de ejemplo (1 skill, 1 MCP server sencillo, 1 workflow), queda completo y operable *antes* de cualquier personalización Protheus:
   - **A — Fundación**: repo, estructura de paquetes, CI, manifiestos de los 6 contratos, Policy Gate y gobernanza base.
   - **B — Motor de ejecución**: persistencia append-only, gateway de modelos vía LiteLLM, runtime LangGraph + Skill Router, observabilidad Langfuse.
   - **C — Capacidades agénticas**: soporte a las specs oficiales Agent Skills y MCP.
   - **D — Producto**: slices verticales backend+UI (identidad y acceso, notificaciones, chat, attachments, catálogo de agentes, cuotas, aprobaciones HITL, mi espacio, administración, gobernanza de plataforma, builders).
   - **E — Calidad y operación**: workflows deterministas, memoria de usuario, despliegue/operación, evals y gates de publicación.
2. **Etapa P — personalización Protheus/ERP.** Solo después de tener la plataforma genérica funcionando, el product owner define y ejecuta la personalización para TOTVS Protheus: ERP Safe Query API, Edge Connector Windows, agentes especializados (documental TDN con RAG real, validación de parametrización, dev AdvPL/TLPP), selector cliente/ambiente, niveles de datos por sesión/ambiente, y demás ítems enumerados en el roadmap.

### Criterio de éxito por etapa (resumen — detalle en el roadmap)

El roadmap define, change por change, la condición "hecho cuando"; aquí solo el resumen por etapa:

| Etapa | Criterio de éxito (resumen) |
|---|---|
| A — Fundación | CI en verde verifica las fronteras de `core/`; manifiestos de ejemplo validan; Policy Gate deny-by-default emite `AuditEvent` en cada decisión, sin red. |
| B — Motor de ejecución | Historial append-only nunca se reescribe (editar/regenerar crea rama); fallback y escalación de modelo son observables; una conversación completa pasa por Router + Policy Gate y es reconstruible en Langfuse con su costo. |
| C — Capacidades agénticas | El Default Chat resuelve una consulta con la skill de ejemplo (spec Agent Skills) y ejecuta una tool del MCP server de ejemplo vía skill, pasando por el gate y quedando auditada. |
| D — Producto | Los flujos E2E del `design/` (alta y acceso, chat, attachments, catálogo, cuotas, aprobaciones, mi espacio, administración, gobernanza, builders) funcionan de punta a punta respetando la matriz de roles. |
| E — Calidad y operación | El workflow de ejemplo corre end-to-end con pausa HITL; una instancia limpia se levanta con un comando y pasa el smoke test; publicar con evals en rojo es imposible por sistema. |
| P — Personalización | Cada ítem de personalización Protheus (ERP Safe Query API, Edge Connector, agentes especializados, RAG real, niveles de datos) nace como change propio sobre la plataforma ya terminada, definido por el product owner. |

## No-objetivos (explícitos)

- **No reemplaza a Protheus** ni a sus interfaces nativas (SIGAMDI, SIGACFG, APSDU). Es una capa de consulta y asistencia.
- **No ejecuta SQL libre, nunca.** Toda consulta al ERP pasa por la ERP Safe Query API con allowlist de tablas/campos y plantillas de consulta. Regla alineada con la matriz de soluciones autorizadas de la empresa (interfaces nativas / APSDU / MsExecAuto).
- **No personaliza Protheus antes de tiempo.** Toda integración específica del ERP (Safe Query API, Edge Connector, agentes documentales/dev, selector cliente/ambiente) es Etapa P, posterior a la plataforma genérica ya funcionando.
- **No implementa RAG real todavía.** Etapa A–E deja la puerta abierta (`RetrievalPort` + campos de manifiesto + adapter nulo); el RAG real sobre documentación TOTVS es Etapa P.
- **No construye infraestructura especulativa**: nada de control plane distribuido, colas de eventos ni celdas hasta que un problema concreto lo justifique.
- Las escrituras en el ERP (vía MsExecAuto) y cualquier acción irreversible siempre requieren aprobación humana (HITL) — regla dura, no negociable, vigente desde la Etapa D (`d17-hitl-aprobaciones`).

## Relación con el blueprint v2.4 y con `design/`

El documento [referencias/arquitectura_plataformas_ia_internas_v2_4_agentic_scaffolding.md](referencias/arquitectura_plataformas_ia_internas_v2_4_agentic_scaffolding.md) es la **referencia aspiracional**: describe el estado objetivo completo (13 capas, componentes, métricas, patrones).

El paquete `design/` (44 vistas con mockup, flujos E2E, mapa funcional, design system, anexo de attachments) es la **fuente normativa de producto y UX**: define qué se construye visualmente y cómo se comporta, con los ajustes de la tabla de pivote en [07-roadmap.md](07-roadmap.md) (runtime, agentes concretos, skills, tools, modelos y extracción de adjuntos se adaptan al stack Python adoptado).

**Regla de jerarquía documental:**

- `docs/` (este directorio) = **lo adoptado y vigente** en arquitectura, dominio y proceso. Si hay conflicto, manda `docs/`.
- `design/` = normativo en producto y UX; sus ajustes de pivote se listan en `docs/07-roadmap.md`.
- El blueprint = referencia aspiracional. Se **cita por sección** (p. ej. "blueprint §2.4.6"), nunca se copia su contenido a los docs.
- El contexto de la empresa vive en [referencias/contexto-resultar-soluciones.md](referencias/contexto-resultar-soluciones.md).
