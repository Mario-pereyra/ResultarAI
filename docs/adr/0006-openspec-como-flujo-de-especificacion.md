# ADR-0006 — OpenSpec como flujo de especificación y desglose de trabajo

- **Estado:** aceptado (2026-07-09)

## Contexto

El proyecto lo construye un equipo chico asistido intensivamente por agentes de código (Claude Code). Sin un flujo de especificación, el trabajo asistido por IA tiende a implementar sin contrato previo, perdiendo trazabilidad de qué se pidió, qué se decidió y qué quedó construido.

## Decisión

Usar **OpenSpec** (https://openspec.dev/) como flujo spec-driven del proyecto:

1. **`openspec/specs/`** = la verdad de lo que ESTÁ construido (se actualiza al archivar changes).
2. **`openspec/changes/`** = propuestas de cambio: proposal → specs delta → tasks → apply → archive.
3. **Nada se implementa sin un change aprobado.** El flujo es: `propose` (proposal + specs + tasks) → revisión humana → `apply` (implementación tarea por tarea) → `archive` (sincroniza specs).
4. El contexto para los agentes vive en `openspec/config.yaml` (`context` + `rules`) y apunta a `docs/` — no duplica su contenido.
5. División documental: `docs/` = arquitectura y decisiones estables; `openspec/` = especificación funcional y desglose fino. El [roadmap](../07-roadmap.md) solo nombra milestones con su change sugerido; el detalle vive en los changes.

## Alternativas consideradas

1. **Issues/tareas sueltas (Jira, GitHub Issues, TODO.md)** — rechazada: no versionan specs ni distinguen "lo propuesto" de "lo construido".
2. **Specs manuales en docs/** — rechazada: docs/ quedaría desactualizado con cada feature; OpenSpec automatiza la sincronización spec↔realidad al archivar.
3. **Spec-kit u otros flujos spec-driven** — OpenSpec ya está instalado, es liviano y tiene integración directa con Claude Code (skills opsx). Reevaluar solo si aparece una limitación concreta.

## Consecuencias

- (+) Desglose extenso y detallado de tareas con contrato verificable por tarea.
- (+) Trazabilidad requisito → change → código; specs vivas de lo construido.
- (−) Ceremonia mínima por feature (proposal antes de código) → aceptada: es exactamente el control que un equipo junior + agentes de IA necesita.

## Fuentes

- OpenSpec — https://openspec.dev/ y https://github.com/Fission-AI/OpenSpec
- Config del proyecto: [`openspec/config.yaml`](../../openspec/config.yaml)
