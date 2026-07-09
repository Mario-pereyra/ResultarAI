# CLAUDE.md — ResultarAI

## Qué es este proyecto

Plataforma interna de IA de Resultar Soluciones (partner TOTVS Bolivia): chat gobernado (Default Chat) que activa skills aprobadas para consultar sistemas —empezando por el ERP Protheus— de forma segura, trazable y sin acceso directo a bases de datos.

## Estado actual

**Greenfield en fase de diseño.** Documentación y paquete de diseño UX (`design/`) completos; sin código todavía. **Pivote 2026-07-09:** producto completo genérico "de fábrica" primero (Etapas A–E), personalización Protheus después (Etapa P) — ver `docs/07-roadmap.md`. Etapa activa: **A — Fundación** (change `a01-fundacion-repo`). *(Actualizar esta línea al avanzar de etapa.)*

## Arquitectura en 60 segundos

Monolito modular Python + núcleo hexagonal + DDD estratégico. `core/` (manifiestos Pydantic, registries, Policy Gate, Skill Router, ports) **no importa ningún framework** — LangGraph, LiteLLM, Langfuse, MCP y Postgres son adapters detrás de ports. Tres deployables separados por física de red: plataforma core, ERP Safe Query API (junto al Protheus de cada cliente) y Edge Connector Windows. Agentes/skills/tools se declaran en manifiestos YAML versionados, no en código.

Detalle: `docs/02-arquitectura.md`. Decisiones con evidencia: `docs/adr/`.

## Reglas duras (no negociables)

1. `core/` no importa frameworks ni adapters (verificado con import-linter; solo stdlib + Pydantic).
2. Toda llamada a modelo pasa por LiteLLM. Nunca SDKs de proveedor directos.
3. Tools solo vía skills. El Default Chat nunca ejecuta tools directamente.
4. Policy Gate deny-by-default, evaluado en cada paso; toda decisión va al audit log (append-only).
5. Nunca SQL libre contra el ERP: solo ERP Safe Query API con allowlist y plantillas.
6. Todo agente/skill/tool tiene manifiesto YAML versionado y validado; sin manifiesto no existe.
7. Skills que tocan el ERP usan plan-then-execute (plan validado antes de ejecutar).
8. Usar exactamente los términos de `docs/03-glosario-dominio.md` — sin sinónimos.
9. Docs, specs y commits en español; código e identificadores en inglés.

## Mapa del repo

| Ruta | Contenido |
|---|---|
| `docs/` | Documentación adoptada y vigente (manda sobre el blueprint) |
| `docs/adr/` | Decisiones de arquitectura (MADR-lite) |
| `docs/referencias/` | Blueprint v2.4 y contexto de la empresa (solo referencia, se cita, no se copia) |
| `design/` | Paquete de diseño UX/UI **normativo** del producto: 44 vistas con mockup, flujos E2E, mapa funcional, design system, anexo de attachments (con los ajustes de la tabla de pivote en `docs/07-roadmap.md`) |
| `openspec/` | Flujo spec-driven: specs (lo construido) y changes (lo propuesto) |
| `resultarai/` | `[placeholder — lo crea el change scaffolding-esqueleto: core/, adapters/, app/, manifests/, tests/]` |

## Comandos

`[placeholder — los define el change scaffolding-esqueleto: uv sync, pytest, ruff check, mypy, lint-imports]`

## Flujo de trabajo

**Nunca implementar sin un change de OpenSpec aprobado** (ADR-0006): `propose` → revisión humana → `apply` (tarea por tarea) → `archive`. Antes de proponer, leer `docs/02-arquitectura.md`, `docs/03-glosario-dominio.md` y `docs/04-manifiestos.md`. El roadmap (`docs/07-roadmap.md`) nombra los changes sugeridos por fase.

## Índice de documentación

| Doc | Contenido |
|---|---|
| `docs/01-vision.md` | Qué es, usuarios, alcance MVP, no-objetivos, jerarquía docs/blueprint |
| `docs/02-arquitectura.md` | Estilo adoptado, bounded contexts, regla de dependencia, deployables, flujo de petición |
| `docs/03-glosario-dominio.md` | Lenguaje ubicuo: scaffolding, conectividad, Protheus |
| `docs/04-manifiestos.md` | Los 6 contratos declarativos con ejemplos YAML y ciclo de vida |
| `docs/05-estructura-y-convenciones.md` | Árbol de paquetes, convenciones Python, testing, import-linter |
| `docs/06-seguridad-gobernanza.md` | Policy Gate, riesgo/HITL, audit log, data boundaries, plan-then-execute, evals |
| `docs/07-roadmap.md` | Fases → changes OpenSpec sugeridos |
| `docs/adr/0001…0006` | Decisiones: estilo, DDD, stack, manifiestos, deployables, OpenSpec |
