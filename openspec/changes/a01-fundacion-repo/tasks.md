# Tasks — a01-fundacion-repo

## 1. Sincronización documental del pivote

- [x] 1.1 Actualizar `docs/01-vision.md`: alcance = producto completo de fábrica (Etapas A–E) + personalización (Etapa P); eliminar secciones MVP; criterio de éxito por etapa. Verificación: cero menciones a "MVP" como alcance vigente. `[modelo: sonnet]`
- [x] 1.2 Actualizar `docs/02-arquitectura.md`: agregar frontend (Next.js + assistant-ui, servido junto a la plataforma core), bounded contexts nuevos del producto (identidad, cuotas, HITL, attachments, notificaciones, workflows) y referencia a design/ como fuente de UX. Verificación: diagrama y tablas coherentes con docs/07. `[modelo: sonnet]`
- [x] 1.3 Actualizar `docs/03-glosario-dominio.md`: agregar términos del producto (Agent Skill, MCP Server, Attachment, Extracción, Cuota, Liberación, Tarjeta HITL, Segunda aprobación, Workflow, Notificación, Memoria de usuario, Instancia, Rol Admin/Técnico/Funcional, Niveles N0–N3, Registro de Prompts, Kill switch, Perfil de modelo, Marcador de escalación). Verificación: todos los términos usados por los changes a02–e25 existen aquí. `[modelo: sonnet]`
- [x] 1.4 Actualizar `docs/04-manifiestos.md`: Skill Manifest referencia un paquete SKILL.md (spec Agent Skills) y Tool Manifest referencia un MCP server (spec MCP); ejemplos YAML actualizados; regla de oro intacta. Verificación: ejemplos validan contra los schemas que definirá a02. `[modelo: opus]`
- [x] 1.5 Escribir ADR-0007 (frontend Next.js + assistant-ui en monorepo), ADR-0008 (stack auth Python: sesiones server-side + Argon2id + TOTP, librería elegida con evaluación) y ADR-0009 (adopción de specs oficiales Agent Skills y MCP con versión fijada). Verificación: formato MADR-lite con alternativas y fuentes. `[modelo: sonnet]`

## 2. Esqueleto Python y tooling

- [x] 2.1 Crear `pyproject.toml` (uv): metadata, Python ≥3.12, dependencia pydantic v2; grupo dev con ruff, mypy, pytest, import-linter, pre-commit. Verificación: `uv sync` termina sin errores. `[modelo: sonnet]`
- [x] 2.2 Crear el árbol de paquetes de docs/05 (`resultarai/core|adapters|app`, `manifests/{agents,skills,tools,policies,routing,evals}/`, `tests/{core,contracts}/`) con `__init__.py`, `py.typed` y `.gitkeep` donde aplique. Verificación: escenario "Árbol de paquetes importable" de la spec. `[modelo: haiku]`
- [x] 2.3 Configurar ruff (lint + format) y mypy estricto en `pyproject.toml` según docs/05. Verificación: `uv run ruff check .` y `uv run mypy .` en verde. `[modelo: sonnet]`
- [x] 2.4 Configurar import-linter con los 3 contratos de docs/05 (core sin frameworks; capas app→adapters→core; independencia de adapters). Verificación: escenarios "Violación de frontera detectada" y "Árbol limpio pasa" (test manual documentado en el PR). `[modelo: sonnet]`
- [x] 2.5 Escribir test de humo `tests/core/test_smoke.py` (importa core, sin red, sin frameworks) y configurar pytest. Verificación: `uv run pytest` en verde; cubre el requirement "Tooling de calidad". `[modelo: sonnet]`

## 3. CI y ciclo local

- [x] 3.1 Crear `.github/workflows/ci.yml`: jobs lint/format/tipos/fronteras/tests con cache de uv, disparado en push y PR a main. Verificación: workflow en verde en GitHub sobre este mismo PR. `[modelo: sonnet]`
- [ ] 3.2 Crear `.pre-commit-config.yaml` (ruff, ruff-format, chequeos de higiene) y documentar `pre-commit install`. Verificación: escenario "Commit con error de lint rechazado localmente". `[modelo: haiku]`

## 4. Cierre

- [ ] 4.1 Actualizar `CLAUDE.md`: sección Comandos con los comandos reales (uv sync, pytest, ruff, mypy, lint-imports) y Mapa del repo sin placeholders. Verificación: comandos copiables funcionan. `[modelo: haiku]`
- [ ] 4.2 Review final del change: consistencia docs↔specs↔código, fronteras verificadas, cero lógica de runtime introducida. Verificación: checklist del reviewer en el PR. `[modelo: opus]`
