# Backlog de descubrimientos

> Hallazgos fuera de alcance detectados durante la implementación (regla del orquestador:
> descubrimientos, mejoras o huecos se anotan aquí, no se implementan).
> Formato: fecha · change origen · nota.

## Huecos conocidos declarados de antemano (no resolver)

- 2026-07-09 · d19 · CRUD de definiciones de cuota (vista 33): señalado como hueco en d19; no implementar.
- 2026-07-09 · d20 · UI admin de backups/retención (vista 39 §6): hueco declarado; no implementar.

## Descubrimientos de implementación

- 2026-07-09 · a01 (review final) · `a02` debe implementar el strict mode que `docs/04` ya promete: rechazo de claves desconocidas, invariante `read_only` ⇒ `plan_then_execute_graph`, `allow_sql_freeform: false`, validación cruzada de `enabled_skills`/`tools` contra registries. Además conviene que adopte los identificadores ya fijados por docs/04: `skill_package.{spec,ref,path,version}`, `mcp.{server,tool_name,spec_revision,endpoint_ref}`, `visibility.roles`, `risk.level`.
- 2026-07-09 · a01 (review final) · En el conjunto de fábrica, `retrieval` queda ausente/`enabled: false` y nunca invoca adapter; `RetrievalPort` real llega en `a03` con adapter nulo (a02/a03 deben respetarlo).
- 2026-07-09 · a01 (review final) · La CI actual solo cubre Python; cuando `d10` cree `frontend/` hay que añadir el pipeline JS (lint/typecheck/build) como job(s) independientes por carpeta (ADR-0007 lo anticipa).
- 2026-07-09 · a02 (review final) · Hardening de import-linter: el contrato "forbidden" es denylist de frameworks nombrados; no atraparía un import accidental de un paquete externo no listado (p. ej. requests) en core/. Considerar contrato allowlist más estricto.
- 2026-07-09 · a02 (review final) · La detección de graph plan-then-execute es por prefijo (startswith "plan_then_execute"); convención aceptada — endurecer a catálogo de graphs válidos cuando b06 defina los Graph Templates reales.
