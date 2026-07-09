# Tasks — a02-core-manifiestos

## 1. Schemas Pydantic de los 6 Manifests (`core/manifests/`)

- [x] 1.1 Crear el schema base de Manifest en `core/manifests/` (Pydantic v2 `ConfigDict(strict=True, extra="forbid")`, campos `id`/`status`/`version` con validación semver, enum de `status` del ciclo `draft→validated→active→deprecated`). Verificación: `tests/core/test_manifest_base.py` prueba strict mode (campo desconocido rechazado), semver inválido rechazado y status fuera del enum rechazado; `uv run lint-imports` KEPT. `[modelo: opus]`
- [x] 1.2 Definir `AgentManifest` con sus campos obligatorios y los `model_validator` de la regla de oro (rechaza `can_execute_tools_directly: true` y `tool_access_policy.mode` ≠ `deny_by_default`). Verificación: `tests/core/test_agent_manifest.py` acepta `default_chat` conforme y rechaza acceso directo a Tools y modo no deny-by-default. `[modelo: opus]`
- [x] 1.3 Definir `SkillManifest` como envoltorio de gobernanza (referencia al paquete Agent Skill por id/versión, `tools` obligatorias no vacías, invariante plan-then-execute para Skills que tocan el ERP; sin embeber contenido del `SKILL.md`). Verificación: `tests/core/test_skill_manifest.py` acepta la Skill de ejemplo, rechaza `tools` vacío, rechaza campos que dupliquen el `SKILL.md` (strict) y rechaza ERP sin graph plan-then-execute. `[modelo: opus]`
- [x] 1.4 Definir `ToolManifest` (referencia a MCP server + `tool_name`, `operation_type` y `risk.level` fijos por `version`, `security.allow_sql_freeform` prohibido en `true`). Verificación: `tests/core/test_tool_manifest.py` acepta la Tool de ejemplo de lectura, rechaza SQL libre y rechaza binding MCP o clasificación de riesgo ausentes. `[modelo: opus]`
- [x] 1.5 Definir `PolicyManifest` (efectos `allow`/`deny`/`escalate_hitl`, deny-by-default implícito), `RoutingManifest` (acciones `answer_directly`/`activate_skill`/`delegate`) y `EvalTemplateManifest` (Eval Placeholder con `status: placeholder`, `dataset: null`). Verificación: `tests/core/test_policy_routing_eval.py` acepta los ejemplos válidos y rechaza `effect`/`action` fuera del conjunto permitido. `[modelo: opus]`
- [x] 1.6 Añadir el campo `retrieval` opcional (sub-schema strict) a los Manifests que aplican, sin adapter ni comportamiento (puerta abierta a RAG). Verificación: `tests/core/test_retrieval_optional.py` valida Manifest sin `retrieval`, con `retrieval` declarado (metadato inerte) y rechaza claves desconocidas dentro del bloque. `[modelo: opus]`

## 2. Registries en memoria (`core/manifests/`)

- [x] 2.1 Implementar el cargador YAML→schema y la construcción de los Registries (`AgentRegistry`, `SkillRegistry`, `ToolRegistry` y los de Policy/Routing/Eval) desde `manifests/`, con detección de `id` duplicado; sin importar adapters. Verificación: `tests/core/test_registry_loading.py` carga manifiestos válidos, falla ante `id` duplicado y ante YAML inválido; `uv run lint-imports` KEPT. `[modelo: sonnet]`
- [x] 2.2 Implementar la validación de referencias cruzadas (Agent→Skill `active`, Skill→Tool `active`, `*`→Eval/Policy/Routing existentes; referencias colgantes prohibidas). Verificación: `tests/core/test_cross_references.py` resuelve un conjunto completo y falla ante Tool inexistente, Skill `deprecated` habilitada y Eval template inexistente. `[modelo: sonnet]`
- [x] 2.3 Implementar el ciclo de vida y el kill switch por `status` (solo `active` invocable; `draft` no se carga; `deprecated` catalogado no invocable; `active` requiere paso previo por `validated`). Verificación: `tests/core/test_lifecycle.py` cubre los 4 escenarios del requirement de ciclo de vida. `[modelo: sonnet]`
- [x] 2.4 Implementar la consulta pura por `status` en los Registries (lista `active`, `deprecated`, colección vacía sin error, sin mutar el catálogo). Verificación: `tests/core/test_query_by_status.py` cubre los 4 escenarios del requirement de consulta. `[modelo: sonnet]`

## 3. Manifiestos de fábrica de ejemplo (`manifests/`)

- [x] 3.1 Escribir los YAML de fábrica del Agent `default_chat` (general, sin nombre comercial, `can_execute_tools_directly: false`, `deny_by_default`), 1 Skill de ejemplo y 1 Tool de ejemplo que referencia un MCP server de ejemplo. Verificación: el CLI de validación (tarea 4.1) los reporta válidos con exit code 0. `[modelo: haiku]`
- [x] 3.2 Escribir los YAML de fábrica de las Policies genéricas (deny-by-default + `allow` de lecturas de ejemplo), el Routing default y el Eval Template placeholder. Verificación: el CLI de validación los reporta válidos y sus referencias cruzadas resuelven. `[modelo: haiku]`
- [x] 3.3 Escribir el test de contrato que carga los manifiestos de fábrica en los Registries y verifica referencias cruzadas, regla de oro de `default_chat` y clasificación de la Tool de ejemplo. Verificación: `tests/contracts/test_factory_manifests.py` en verde (cubre el requirement "Manifiestos de fábrica de ejemplo cargables"). `[modelo: sonnet]`

## 4. Validación por CLI, arranque fail-fast y CI

- [x] 4.1 Implementar la función única de validación en `core/` (schemas + referencias cruzadas) y su comando CLI vía uv (sin red). Verificación: `tests/contracts/test_validate_cli.py` prueba exit 0 con manifiestos válidos, exit ≠0 con Manifest inválido y con referencia colgante. `[modelo: sonnet]`
- [x] 4.2 Implementar la validación fail-fast al arranque en `app/` reutilizando la función de 4.1 (aborta si algún Manifest falla; `draft` no impide arrancar). Verificación: `tests/contracts/test_startup_failfast.py` prueba arranque exitoso, abortos por schema y por referencia colgante. `[modelo: sonnet]`
- [x] 4.3 Añadir a `.github/workflows/ci.yml` un job que valide los manifiestos en cada push/PR a `main` reutilizando el mismo CLI de 4.1. Verificación: el job pasa en verde sobre este PR y falla al introducir un Manifest inválido (test manual documentado en el PR). `[modelo: sonnet]`

## 5. Cierre

- [ ] 5.1 Review final del change: consistencia specs↔schemas↔manifiestos de fábrica, invariantes duras codificadas en el schema, `core/manifests/` sin frameworks (import-linter KEPT), cero ejecución de Tools/modelos introducida. Verificación: checklist del reviewer en el PR y `openspec validate "a02-core-manifiestos"` en verde. `[modelo: opus]`
