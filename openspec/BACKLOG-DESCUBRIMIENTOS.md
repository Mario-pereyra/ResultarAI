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
- 2026-07-09 · d10 (7.1 contraste) · `design/mockups/tokens.css` trae dos valores de `--ink-faint` cuyo ratio real NO cumple lo que declara `design/DESIGN-SYSTEM.md` §5.3 (verificado con la fórmula WCAG 2.1 dos veces): light·default `#6e7787` sobre `--panel #fffdf8` = 4.44:1 (declara 4.5) y dark·totvs `#74879b` sobre `--panel #0e2030` = 4.48:1 (declara 4.8). En `frontend/styles/tokens.css` se aplicó el ajuste mínimo que cumple el ratio declarado (`#6d7686` → 4.505:1 y `#7a8da1` → 4.852:1), documentado como desvío consciente en el propio archivo. Pendiente: corregir los dos hex (o los ratios documentados) en `design/` aguas arriba — este change tiene prohibido tocar `design/`.
- 2026-07-09 · d10 (review final, H4) · El topbar de Vista 3 incluye elementos diferidos que no están en ningún scenario de d10 ni listados en sus Non-Goals: dot de estado del gateway + perfil LLM visible (Admin) y taxímetro de consumo. Deben aterrizar con sus backends: d12-notificaciones/d13-chat-conversacion (dot/perfil según corresponda) y d16-cuotas-liberaciones (taxímetro). Verificar al proponer esos changes que la Vista 3 quede completa.
