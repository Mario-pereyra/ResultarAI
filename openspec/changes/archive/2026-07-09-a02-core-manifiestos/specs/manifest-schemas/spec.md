# manifest-schemas — Delta Spec (a02-core-manifiestos)

## ADDED Requirements

### Requirement: Los 6 Manifests como schemas Pydantic v2 strict

El sistema SHALL definir en `core/manifests/` un schema Pydantic v2 en modo estricto por cada uno de los 6 Manifests: `AgentManifest`, `SkillManifest`, `ToolManifest`, `PolicyManifest`, `RoutingManifest` y `EvalTemplateManifest`. Cada Manifest MUST declarar `id` (identificador en inglés), `status` y una `version` con formato semver; el modo estricto MUST rechazar campos desconocidos y coerciones implícitas de tipo. Los schemas SHALL depender solo de stdlib + Pydantic (sin frameworks), conforme a la regla de dependencia de `core/`.

#### Scenario: Manifest válido se parsea

- **WHEN** se carga un YAML con `id`, `status` y `version` semver bien formados contra su schema
- **THEN** Pydantic construye la instancia sin errores y expone los campos tipados

#### Scenario: Campo desconocido rechazado por strict mode

- **WHEN** un YAML de Manifest incluye una clave no declarada en el schema
- **THEN** la validación falla con un error que nombra la clave desconocida y el Manifest afectado

#### Scenario: Versión no-semver rechazada

- **WHEN** un Manifest declara `version` que no cumple el formato semver (p. ej. `v1` o `1.2`)
- **THEN** la validación falla señalando el campo `version` inválido

#### Scenario: core/manifests no importa frameworks

- **WHEN** se ejecuta `uv run lint-imports` tras añadir los schemas
- **THEN** el contrato "core sin frameworks" reporta KEPT y el exit code es 0

### Requirement: Invariantes del Agent Manifest garantizan la regla de oro

El `AgentManifest` SHALL declarar los campos obligatorios de `docs/04-manifiestos.md` (`id`, `name`, `type`, `status`, `runtime`, `capabilities`, `enabled_skills`, `tool_access_policy`, `observability`, `evals`). El schema MUST rechazar por invariante todo Agent cuyo `capabilities.can_execute_tools_directly` sea `true` o cuyo `tool_access_policy.mode` no sea `deny_by_default`, de modo que el Default Chat nunca pueda ejecutar Tools directamente (regla dura 3).

#### Scenario: Default Chat conforme se acepta

- **WHEN** se valida el Agent Manifest `default_chat` con `can_execute_tools_directly: false` y `tool_access_policy.mode: deny_by_default`
- **THEN** el schema lo acepta como Manifest válido

#### Scenario: Agente con acceso directo a Tools rechazado

- **WHEN** un Agent Manifest declara `capabilities.can_execute_tools_directly: true`
- **THEN** la validación falla citando la invariante de la regla de oro (Tools solo vía Skills)

#### Scenario: tool_access_policy sin deny-by-default rechazado

- **WHEN** un Agent Manifest declara `tool_access_policy.mode` distinto de `deny_by_default`
- **THEN** la validación falla señalando el campo `tool_access_policy.mode`

#### Scenario: Falta un campo obligatorio

- **WHEN** un Agent Manifest omite `enabled_skills` o `evals`
- **THEN** la validación falla nombrando el campo obligatorio ausente

### Requirement: Skill Manifest como envoltorio de gobernanza de un paquete Agent Skill

El `SkillManifest` SHALL ser el envoltorio de gobernanza de un paquete conforme a la spec oficial Agent Skills (carpeta con `SKILL.md` + frontmatter `name`/`description`, progressive disclosure): MUST referenciar el paquete por identificador y `version`, y declarar `status`, `execution`, `tools` permitidas, `output_policy` y `evals`. El schema MUST NOT duplicar el contenido de la Skill (instrucciones ni ejemplos del `SKILL.md`); solo aporta la capa de gobernanza (id, versión, policies, Tools permitidas, status).

#### Scenario: Skill Manifest referencia un paquete Agent Skill

- **WHEN** se valida un Skill Manifest que apunta a un paquete Agent Skill por identificador y declara sus `tools` permitidas
- **THEN** el schema lo acepta sin exigir el cuerpo del `SKILL.md` dentro del YAML

#### Scenario: Skill declara sus Tools explícitamente

- **WHEN** un Skill Manifest omite el campo `tools` o lo deja vacío sin declararlo
- **THEN** la validación falla, porque cada Skill MUST declarar explícitamente las Tools que puede usar

#### Scenario: Intento de embeber contenido de la Skill rechazado

- **WHEN** un Skill Manifest incluye campos que dupliquen instrucciones o ejemplos del `SKILL.md`
- **THEN** la validación falla por strict mode (campos no declarados en el envoltorio de gobernanza)

#### Scenario: Skill que toca el ERP exige plan-then-execute

- **WHEN** un Skill Manifest declara `execution.mode: read_only` contra la ERP Safe Query API pero `execution.graph` no es un Graph Template plan-then-execute
- **THEN** la validación falla citando la regla dura 7 (plan validado antes de ejecutar)

### Requirement: Tool Manifest referencia un MCP Server con clasificación fija por versión

El `ToolManifest` SHALL referenciar un MCP server (spec oficial MCP) por su identificador de server + `tool_name`, y declarar la clasificación `operation_type` (lectura/escritura), el `risk.level`, `permissions`, `security` y `audit`. La clasificación lectura/escritura y el nivel de riesgo MUST quedar fijos por `version` del Manifest: cambiarlos exige una nueva `version` (un PR), nunca una mutación en runtime. El schema MUST rechazar SQL libre (`security.allow_sql_freeform: true`) contra el ERP.

#### Scenario: Tool Manifest de lectura vía MCP Server se acepta

- **WHEN** se valida un Tool Manifest que referencia un MCP server + `tool_name` con `operation_type: read` y `risk.level: low`
- **THEN** el schema lo acepta con la clasificación registrada para esa `version`

#### Scenario: SQL libre contra el ERP rechazado

- **WHEN** un Tool Manifest declara `security.allow_sql_freeform: true`
- **THEN** la validación falla citando la regla dura 5 (nunca SQL libre contra el ERP)

#### Scenario: Falta la referencia al MCP Server

- **WHEN** un Tool Manifest de tipo MCP omite el identificador del server o el `tool_name`
- **THEN** la validación falla nombrando el binding MCP ausente

#### Scenario: Clasificación de riesgo obligatoria

- **WHEN** un Tool Manifest omite `risk.level` u `operation_type`
- **THEN** la validación falla, porque la clasificación lectura/escritura y riesgo es obligatoria y fija por versión

### Requirement: Policy, Routing y Eval Template Manifests

El sistema SHALL definir los schemas de `PolicyManifest` (reglas declarativas con efectos `allow`/`deny`/`escalate_hitl` y semántica deny-by-default: lo no permitido explícitamente queda bloqueado), `RoutingManifest` (reglas del Skill Router: `answer_directly`, `activate_skill`, `delegate`) y `EvalTemplateManifest` (Eval Placeholder obligatorio con `target_kind`, `metrics_planned` y `dataset: null`). El `EvalTemplateManifest` MUST admitir `status: placeholder` y `dataset` vacío, conforme al principio 16 del blueprint (evals preparadas, no definidas).

#### Scenario: Policy Manifest deny-by-default declara su efecto

- **WHEN** se valida un Policy Manifest cuyas reglas solo declaran `allow` para lecturas y ningún `allow` para escrituras
- **THEN** el schema lo acepta y toda operación no cubierta queda implícitamente en `deny` (la decisión del Policy Gate en runtime, `a03`, será deny)

#### Scenario: Efecto de Policy fuera del conjunto permitido rechazado

- **WHEN** una regla de Policy declara un `effect` distinto de `allow`, `deny` o `escalate_hitl`
- **THEN** la validación falla señalando el `effect` inválido

#### Scenario: Routing con acción desconocida rechazado

- **WHEN** una regla de Routing declara una `action` que no es `answer_directly`, `activate_skill` ni `delegate`
- **THEN** la validación falla señalando la acción inválida

#### Scenario: Eval Template placeholder sin dataset se acepta

- **WHEN** se valida un Eval Template Manifest con `status: placeholder` y `dataset: null`
- **THEN** el schema lo acepta como Eval Placeholder válido sin exigir casos reales

### Requirement: Puerta abierta a RAG sin implementación

Los schemas de Manifest que puedan consumir recuperación de conocimiento SHALL exponer un campo `retrieval` opcional que, cuando esté ausente, no active ningún comportamiento. El campo MUST ser declarativo y sin adapter asociado en este change: no habilita RAG, solo reserva el contrato para cuando exista `RetrievalPort` (diferido a `a03` y su implementación real a la Etapa P).

#### Scenario: Manifest sin campo retrieval es válido

- **WHEN** se valida un Skill Manifest que omite por completo el campo `retrieval`
- **THEN** el schema lo acepta y ningún comportamiento de recuperación queda activo

#### Scenario: Campo retrieval declarado no ejecuta nada

- **WHEN** un Skill Manifest declara un bloque `retrieval` opcional
- **THEN** la validación lo acepta como metadato declarativo y no se invoca ningún adapter de recuperación

#### Scenario: retrieval mal formado rechazado

- **WHEN** el bloque `retrieval` incluye claves no declaradas en su sub-schema
- **THEN** la validación falla por strict mode señalando la clave desconocida

#### Scenario: Ausencia de adapter de retrieval no rompe la carga

- **WHEN** se cargan todos los manifiestos de fábrica sin ningún adapter de recuperación configurado
- **THEN** la carga termina sin errores y ningún Manifest exige un `RetrievalPort`
