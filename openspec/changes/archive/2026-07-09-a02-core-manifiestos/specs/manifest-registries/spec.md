# manifest-registries — Delta Spec (a02-core-manifiestos)

## ADDED Requirements

### Requirement: Carga de manifiestos YAML a Registries en memoria

El sistema SHALL construir Registries en memoria (`AgentRegistry`, `SkillRegistry`, `ToolRegistry` y los Registries de Policy, Routing y Eval) que lean los YAML desde `manifests/{agents,skills,tools,policies,routing,evals}/` y los validen contra sus schemas Pydantic antes de admitirlos. Los Registries MUST vivir en `core/` sin importar frameworks y MUST NOT ejecutar ninguna Tool ni llamar a ningún modelo: solo cargan, validan y catalogan.

#### Scenario: Carga de manifiestos válidos

- **WHEN** se construyen los Registries sobre un directorio `manifests/` con YAML válidos
- **THEN** cada Manifest queda catalogado y consultable por su `id` sin errores

#### Scenario: id duplicado rechazado

- **WHEN** dos manifiestos del mismo tipo declaran el mismo `id`
- **THEN** la construcción del Registry falla señalando el `id` duplicado

#### Scenario: YAML inválido detiene la carga del Registry

- **WHEN** un archivo de `manifests/` no pasa la validación de su schema
- **THEN** la construcción del Registry falla nombrando el archivo y el error de validación

#### Scenario: Registry no ejecuta Tools ni modelos

- **WHEN** se construye cualquier Registry
- **THEN** no se importa ningún adapter (LiteLLM, MCP, LangGraph) y `uv run lint-imports` reporta KEPT

### Requirement: Validación de referencias cruzadas entre Manifests

Los Registries SHALL validar las referencias cruzadas entre Manifests: cada `enabled_skills` de un Agent MUST existir como Skill `active`; cada Tool declarada en `tools` de una Skill MUST existir como Tool `active`; cada `template` de evals MUST existir como Eval Template; cada Policy y Routing referenciados MUST existir. Una referencia a un Manifest inexistente o no `active` MUST hacer fallar la construcción del Registry (referencias colgantes prohibidas).

#### Scenario: Referencias cruzadas completas

- **WHEN** un Agent habilita una Skill `active` que declara Tools `active` y una Eval Template existente
- **THEN** los Registries se construyen y todas las referencias resuelven

#### Scenario: Skill referencia una Tool inexistente

- **WHEN** una Skill declara en `tools` un `id` que ningún Tool Manifest define
- **THEN** la construcción del Registry falla citando la referencia colgante Skill→Tool

#### Scenario: Agent habilita una Skill deprecated

- **WHEN** un Agent lista en `enabled_skills` una Skill cuyo `status` es `deprecated`
- **THEN** la construcción del Registry falla, porque un Agent solo referencia Skills `active`

#### Scenario: Eval template referenciado inexistente

- **WHEN** una Skill referencia en `evals.template` un Eval Template que no existe
- **THEN** la construcción del Registry falla nombrando la referencia colgante

### Requirement: Ciclo de vida draft→validated→active→deprecated y kill switch por status

Cada Manifest SHALL exponer un `status` dentro del ciclo de vida `draft → validated → active → deprecated`. Los Registries MUST hacer invocable solo lo `active`: un Manifest `draft` no se carga al runtime, un `deprecated` permanece catalogado por trazabilidad pero no es invocable. El kill switch MUST ser cambiar `status` (p. ej. a `deprecated`), nunca borrar el Manifest, preservando la historia.

#### Scenario: Manifest active es invocable

- **WHEN** un Manifest tiene `status: active` y pasa validación cruzada
- **THEN** el Registry lo expone como invocable

#### Scenario: Manifest draft no se carga al runtime

- **WHEN** un Manifest tiene `status: draft`
- **THEN** el Registry no lo hace invocable, aunque exista en `manifests/`

#### Scenario: Kill switch por cambio de status

- **WHEN** un Manifest `active` cambia su `status` a `deprecated`
- **THEN** deja de ser invocable pero permanece catalogado y consultable por trazabilidad

#### Scenario: Transición de estado no permitida rechazada

- **WHEN** se intenta marcar como `active` un Manifest que no ha pasado por `validated`
- **THEN** la operación falla, porque `active` requiere validación previa

### Requirement: Consulta de Manifests por status

Los Registries SHALL ofrecer consulta de Manifests filtrada por `status` (p. ej. listar todos los `active`, o todos los `deprecated`) sin exponer los `draft` como invocables. La consulta MUST ser una operación pura de lectura sobre el catálogo en memoria.

#### Scenario: Listar solo Manifests active

- **WHEN** se consulta un Registry por `status: active`
- **THEN** devuelve únicamente los Manifests activos, excluyendo `draft` y `deprecated`

#### Scenario: Consultar un deprecated por trazabilidad

- **WHEN** se consulta un Registry por `status: deprecated`
- **THEN** devuelve los Manifests deprecados sin marcarlos como invocables

#### Scenario: Consulta no muta el catálogo

- **WHEN** se ejecuta cualquier consulta por `status`
- **THEN** el catálogo en memoria permanece sin cambios (operación pura de lectura)

#### Scenario: Consulta por status inexistente

- **WHEN** se consulta por un `status` sin Manifests
- **THEN** devuelve una colección vacía sin error

### Requirement: Manifiestos de fábrica de ejemplo cargables

El repo SHALL incluir un conjunto de manifiestos de fábrica de ejemplo en `manifests/`: el Agent `default_chat` (sin nombre comercial, general, `can_execute_tools_directly: false`, `tool_access_policy.mode: deny_by_default`), 1 Skill de ejemplo, 1 Tool de ejemplo que referencia un MCP server de ejemplo, Policies genéricas (deny-by-default + `allow` de lecturas de ejemplo), 1 Routing default y 1 Eval Template placeholder. Todos MUST cargar y validar en los Registries con sus referencias cruzadas resueltas.

#### Scenario: Los manifiestos de fábrica cargan y validan

- **WHEN** se construyen los Registries sobre los manifiestos de fábrica de ejemplo
- **THEN** todos validan, sus referencias cruzadas resuelven y el conjunto queda `active` e invocable

#### Scenario: default_chat de ejemplo respeta la regla de oro

- **WHEN** se carga el Agent `default_chat` de fábrica
- **THEN** el Registry confirma `can_execute_tools_directly: false` y `tool_access_policy.mode: deny_by_default`

#### Scenario: La Policy de ejemplo es deny-by-default

- **WHEN** se carga la Policy genérica de ejemplo, que solo declara `allow` para lecturas
- **THEN** toda operación de escritura queda implícitamente en `deny` (la decisión del Policy Gate en runtime, `a03`, será deny)

#### Scenario: La Tool de ejemplo referencia un MCP Server

- **WHEN** se carga la Tool de ejemplo de fábrica
- **THEN** el Registry resuelve su referencia a un MCP server + `tool_name` con clasificación de lectura y riesgo `low`
