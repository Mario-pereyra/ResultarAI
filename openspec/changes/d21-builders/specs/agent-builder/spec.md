# agent-builder — Delta Spec (d21-builders)

> Vista de diseño: `design/VISTAS/09-builders.md` Vista 41 (`41-builder-agentes.html`). Funcionalidad: `design/FUNCIONALIDADES.md` §13. Alcance: solo Admin.

## ADDED Requirements

### Requirement: Wizard de creación/edición de versión de agente, solo Admin

El sistema SHALL exponer un wizard de 4 pasos (Identidad → Prompt → Tools y políticas → Evals y publicación) para crear o editar una versión de `AgentManifest`, accesible únicamente para el rol Admin. Técnico y Funcional NUNCA SHALL ver la entrada de navegación ni la ruta del builder; un acceso directo de esos roles SHALL comportarse como si la ruta no existiera (sin revelar "sin permiso"). El sistema SHALL permitir a lo sumo **un borrador por agente** a la vez: editar un agente con una versión activa crea un borrador nuevo, nunca muta la versión activa.

#### Scenario: Admin abre el builder para un agente nuevo

- **WHEN** un Admin crea un agente nuevo
- **THEN** el sistema abre el wizard vacío con el Paso 1 activo, los pasos 2-4 en estado `pendiente` y ningún `AgentManifest` activo asociado todavía

#### Scenario: Editar un agente con versión activa crea un borrador nuevo

- **WHEN** un Admin abre un agente que ya tiene una versión `active` y modifica cualquier campo
- **THEN** el sistema crea un borrador nuevo (`draft`) sin alterar la versión activa; el borrador queda asociado a esa versión como base

#### Scenario: Técnico o Funcional no acceden al builder

- **WHEN** un usuario con rol Técnico o Funcional intenta acceder directamente a la ruta del Agent Builder
- **THEN** el sistema lo redirige a su home sin mostrar la ruta ni un mensaje de "sin permiso"

#### Scenario: Un segundo borrador del mismo agente es rechazado

- **WHEN** ya existe un `draft` para un agente y el Admin intenta crear uno nuevo para el mismo agente
- **THEN** el sistema rechaza la creación y abre el `draft` existente en su lugar

### Requirement: El header estático cache-safe lo antepone la plataforma

El prefijo estático cache-safe del prompt (identidad del agente, reglas de citas, política de abstención, declaración del marcador de escalación `<<<NEEDS_PRO>>>`) SHALL ser generado y antepuesto por la plataforma, no por el Admin. El builder MUST mostrarlo como bloque de solo lectura y MUST NOT incluirlo en el payload editable que el Admin envía: ningún endpoint del builder SHALL aceptar una modificación del prefijo, ni siquiera mediante una llamada directa a la API que salte la UI. Las únicas secciones editables son las posteriores al prefijo (tono y estilo, reglas de dominio, formato de respuesta).

#### Scenario: El builder muestra el prefijo como bloque bloqueado

- **WHEN** un Admin abre el Paso 2 (Prompt) de una versión de agente
- **THEN** el sistema muestra el prefijo estático en un bloque de solo lectura, separado de las secciones editables, sin controles de edición

#### Scenario: Un intento de modificar el prefijo vía API es rechazado

- **WHEN** una llamada a la API del builder incluye un payload que intenta alterar el contenido del prefijo estático
- **THEN** el sistema rechaza la llamada porque el prefijo no forma parte del contrato de campos editables, independientemente de si la UI lo habría bloqueado

#### Scenario: Las secciones editables no alteran el prefijo

- **WHEN** un Admin guarda cambios en "Reglas de dominio" o "Formato de respuesta"
- **THEN** el prompt resultante conserva el prefijo estático sin cambios, con las secciones editables ubicadas después de él

### Requirement: El toolset se elige exclusivamente entre Tools activas del Tool Registry

El Paso 3 del builder SHALL listar como seleccionables únicamente las Tools con `status: active` en el Tool Registry (`c09-mcp-tools`). Tools en estado `draft` o `deprecated` MUST NOT aparecer en la lista de selección. La clasificación lectura/escritura/riesgo y el requisito de HITL de cada Tool SHALL mostrarse como datos de solo lectura provenientes del `ToolManifest`, sin control de edición en el builder (cambiarla es un PR sobre el manifiesto, fuera del builder).

#### Scenario: Solo tools activas aparecen en la allowlist

- **WHEN** un Admin abre el Paso 3 y el Tool Registry contiene Tools en estado `active`, `draft` y `deprecated`
- **THEN** solo las Tools `active` aparecen como seleccionables; las `draft` y `deprecated` no se listan

#### Scenario: La clasificación de una tool no es editable desde el builder

- **WHEN** un Admin intenta cambiar la clasificación de riesgo o el requisito de HITL de una Tool de escritura seleccionada
- **THEN** el sistema no ofrece ningún control para ese cambio; el campo se muestra de solo lectura con su valor tomado del `ToolManifest`

### Requirement: Perfil de modelo y escalación configurables por versión

El Paso 3 del builder SHALL permitir configurar, por versión del agente, el perfil de modelo primario (de los perfiles definidos en `b05-gateway-modelos`) y si la escalación manual a un perfil Pro está habilitada. Al guardar, estos valores SHALL persistirse en los campos correspondientes del `AgentManifest` que consume `b05` para la cascada de fallback y la detección del marcador `<<<NEEDS_PRO>>>`.

#### Scenario: Habilitar escalación guarda el campo en el Agent Manifest

- **WHEN** un Admin marca "Permitir escalación manual a Pro" y selecciona un perfil Pro
- **THEN** el borrador guarda `escalation.enabled = true` con el perfil Pro referenciado, consumible por `b05` en runtime

#### Scenario: Deshabilitar escalación detiene la evaluación del marcador

- **WHEN** un Admin desmarca "Permitir escalación manual a Pro"
- **THEN** el borrador guarda `escalation.enabled = false`; una vez activada esa versión, `b05` no evalúa el marcador `<<<NEEDS_PRO>>>` para ese agente

### Requirement: La versión hornea toolset y skillset — fijos, nunca a mitad de sesión

Al activar una versión de agente, el sistema SHALL congelar un snapshot de su toolset (Paso 3) y de su skillset (`enabled_skills`) como parte inmutable de esa versión. Una sesión que arrancó bajo una versión SHALL conservar el toolset y skillset de esa versión durante toda su vida, incluso si una versión posterior se activa mientras la sesión sigue en curso (mismo principio de stickiness que las sesiones de prompt en `d20`). Habilitar una Tool o Skill nueva para un agente exige una versión nueva, nunca una recarga en caliente.

#### Scenario: Sesión en curso conserva el toolset de su versión

- **WHEN** una sesión arrancó bajo `docagent@12` y el Admin activa `docagent@13` con un toolset distinto mientras la sesión sigue abierta
- **THEN** la sesión en curso sigue operando con el toolset y skillset horneados de `docagent@12` hasta que termina; las sesiones nuevas usan `@13`

#### Scenario: Desmarcar una tool usada por una skill horneada advierte antes de guardar

- **WHEN** un Admin desmarca en el Paso 3 una Tool que una Skill incluida en `enabled_skills` requiere
- **THEN** el sistema muestra una advertencia listando las Skills afectadas antes de permitir continuar, sin bloquear el guardado del borrador

### Requirement: Identificador inmutable tras la creación del agente

El `id` (slug) de un agente SHALL generarse a partir del nombre al crear la primera versión y MUST volverse inmutable a partir de ese momento, porque es la clave de sus versiones, de su prompt en el Registro de Prompts y de sus evals. Ningún paso del wizard SHALL ofrecer edición del `id` en versiones posteriores a la primera.

#### Scenario: El identificador no es editable después de crear el agente

- **WHEN** un Admin edita una versión posterior a la primera de un agente existente
- **THEN** el campo `id`/slug se muestra de solo lectura y ninguna acción del wizard permite cambiarlo

### Requirement: El Paso 1 consume la matriz de visibilidad agente×rol de d20

El Paso 1 (Identidad) SHALL permitir al Admin editar, para el agente en edición, su entrada en la matriz de visibilidad agente×rol, usando el contrato de escritura ya definido por `d20-gobernanza-plataforma` — el builder no redefine el modelo de la matriz, solo la expone en el flujo de creación/edición del agente. El sistema SHALL aplicar la regla encadenada: si "Puede iniciar sesiones" está marcado para un rol, "Aparece en catálogo" MUST estar marcado también para ese rol; desmarcar "Aparece en catálogo" SHALL desmarcar y deshabilitar automáticamente "Puede iniciar sesiones" para esa fila.

#### Scenario: Desmarcar catálogo desmarca y bloquea iniciar sesiones

- **WHEN** un Admin desmarca "Aparece en catálogo" para el rol Técnico
- **THEN** el sistema desmarca y deshabilita "Puede iniciar sesiones" para Técnico en la misma acción

#### Scenario: La fila Admin siempre está marcada y bloqueada

- **WHEN** un Admin abre la matriz de visibilidad del Paso 1
- **THEN** la fila Admin aparece con ambas columnas marcadas y deshabilitadas, con la explicación de que el Admin siempre ve todo

### Requirement: Activar una versión reutiliza el gate pluggable de publicación de d20

La acción "Activar versión" SHALL invocar el gate de publicación pluggable ya especificado en `d20-gobernanza-plataforma` (modo placeholder mientras `e25-evals-gates` no esté archivado; modo enforcing cuando lo esté) sobre la versión de prompt vinculada, sin redefinir sus reglas. El sistema SHALL exigir además que los pasos 1-3 del wizard estén válidos antes de habilitar "Activar versión". En modo placeholder, la ausencia de evals MUST mostrarse como advertencia visible y accionable y NUNCA SHALL bloquear la activación.

#### Scenario: Activar sin evals en modo placeholder muestra advertencia y permite continuar

- **WHEN** un Admin con los pasos 1-3 válidos intenta activar una versión y no existe corrida de evals asociada (`e25` no archivado)
- **THEN** el sistema muestra una advertencia visible "se activa sin evaluación" y permite completar la activación

#### Scenario: Activar con pasos inválidos queda bloqueado con motivo

- **WHEN** un Admin intenta activar una versión con el Paso 3 en estado `con errores`
- **THEN** el botón "Activar versión" permanece deshabilitado y el sistema muestra el motivo junto al botón, no solo en un tooltip

### Requirement: Un agente publicado aparece en el catálogo tras pasar el gate

Cuando una versión de agente se activa exitosamente (gate pasado, en modo placeholder o enforcing), el `AgentManifest` SHALL pasar a `status: active`, la versión previa SHALL pasar a `deprecated`, y el agente SHALL aparecer en el catálogo (`d15-catalogo-agentes`) exactamente según lo que su entrada en la matriz de visibilidad agente×rol permita para cada rol.

#### Scenario: Agente nuevo aparece en el catálogo tras activar su primera versión

- **WHEN** un Admin activa la primera versión de un agente nuevo con visibilidad marcada para Técnico y Funcional
- **THEN** el agente aparece en el catálogo de Técnico y de Funcional a partir de esa activación, sin requerir despliegue

#### Scenario: La versión previa queda deprecated tras activar una nueva

- **WHEN** un Admin activa `docagent@13` teniendo `docagent@12` como versión activa
- **THEN** `docagent@12` pasa a `status: deprecated` (visible en el registro por trazabilidad, no invocable) y `docagent@13` pasa a `active`

### Requirement: Toda acción del builder queda auditada

Cada acción sobre una versión de agente (`draft-create`, `draft-edit`, `activate`) SHALL generar un `AuditEvent` append-only con usuario, fecha-hora, agente, versión y — en `activate` — el resultado del gate (placeholder/enforcing, advertencia u OK). La auditoría del builder se suma a la que ya genera `d20` para la versión de prompt vinculada, sin duplicar el evento de publicación del prompt.

#### Scenario: Activar una versión genera un evento con el resultado del gate

- **WHEN** un Admin activa `docagent@13` en modo placeholder
- **THEN** el `AuditEvent` de `activate` registra usuario, fecha-hora, `docagent@13` y que el gate operó en modo placeholder con advertencia
