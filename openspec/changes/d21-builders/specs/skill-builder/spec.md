# skill-builder — Delta Spec (d21-builders)

> Vista de diseño: `design/VISTAS/09-builders.md` Vista 42 (`42-builder-skills.html`). Funcionalidad: `design/FUNCIONALIDADES.md` §13. Alcance: edición solo Admin; Registro de skills consultable por Técnico; propuestas guiadas para Técnico; sandbox para todos los roles.

## ADDED Requirements

### Requirement: Wizard de creación/edición de paquetes de Skill conformes a la spec Agent Skills

El sistema SHALL exponer un editor (solo Admin) para crear o editar una Skill como **paquete conforme a la spec oficial Agent Skills**: carpeta con `SKILL.md` (frontmatter YAML `name`/`description` + cuerpo markdown) y archivos de apoyo opcionales (`scripts/`, `references/`, `assets/`), junto con su `SkillManifest` de gobernanza (`a02-core-manifiestos`: `status`, `execution`, `tools` permitidas, `output_policy`, `evals`). El resultado de publicar MUST ser un paquete que pasa la validación de `c08-agent-skills` sin cambios en `c08`. El sistema SHALL permitir a lo sumo un borrador por Skill; publicar congela la versión (inmutable) y editar una versión publicada crea el borrador `@n+1`.

#### Scenario: Publicar produce un paquete válido para el loader de c08

- **WHEN** un Admin publica una Skill creada en el builder
- **THEN** el sistema materializa el paquete (`SKILL.md` + archivos de apoyo) y su `SkillManifest`, y la validación de paquetes de `c08` lo acepta sin errores

#### Scenario: Editar una skill publicada crea un borrador nuevo

- **WHEN** un Admin edita el contenido de una Skill con versión publicada `@1`
- **THEN** el sistema crea el borrador `@2` sin alterar `@1`; la versión publicada permanece inmutable (contenido y casos de eval congelados)

#### Scenario: El slug de la skill es inmutable tras la primera publicación

- **WHEN** un Admin intenta renombrar el slug de una Skill ya publicada
- **THEN** el sistema no ofrece esa edición; solo la descripción y el owner son editables sin crear versión nueva (metadatos, no contenido)

### Requirement: Validación en vivo del frontmatter

El editor SHALL validar el frontmatter del `SKILL.md` en vivo (al editar, antes de guardar) contra las reglas de la spec Agent Skills que aplica `c08`: `name` y `description` obligatorios; `name` de 1–64 caracteres, solo minúsculas, dígitos y guiones, sin guion inicial/final ni guiones consecutivos; `name` idéntico al slug del paquete. Un paquete con frontmatter inválido MUST NOT ser publicable: el botón "Publicar skill" queda deshabilitado con el motivo visible junto al botón (no solo tooltip).

#### Scenario: Skill con frontmatter inválido no es publicable

- **WHEN** el frontmatter del borrador carece de `description` o su `name` viola el formato de la spec (mayúsculas, guiones consecutivos, guion inicial/final)
- **THEN** el editor muestra el error en vivo señalando la regla violada y "Publicar skill" permanece deshabilitado con el motivo visible; no existe ruta de publicación

#### Scenario: Corregir el frontmatter rehabilita el camino de publicación

- **WHEN** el Admin corrige el frontmatter y el borrador cumple todas las reglas de la spec (y el gate de casos está en verde)
- **THEN** la validación en vivo pasa y "Publicar skill" se habilita

### Requirement: Publicar exige al menos 3 casos de eval declarados

La publicación de una Skill SHALL exigir que el borrador declare **≥3 casos de eval** (id, descripción y criterio esperado). Es un gate de conteo verificado por el sistema: con menos de 3 casos NO SHALL existir ruta de publicación (ni parámetro de API para forzarla). El progreso (`n/3`) y cuántos faltan SHALL mostrarse siempre. Los casos declarados SHALL guardarse como **dataset versionado con la Skill** para que `e25-evals-gates` los ejecute cuando exista; mientras `e25` no esté archivado, los casos MUST NOT ejecutarse (modo placeholder) y la UI SHALL indicar que la ejecución llegará con el runner de evals. Quitar casos de una versión publicada es imposible (inmutable); en un borrador, si el conteo cae bajo 3, el gate SHALL volver a bloquearse en vivo.

#### Scenario: Con 2 casos la publicación queda bloqueada con el motivo visible

- **WHEN** un borrador de Skill declara 2 casos de eval y el Admin intenta publicar
- **THEN** el sistema mantiene "Publicar skill" deshabilitado mostrando "2/3 casos" y cuántos faltan; una llamada directa a la API de publicación también se rechaza

#### Scenario: Con 3 casos declarados la skill publica sin ejecutar evals

- **WHEN** un borrador declara 3 casos de eval con frontmatter válido y el Admin publica (`e25` no archivado)
- **THEN** la publicación se completa guardando los casos como dataset de la versión, sin ejecutar ningún caso, y la UI indica que la ejecución llegará con el runner de evals

#### Scenario: Borrar un caso en el borrador re-bloquea el gate en vivo

- **WHEN** un borrador con 3 casos pierde uno por edición del Admin
- **THEN** el gate vuelve a "2/3 casos" y "Publicar skill" se deshabilita en la misma interacción

### Requirement: Publicar una Skill no modifica ningún agente

Publicar una Skill SHALL dejarla disponible en el Registro de skills sin alterar ningún `AgentManifest` ni ninguna sesión: las Skills se hornean en versiones de agente (`agent-builder`) y NUNCA se cargan a mitad de sesión. La UI SHALL comunicar esta regla de forma permanente (banda de recordatorio) y en el momento de publicar (toast con CTA hacia el Agent Builder). Archivar una Skill usada por versiones activas de agentes SHALL permitirse con advertencia: las versiones ya horneadas no cambian; archivar solo impide hornearla en versiones nuevas.

#### Scenario: Publicar no toca los agentes que la declaran destino

- **WHEN** un Admin publica una Skill marcando a un agente como destino
- **THEN** ningún `AgentManifest` cambia; el sistema informa que para usarla hay que crear y activar una versión nueva del agente, con enlace al Agent Builder

#### Scenario: Archivar una skill horneada no afecta versiones activas

- **WHEN** un Admin archiva una Skill incluida en la versión activa de un agente
- **THEN** el sistema advierte antes de archivar, la versión activa del agente conserva la Skill horneada, y la Skill archivada ya no aparece como seleccionable para versiones nuevas

### Requirement: Registro de skills consultable

El sistema SHALL exponer un Registro de skills con una fila por Skill: slug, versión vigente, owner, agentes que la usan (derivado de `enabled_skills` de las versiones activas de `AgentManifest`; "—" si ninguno), estado (ACTIVA/BORRADOR/ARCHIVADA) y conteo de casos de eval contra el mínimo. El rol Técnico SHALL poder consultarlo en solo lectura; la edición es exclusiva del Admin. El campo `owner` es informativo (quién la mantiene) y MUST NOT otorgar permisos de edición. Cada Skill SHALL tener un changelog inmutable por versión (estado, fecha, autor y nota de cambio), que solo crece.

#### Scenario: Técnico consulta el registro sin poder editar

- **WHEN** un usuario Técnico abre el Registro de skills
- **THEN** ve la lista con slug, versión, owner, agentes que la usan y estado, sin ninguna acción de edición ni creación disponible

#### Scenario: El owner no puede editar por serlo

- **WHEN** un usuario Técnico figura como `owner` de una Skill
- **THEN** sigue sin poder editarla: el campo owner es informativo y la edición requiere rol Admin

#### Scenario: El changelog registra cada versión y no se reescribe

- **WHEN** una Skill acumula versiones publicadas
- **THEN** su changelog muestra una entrada por versión con autor y fecha del sistema, sin posibilidad de editar ni borrar entradas

### Requirement: Propuestas guiadas de Técnicos dentro de un template fijo

El sistema SHALL permitir que un usuario Técnico proponga un agente o una Skill personalizando **solo las secciones editables de un template fijo** (instrucciones dentro del marco; nunca el prefijo cache-safe ni las políticas), con el toolset seleccionable acotado a las Tools que la matriz rol×tool de `d20-gobernanza-plataforma` permite a su rol. La propuesta SHALL quedar en estado `pendiente` y MUST NOT aparecer en el catálogo, en el Registro de skills ni en ningún runtime hasta que un Admin la apruebe. La aprobación SHALL convertirla en un borrador normal del builder correspondiente (sujeto al mismo gate que una creación directa del Admin); el rechazo SHALL exigir motivo y notificar al Técnico vía el contrato de emisión de `d12-notificaciones`. Ambas decisiones SHALL emitir `AuditEvent`.

#### Scenario: La propuesta de un Técnico no es visible hasta la aprobación del Admin

- **WHEN** un Técnico envía una propuesta de agente personalizando las secciones editables del template
- **THEN** la propuesta queda `pendiente`, no aparece en el catálogo ni en el Registro de skills para ningún rol salvo la bandeja del Admin, y el Admin recibe una notificación

#### Scenario: El toolset propuesto se limita a lo permitido por el rol

- **WHEN** un Técnico arma una propuesta y su rol no tiene permitida una Tool según la matriz rol×tool
- **THEN** esa Tool no aparece como seleccionable en el formulario de propuesta; una propuesta manipulada que la incluya se rechaza en la validación del servidor

#### Scenario: Aprobar convierte la propuesta en borrador con gate completo

- **WHEN** un Admin aprueba una propuesta pendiente
- **THEN** la propuesta se convierte en un borrador del builder correspondiente que debe pasar el mismo gate de publicación/activación que cualquier creación del Admin, y la decisión queda auditada

#### Scenario: Rechazar exige motivo y notifica al Técnico

- **WHEN** un Admin rechaza una propuesta sin escribir motivo
- **THEN** el sistema mantiene deshabilitada la confirmación hasta que haya motivo; al confirmar, el Técnico recibe la notificación con el motivo y el evento queda en el Audit Log

### Requirement: Sandbox self-service sin Tools de escritura

El sistema SHALL ofrecer un constructor no-code en sandbox disponible para cualquier rol (Admin, Técnico, Funcional). El selector de tools del sandbox MUST listar únicamente Tools con `operation_type: read` del Tool Registry; ninguna Tool clasificada como escritura SHALL ofrecerse jamás en el sandbox, para ningún rol. Las construcciones de sandbox MUST NOT aparecer en el catálogo ni ser visibles para otros usuarios: solo su creador las ve y las ejercita. Toda ejecución dentro del sandbox SHALL pasar por el Policy Gate con las mismas reglas que producción.

#### Scenario: El sandbox nunca ofrece tools de escritura

- **WHEN** cualquier usuario abre el selector de tools del constructor sandbox
- **THEN** solo se listan Tools de lectura; ninguna Tool con `operation_type: write` aparece, sin importar el rol del usuario

#### Scenario: Un intento de invocar una tool de escritura desde el sandbox es denegado por el Policy Gate

- **WHEN** una construcción de sandbox manipulada intenta invocar una Tool clasificada como escritura
- **THEN** el Policy Gate devuelve `deny` (deny-by-default: el contexto sandbox no tiene ningún `allow` de escritura) y la decisión queda registrada en el Audit Log

#### Scenario: Una construcción de sandbox no es visible para otros usuarios

- **WHEN** un usuario crea un agente en el sandbox
- **THEN** ese agente no aparece en el catálogo ni en las vistas de ningún otro usuario; solo su creador lo ve dentro del sandbox

### Requirement: Promover del sandbox al catálogo exige el gate completo del Admin

La promoción de una construcción de sandbox al catálogo SHALL ser una acción exclusiva del Admin y SHALL recorrer el mismo flujo completo que una creación directa: conversión a borrador del builder correspondiente, validación de pasos, gate de publicación/activación (pluggable, según `d20`) y — si es una Skill — el gate de ≥3 casos de eval declarados. NO SHALL existir ningún atajo que salte pasos del gate por venir del sandbox.

#### Scenario: Promover una construcción de sandbox recorre el gate completo

- **WHEN** un Admin promueve al catálogo un agente creado en el sandbox por un Funcional
- **THEN** el sistema crea un borrador en el Agent Builder que debe pasar los 4 pasos válidos y el gate pluggable antes de activarse; recién entonces el agente aparece en el catálogo según su matriz de visibilidad

#### Scenario: Un rol no-Admin no puede promover

- **WHEN** un Técnico o Funcional intenta promover su construcción de sandbox al catálogo
- **THEN** el sistema no ofrece esa acción; el camino disponible para un Técnico es la propuesta guiada y, para un Funcional, solicitar la promoción a un Admin fuera del sistema

### Requirement: Toda acción del Skills Builder queda auditada

Cada acción relevante del Skills Builder (`draft-create`, `draft-edit`, `publish`, `archive`, `proposal-submit`, `proposal-approve`, `proposal-reject`, `sandbox-promote`) SHALL emitir un `AuditEvent` append-only con usuario, fecha-hora, Skill/propuesta, versión y resultado del gate cuando aplique.

#### Scenario: Publicar una skill queda en el Audit Log con su gate

- **WHEN** un Admin publica una Skill con 3/3 casos declarados
- **THEN** el Audit Log registra el evento `publish` con usuario, fecha-hora, slug, versión y el estado del gate de conteo (3/3, modo placeholder sin ejecución)
