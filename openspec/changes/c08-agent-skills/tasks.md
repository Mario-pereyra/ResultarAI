# Tasks — c08-agent-skills

## 1. Modelo, validación e intersección (core, compliance con la spec)

- [ ] 1.1 Modelo `SkillPackage` (Pydantic) en `resultarai/core/skills/`: frontmatter `name`, `description`, opcionales `license`, `compatibility`, `metadata`, `allowed-tools`; cuerpo Markdown; referencias a archivos de apoyo. Verificación: test `tests/core/test_skill_package.py` construye un paquete válido y falla ante frontmatter incompleto. `[modelo: opus]`
- [ ] 1.2 Reglas de validación conformes a la spec Agent Skills en `core/skills/`: formato de `name` (1–64, minúsculas/dígitos/guiones, sin guion inicial/final ni dobles), `name` = directorio = referencia del Skill Manifest, y tope configurable de metadata de descubrimiento (`name`+`description`). Verificación: test cubre los 4 rechazos de la spec (campo faltante, formato inválido, nombre inconsistente, metadata excedida) con error accionable. `[modelo: opus]`
- [ ] 1.3 Función pura `resolve_executable_toolset(package_allowed_tools, manifest_tools) -> frozenset` en `core/skills/`. Verificación: test de tabla `tests/core/test_toolset_intersection.py` cubre tool en ambos, solo en paquete y solo en manifiesto; el resultado es la intersección. `[modelo: opus]`

## 2. Port de carga y adapter de filesystem (loader)

- [ ] 2.1 Definir `SkillPackagePort` (`typing.Protocol`) en `resultarai/core/ports/` con `discover`, `read_metadata`, `read_body`, `read_resource`. Verificación: `uv run lint-imports` mantiene `core/` sin I/O ni frameworks y `tests/core/test_smoke.py` importa el port sin efectos. `[modelo: sonnet]`
- [ ] 2.2 Adapter `resultarai/adapters/skills_fs/`: recorre `manifests/skills/packages/`, separa frontmatter YAML del cuerpo, lee archivos de apoyo bajo demanda. Verificación: test de contrato `tests/contracts/test_skills_fs.py` sobre un paquete fixture devuelve metadata, cuerpo y recurso por separado. `[modelo: sonnet]`
- [ ] 2.3 Descubrimiento fail-fast: para cada Skill Manifest `active`, cargar y validar su paquete e integrarlo al `SkillRegistry` (`a02`); manifiesto sin paquete válido no queda `active`. Verificación: test donde un manifiesto referencia un paquete inexistente hace fallar la carga (arranque/CI en rojo) y la skill no queda disponible. `[modelo: sonnet]`

## 3. Divulgación progresiva (orquestación)

- [ ] 3.1 Nivel 1: inyectar los metadatos (`name`+`description`) de las skills `active` del agente en el contexto de sistema al construirlo, sin el cuerpo. Verificación: test que el contexto contiene los metadatos y NO el cuerpo de ningún `SKILL.md`. `[modelo: opus]`
- [ ] 3.2 Niveles 2–3: cargar el cuerpo al activar la skill (Skill Router `b06`) vía `read_body` y los archivos de apoyo bajo demanda vía `read_resource`; nunca precargados. Verificación: test que el cuerpo se carga solo al activar y un recurso solo al referenciarse. `[modelo: opus]`
- [ ] 3.3 Skillset/toolset fijo por versión de agente: resolver desde `enabled_skills` + Skill Manifest `active` al cargar e inmutable en la sesión. Verificación: test que una skill activada después de iniciar una sesión no aparece en esa sesión en curso. `[modelo: sonnet]`

## 4. Skill de ejemplo de fábrica

- [ ] 4.1 Crear el paquete `manifests/skills/packages/report-formatting/SKILL.md` (frontmatter `name`+`description`, cuerpo de redacción/formato de informes) + un archivo de apoyo en `references/` (plantilla de estructura), con `allowed-tools` referenciando la tool de ejemplo de `c09`. Verificación: el paquete pasa la validación de la capability (escenario "El paquete de ejemplo valida"). `[modelo: haiku]`
- [ ] 4.2 Crear el Skill Manifest de ejemplo en `manifests/skills/` que referencia el paquete y declara `tools` (intersección esperada con el id de la tool de ejemplo). Verificación: el manifiesto valida contra el schema de `a02` y su referencia cruzada al paquete resuelve. `[modelo: haiku]`

## 5. Integración y cierre

- [ ] 5.1 Test de integración estructural: el Skill Router activa la skill de ejemplo → cuerpo cargado por divulgación progresiva, toolset ejecutable resuelto (id de tool stub de `c09`), y la decisión del Policy Gate queda en el Audit Log. Verificación: `uv run pytest` en verde cubriendo el escenario "El Default Chat resuelve una consulta con la skill de ejemplo". `[modelo: sonnet]`
- [ ] 5.2 Review final del change: compliance con la spec Agent Skills (frontmatter, disclosure, `allowed-tools`), regla dura 3 intacta (tools solo vía skill, cada ejecución por el Policy Gate), `core/` sin I/O ni frameworks, cero ejecución real de tools. Verificación: checklist del reviewer en el PR. `[modelo: opus]`
