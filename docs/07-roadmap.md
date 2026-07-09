# 07 — Roadmap

> Última actualización: 2026-07-09 (pivote a producto completo)
> **Regla anti-duplicación:** este roadmap nombra etapas, changes, dependencias y criterios de salida. El desglose fino (proposal, specs, tasks) vive SOLO en `openspec/changes/` ([ADR-0006](adr/0006-openspec-como-flujo-de-especificacion.md)).

## Pivote 2026-07-09 — producto completo "de fábrica"

Decisión del product owner (reemplaza el enfoque MVP-incremental anterior):

1. **Se especifica TODO el producto por adelantado** (Etapas A–E) y la implementación se ejecuta change por change, en orden, apta para ejecución en segundo plano por agentes.
2. **Primero la plataforma genérica** ("de fábrica"): el agente default sin nombre + contenido de ejemplo (1 skill, 1 MCP server sencillo, 1 workflow). **Toda personalización Protheus/ERP llega después** (Etapa P) y la define el product owner sobre la plataforma ya funcionando.
3. **`design/` es la fuente normativa de producto y UX** (44 vistas con mockup, flujos E2E, mapa funcional, design system, anexo de attachments); `docs/` manda en arquitectura. Diferencias → tabla siguiente.
4. **Contratos oficiales:** skills según la spec **Agent Skills** (agentskills.io, formato SKILL.md); tools según la spec **MCP** vigente (revisión 2025-11-25, confirmada al proponer `c09`).
5. **RAG queda como puerta abierta:** `RetrievalPort` + campos de manifiesto + adapter nulo. No se implementa.

## Cambios adoptados respecto del paquete de diseño (`design/`)

| Tema | design/ (intento 2026-06) | Adoptado ahora |
|---|---|---|
| Runtime backend | Node/Mastra, gateway `:4111`, Better Auth | Python: FastAPI + LangGraph + LiteLLM ([docs/02](02-arquitectura.md)); auth con librería Python mantenida + TOTP (pyotp) — nunca criptografía artesanal |
| Agentes concretos | DocAgent, ValidationAgent, DevAgent | Solo `default_chat` + agente de ejemplo; los agentes reales son personalización (Etapa P) |
| Skills | Paquete propio (instrucciones + ejemplos + tools) | Spec oficial Agent Skills (SKILL.md, progressive disclosure) envuelta por el Skill Manifest, que aporta la capa de gobernanza |
| Tools | Bridge propio `tat-mcp` | Spec oficial MCP (cliente + registro); MCP server de ejemplo genérico; el bridge Protheus → Etapa P |
| Modelos | `deepseek-v4-flash/pro` hardcodeados | Perfiles de modelo + cascada de fallback por config vía LiteLLM (proveedor-agnóstico); la economía cache-first y el marcador de escalación se conservan como mecanismo genérico |
| Protheus | Selector cliente/ambiente, checklists, SQL INBOLSA, niveles N por ambiente | Etapa P completa; el escaneo N2/N3 de adjuntos SÍ entra ahora (es genérico) |
| Extracción de adjuntos | SheetJS / unpdf / mammoth / tesseract.js (Node) | Equivalentes Python: openpyxl + python-calamine, pypdf, mammoth (existe en Python), pytesseract; Presidio + reglas propias para PII |
| ADRs 0001–0014 citados | Numeración del intento anterior | Histórica. `docs/adr/` actual es canónico; el pivote genera ADRs nuevos (frontend, auth, specs oficiales) en `a01-fundacion-repo` |
| Frontend | Next.js + assistant-ui | Se conserva (ADR nuevo lo formaliza) |

**Principios del design que se adoptan sin cambio:** una sola UI por capas de rol (Admin/Técnico/Funcional), append-only / branch-never-rewrite, transparencia de costo y de modelo, dual-brand por tokens con dark+light, estados de error accionables, instancia por cliente, WCAG 2.1 AA, i18n preparado (ES, PT-BR después), centro de notificaciones in-app, workflows como sección propia.

## Convención de asignación de modelos (escalera `/asignar-modelo`)

**Cada tarea de cada `tasks.md` declara su escalón** con el sufijo `[modelo: haiku|sonnet|opus]`. Guía de colocación para este proyecto:

| Escalón | Tareas típicas |
|---|---|
| `haiku` | Fixtures y manifiestos de ejemplo, seeds, portar textos UI y tokens ya definidos en `design/`, boilerplate de migraciones, documentación derivada |
| `sonnet` (default) | Endpoints y CRUD, adapters (LiteLLM/Langfuse), componentes UI desde mockups, tests, extractores por tipo de archivo, consolas admin |
| `opus` | Contratos de `core/` (schemas, ports), Policy Gate, modelo append-only/ramas, motor de cuotas, compliance con specs MCP/Agent Skills, seguridad de adjuntos (N2/N3, anti-injection), gates de evals, review final de cada change |

La señal legítima para subir de escalón es un fallo observado en esa misma tarea.

---

## Etapa A — Fundación (repo y dominio)

*Prerrequisito manual: `git init` + commit de línea base + API key de al menos un proveedor LLM.*

| # | Change | Alcance | Hecho cuando |
|---|---|---|---|
| 01 | `a01-fundacion-repo` | Estructura de paquetes ([docs/05](05-estructura-y-convenciones.md)), uv, CI (ruff, mypy, import-linter, pytest), pre-commit; ADRs del pivote (frontend Next.js+assistant-ui, auth Python, specs oficiales); sincronización de docs 01/02/03/04 con el pivote | CI en verde verifica fronteras; docs sin contradicciones con este roadmap |
| 02 | `a02-core-manifiestos` | Schemas Pydantic de los 6 manifiestos (Skill Manifest referencia paquetes SKILL.md; Tool Manifest referencia servers MCP); registries; validación CLI + arranque fail-fast; manifiestos de fábrica (`default_chat`, skill/tool/policy/routing/eval de ejemplo) | Los manifiestos de ejemplo validan en CI; referencias cruzadas verificadas |
| 03 | `a03-core-gobernanza` | Policy Gate puro deny-by-default (allow/deny/escalate_hitl), niveles de riesgo, `AuditEvent`; ports: `LLMPort`, `ToolPort`, `TracePort`, `StatePort`, `PolicyPort` y `RetrievalPort` (placeholder RAG con adapter nulo) | Tests de tabla de decisión del gate corren sin red; toda decisión emite AuditEvent |

## Etapa B — Motor de ejecución

| # | Change | Alcance | Hecho cuando |
|---|---|---|---|
| 04 | `b04-persistencia-postgres` | Postgres + Alembic; sesiones y mensajes **append-only** con `parent_id` (ramas, branch-never-rewrite); stickiness de perfil por sesión; audit log append-only; schema de attachments | Editar/regenerar crea rama; nada reescribe historia (test de invariante) |
| 05 | `b05-gateway-modelos` | Adapter LiteLLM: perfiles de modelo + cascada de fallback por config; etiqueta "modelo alterno"; contadores cache hit/miss; marcador genérico de escalación (`<<<NEEDS_PRO>>>`) que un adjunto no puede disparar | Fallback y escalación observables en tests con proveedor simulado |
| 06 | `b06-runtime-grafos` | LangGraph: graph template de respuesta directa; Skill Router con routing manifest; Policy Gate evaluado por paso; compaction al 80% (una vez, frontera de turno) | Conversación completa pasa por router + gate con trazas de decisión |
| 07 | `b07-observabilidad` | Adapter Langfuse: traza por turno con costo/sesión/usuario enmascarado; feedback 👍/👎 ligado a traza y a versión de prompt | Un turno cualquiera es reconstruible en Langfuse con su costo |

## Etapa C — Capacidades agénticas (specs oficiales)

| # | Change | Alcance | Hecho cuando |
|---|---|---|---|
| 08 | `c08-agent-skills` | Soporte de la spec Agent Skills: descubrimiento de paquetes SKILL.md, progressive disclosure, `allowed-tools`; el `default_chat` se especializa por skill activa (las tools SIEMPRE llegan vía skill — regla dura 3 intacta); skill de ejemplo de fábrica | El default chat resuelve una consulta usando la skill de ejemplo conforme a la spec |
| 09 | `c09-mcp-tools` | Cliente MCP según spec vigente; binding con Tool Registry; clasificación lectura/escritura/riesgo **fija por versión** (cambiarla = PR); tool calls visibles (colapsadas/expandibles); MCP server de ejemplo sencillo (utilidades) | Una tool del server de ejemplo se ejecuta vía skill, pasa por el gate y queda auditada |

## Etapa D — Producto (slices verticales: backend + UI juntos)

*El slice `d10` puede arrancar en paralelo con la Etapa B (los contratos ya estarán especificados).*

| # | Change | Alcance | Hecho cuando |
|---|---|---|---|
| 10 | `d10-design-system-shell` | Frontend Next.js + assistant-ui: tokens dual-brand (dark+light), tipografías, componentes base, shell única por capacidades de rol, i18n externalizado, WCAG AA, responsive base; banner permanente de IA | Styleguide renderiza los 4 sets de tokens; shell filtra secciones por rol |
| 11 | `d11-identidad-acceso` | Sesiones server-side firmadas con revocación; roles Admin/Técnico/Funcional; TOTP obligatorio Admin (opcional resto); sin registro público; acuerdo de uso auditado con re-aceptación; primer acceso (wizard); gestión de usuarios/grupos (admin) | Flujo A del design completo: alta → primer login → acuerdo → shell |
| 12 | `d12-notificaciones` | Centro de notificaciones in-app: campana, no-leídas, deep links, filtrado por rol/ownership | Una solicitud de liberación notifica al Admin y la decisión al solicitante |
| 13 | `d13-chat-conversacion` | Chat completo: streaming SSE, markdown/código, edición=rama + selector de versiones, regenerar, aviso de regeneración costosa, escalación manual a Pro (nueva rama), etiqueta modelo alterno, tarjetas de error accionables, ejemplos clicables, historial de sesiones, indicador de compaction | Flujos B (sin citas), D y G del design funcionan end-to-end |
| 14 | `d14-attachments` | Pipeline del ANEXO completo en Python: validación magic bytes + allowlist, extracción por tipo (XLSX/CSV/PDF/DOCX/TXT/código/logs), sanitización anti-injection (spotlighting), escaneo N3=bloqueo / N2=confirmación auditada, truncado única vez, dedup sha256, retención 90 días, "Ver lo que verá el agente"; OCR opt-in diferido a iteración posterior | Flujo H del design completo; secretos bloquean; PII exige confirmación auditada |
| 15 | `d15-catalogo-agentes` | Catálogo filtrado por matriz visibilidad agente×rol; ficha con capa común y ficha técnica (T/A); estado kill-switch visible; iniciar conversación | Cada rol ve exactamente lo que su matriz permite |
| 16 | `d16-cuotas-liberaciones` | Cuotas jerárquicas global→grupo→usuario→sesión evaluadas ANTES de cada llamada (tarifas hit/miss separadas); aviso 80% / bloqueo 100%; solicitud y liberación auditadas; Mi consumo (% para Funcional, tokens/costo para T/A) | Flujo E del design completo |
| 17 | `d17-hitl-aprobaciones` | Tarjeta de aprobación (payload, riesgo, expiración=rechazo auditado), comentario obligatorio en críticos, segunda aprobación 4-ojos en irreversibles, cola + historial, móvil primera clase; escrituras JAMÁS sin aprobación | Una tool de escritura del server de ejemplo se detiene en tarjeta y se reanuda al aprobar |
| 18 | `d18-mi-espacio` | Auditoría personal, mis adjuntos (descarga auditada), mis solicitudes, configuración personal (tema, idioma, TOTP, contraseña) | Cada usuario reconstruye su propio rastro sin ver el de otros |
| 19 | `d19-admin-operacion` | Tablero de operación, telemetría/analítica (solo Admin), audit log global con filtros y export, salud del sistema (links Langfuse/Uptime Kuma) | El Admin responde "quién hizo qué, cuándo y cuánto costó" sin salir de la consola |
| 20 | `d20-gobernanza-plataforma` | Registro de prompts (versiones inmutables, draft→published→retired, diff, activar/rollback sin deploy, espejo Git); feature flags + kill-switch por agente y tool (<1 min, auditado, flujo I del design); tools y permisos; configuración de instancia (branding, retención, límites, matrices) | Publicar, activar, rollback y kill-switch operan sin deploy y quedan auditados |
| 21 | `d21-builders` | Agent Builder y Skills Builder (solo Admin): validan spec oficial, toolset del registro, publicar exige evals en verde; propuestas guiadas de Técnicos; sandbox self-service sin escrituras | Un agente creado en el builder queda en catálogo tras pasar el gate |

## Etapa E — Calidad y operación

| # | Change | Alcance | Hecho cuando |
|---|---|---|---|
| 22 | `e22-workflows-deterministas` | Motor de workflows (pasos fijos por versión), formulario tipado con archivos esperados, pasos con estado en vivo, pausa HITL, resultado descargable, historial + re-ejecución + cancelación auditada; workflow de ejemplo de fábrica | El workflow de ejemplo corre end-to-end con una pausa HITL |
| 23 | `e23-memoria-usuario` | Mi memoria (ver/editar/borrar; el agente solo PROPONE y el usuario confirma; límite ~1k tokens; snapshot post-prefijo), indicador de memoria usada en chat; memoria de proyecto compartida queda para Etapa P | Una propuesta de memoria aceptada aparece editable y entra en la sesión siguiente |
| 24 | `e24-despliegue-operacion` | Docker Compose (plataforma, Postgres, Langfuse, Uptime Kuma), backups, hardening (rate limits, headers, gateway no público), seed inicial, smoke test E2E, runbook de incidentes | Instancia limpia se levanta de cero con un comando y pasa el smoke test |
| 25 | `e25-evals-gates` | **Ejecutada por el product owner al final** (especificada desde ya): datasets YAML por agente/skill (solo datos sintéticos), runner, score por versión, gate de publicación (≥80%, casos safety = hard-fail individual), integración CI, feedback 👎 → caso de regresión | Publicar con evals en rojo es imposible por sistema |

**Nota de desacople (decisión 2026-07-09):** los gates de publicación de `d20-gobernanza-plataforma` y `d21-builders` nacen **pluggables**: mientras `e25-evals-gates` no esté archivado operan en modo placeholder (score ausente = advertencia visible, no bloqueo). La instrumentación Langfuse queda completa desde `b07-observabilidad` (trazas, costo, feedback ligado a traza y versión de prompt); lo ÚNICO diferido es el runner de evals/golden sets.

## Etapa P — Personalización (post-fábrica; la define el product owner)

Solo enumerada; cada ítem nacerá como change propio sobre la plataforma terminada: ERP Safe Query API (deployable 2), Edge Connector Windows (deployable 3), agentes personalizados (documental TDN con RAG real sobre `RetrievalPort`, validación de parametrización con checklists, dev AdvPL/TLPP), selector cliente/ambiente y perfiles de conexión (vistas 27/28/29/36 del design), niveles de datos por sesión/ambiente, política datos×proveedor con ZDR, OCR opt-in, visión, PT-BR activado, prompt caching medido, FinOps avanzado, memoria de proyecto, evals con datos reales.

## Orden y paralelismo

```
A(01→02→03) ──▶ B(04→05→06→07) ──▶ C(08→09) ──▶ D(11→…→21) ──▶ E(22→23→24) ──▶ E(25 evals, P.O.) ──▶ P
                     │
                     └─ paralelo: D(10) design-system-shell
```

Regla de ejecución: un change se implementa solo con sus dependencias archivadas (o su interfaz ya especificada); cada tarea corre con el modelo declarado en su `[modelo: …]`.
