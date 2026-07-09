# agent-skills Specification

## Purpose
TBD - created by archiving change c08-agent-skills. Update Purpose after archive.
## Requirements
### Requirement: Descubrimiento y carga de paquetes de skill referenciados por el Skill Manifest

El sistema SHALL descubrir y cargar el paquete de skill (carpeta con `SKILL.md`) que cada Skill Manifest en estado `active` referencia. El Skill Manifest es el envoltorio de gobernanza (`status`, políticas, tools permitidas) y el paquete es el contenido conforme a la spec Agent Skills. Un Skill Manifest cuyo paquete no existe o no valida MUST no quedar `active` (fail-fast al arranque y en CI), sin degradar silenciosamente.

#### Scenario: Paquete válido cargado desde el manifiesto activo

- **WHEN** un Skill Manifest `active` referencia un paquete cuya carpeta contiene un `SKILL.md` válido
- **THEN** el `SkillRegistry` expone la skill con su paquete resuelto y la marca disponible para el Skill Router

#### Scenario: Manifiesto que referencia un paquete inexistente

- **WHEN** un Skill Manifest `active` referencia una carpeta de paquete que no existe o no contiene `SKILL.md`
- **THEN** la carga falla fast (arranque/CI en rojo) y la skill NO queda `active` ni disponible para el Skill Router

### Requirement: Validación de paquete conforme a la spec Agent Skills

El sistema SHALL validar cada paquete de skill contra la spec Agent Skills antes de marcarlo disponible: frontmatter YAML con `name` y `description` obligatorios; `name` de 1–64 caracteres, solo minúsculas, dígitos y guiones, sin guion inicial/final ni guiones consecutivos; `name` idéntico al nombre del directorio padre y coherente con la referencia del Skill Manifest; y el tamaño de la metadata de descubrimiento (`name`+`description`) acotado a un límite configurado para no inflar el contexto de sistema. Un paquete que viola cualquiera de estas reglas MUST ser rechazado con un error accionable que identifique la regla violada.

#### Scenario: Frontmatter sin campo obligatorio

- **WHEN** un `SKILL.md` carece de `description` (o de `name`) en su frontmatter
- **THEN** la validación rechaza el paquete con un error que nombra el campo faltante y la skill no queda disponible

#### Scenario: Nombre con formato inválido

- **WHEN** un `SKILL.md` declara `name` con mayúsculas, guiones consecutivos o guion inicial/final
- **THEN** la validación rechaza el paquete señalando el formato de `name` requerido por la spec

#### Scenario: Nombre inconsistente con directorio o manifiesto

- **WHEN** el `name` del frontmatter no coincide con el nombre del directorio del paquete o con la referencia del Skill Manifest
- **THEN** la validación rechaza el paquete señalando la inconsistencia de nombre

#### Scenario: Metadata de descubrimiento excede el límite

- **WHEN** la suma de `name`+`description` de un paquete supera el límite de metadata configurado
- **THEN** la validación rechaza el paquete para proteger el presupuesto de contexto de sistema

### Requirement: Progressive disclosure en tres niveles

El sistema SHALL exponer el contenido de las skills en tres niveles de divulgación progresiva conforme a la spec Agent Skills: (1) los metadatos (`name`+`description`) de las skills ACTIVAS del agente entran al contexto de sistema al iniciar; (2) el cuerpo de `SKILL.md` se carga solo cuando el Skill Router activa la skill; (3) los archivos de apoyo (`scripts/`, `references/`, `assets/`) se leen únicamente bajo demanda al ser referenciados. Los niveles 2 y 3 MUST no cargarse por adelantado.

#### Scenario: Solo metadatos en el contexto de sistema antes de activar

- **WHEN** un agente arranca con skills `active` y aún no se activa ninguna
- **THEN** el contexto de sistema contiene los metadatos (`name`+`description`) de esas skills y NO contiene el cuerpo de ningún `SKILL.md`

#### Scenario: El cuerpo se carga al activar la skill

- **WHEN** el Skill Router activa una skill para la consulta en curso
- **THEN** el cuerpo de su `SKILL.md` se carga en contexto y su toolset ejecutable queda disponible para esa activación

#### Scenario: Archivo de apoyo cargado bajo demanda

- **WHEN** una skill activa referencia un archivo de `references/` (o `scripts/`/`assets/`) durante su ejecución
- **THEN** ese archivo se lee en ese momento y no antes; los archivos no referenciados nunca se cargan

### Requirement: Intersección allowed-tools como único toolset ejecutable

El toolset ejecutable de una skill activa SHALL ser la intersección entre las tools declaradas por el paquete (`allowed-tools`) y las tools permitidas por su Skill Manifest (`tools`). Una tool presente en solo uno de los dos MUST quedar fuera del toolset ejecutable. Regla dura 3 INTACTA: las tools llegan SOLO vía la skill activa, el Default Chat nunca las ejecuta directamente, y cada ejecución MUST pasar por el Policy Gate (deny-by-default) y registrarse en el Audit Log.

#### Scenario: Tool en la intersección se ejecuta con decisión allow del Policy Gate

- **WHEN** una skill activa invoca una tool presente tanto en `allowed-tools` del paquete como en `tools` del Skill Manifest
- **THEN** el Policy Gate evalúa la ejecución y devuelve `allow`, la tool se ejecuta vía su adapter y la decisión queda en el Audit Log

#### Scenario: Tool del paquete ausente del Skill Manifest queda fuera y el Policy Gate la deniega

- **WHEN** un paquete declara en `allowed-tools` una tool que su Skill Manifest NO permite y se intenta invocarla
- **THEN** la tool no forma parte del toolset ejecutable y el Policy Gate devuelve `deny` (deny-by-default), registrando el rechazo en el Audit Log

#### Scenario: El Default Chat no puede ejecutar una tool sin skill activa

- **WHEN** el Default Chat intenta invocar una tool sin una skill activa que la habilite
- **THEN** el Policy Gate devuelve `deny` por la regla dura 3 y la decisión queda auditada

### Requirement: Skillset fijo por versión de agente

Las skills activas de un agente SHALL resolverse al cargar, a partir de `enabled_skills` del Agent Manifest y de los Skill Manifest `active`, y permanecer fijas durante la sesión. No SHALL existir carga de skills a mitad de sesión: habilitar o cambiar una skill exige una nueva versión de manifiesto (`draft → validado → active`), no un hot-reload en runtime.

#### Scenario: Una skill añadida después no aparece en una sesión en curso

- **WHEN** se activa un nuevo Skill Manifest mientras una sesión ya está en curso
- **THEN** la sesión en curso conserva su skillset resuelto al inicio y no incorpora la skill nueva hasta iniciar una sesión posterior

### Requirement: Skill de ejemplo de fábrica conforme a la spec

El repo SHALL incluir una skill de ejemplo genérica de fábrica (redacción/formato de informes, sin dominio ERP) compuesta por un paquete conforme a la spec —frontmatter con `name`+`description`, cuerpo de `SKILL.md`, al menos un archivo de apoyo en `references/` y `allowed-tools` referenciando la tool de ejemplo de `c09`— y por su Skill Manifest envolvente que la referencia. El paquete de ejemplo MUST pasar la validación de esta capability.

#### Scenario: El Default Chat resuelve una consulta con la skill de ejemplo

- **WHEN** el Skill Router activa la skill de ejemplo para una consulta de redacción/formato de informe
- **THEN** el cuerpo del paquete se carga por divulgación progresiva, su toolset ejecutable (intersección con el Skill Manifest) queda disponible, y el Default Chat produce la respuesta usando la skill conforme a la spec

#### Scenario: El paquete de ejemplo valida contra la capability

- **WHEN** se ejecuta la validación de paquetes sobre la skill de ejemplo de fábrica
- **THEN** el frontmatter, el formato de `name`, la coherencia con el Skill Manifest y el límite de metadata se reportan válidos

