# skill-router Specification

## Purpose
TBD - created by archiving change b06-runtime-grafos. Update Purpose after archive.
## Requirements
### Requirement: Decisión de ruteo por Routing Manifest

El `SkillRouter` (`core/routing`, función pura, sin I/O ni frameworks) SHALL decidir la acción del turno (`answer_directly` | `activate_skill`) evaluando las reglas activas del Routing Manifest (`a02-core-manifiestos`) contra el intent del turno.

#### Scenario: Intent conocido activa la skill declarada por la regla

- **WHEN** el turno tiene intent `erp_query` y la regla activa del Routing Manifest mapea ese intent a `action: activate_skill, target: erp_query_skill`
- **THEN** el `SkillRouter` devuelve la decisión `activate_skill` con `target=erp_query_skill`

#### Scenario: Intent general responde directo

- **WHEN** el turno tiene intent `general_question`
- **THEN** el `SkillRouter` devuelve la decisión `answer_directly`

#### Scenario: Intent desconocido nunca inventa acceso a datos

- **WHEN** el turno tiene un intent que no coincide con ninguna regla activa del Routing Manifest
- **THEN** el `SkillRouter` devuelve `answer_directly` con una razón que declara la ausencia de esa capacidad, sin activar ninguna skill

### Requirement: Razón legible de la decisión de ruteo

Toda decisión del `SkillRouter` SHALL incluir una razón legible: qué regla del Routing Manifest se aplicó, o por qué ninguna aplicó. Esa razón es consumible por el audit log y, en changes posteriores, por la vista de tool calls (`d13-chat-conversacion`).

#### Scenario: La razón referencia la regla aplicada

- **WHEN** el `SkillRouter` decide `activate_skill` a partir de una regla del Routing Manifest
- **THEN** la razón incluye el `id` del Routing Manifest y el `intent` que disparó esa regla

#### Scenario: La razón declara la ausencia de regla

- **WHEN** el `SkillRouter` decide `answer_directly` por no encontrar ninguna regla que coincida con el intent
- **THEN** la razón declara explícitamente que no hubo coincidencia, en vez de dejarla vacía o genérica

### Requirement: Toda decisión de ruteo se audita

Cada decisión del `SkillRouter` SHALL traducirse en un `ActionRequest` evaluado por el Policy Gate (`PolicyPort`, `a03-core-gobernanza`) antes de ejecutar la acción decidida. La `PolicyDecision` resultante y la razón de ruteo se registran juntas en un `AuditEvent` append-only.

#### Scenario: Activar una skill pasa por el Policy Gate antes de ejecutarse

- **WHEN** el `SkillRouter` decide `activate_skill` para `erp_query_skill`
- **THEN** el runtime construye un `ActionRequest` con `skill=erp_query_skill`, lo somete a `PolicyPort` antes de cualquier ejecución, y el `AuditEvent` resultante referencia la razón de ruteo junto con la `PolicyDecision` obtenida

#### Scenario: Responder directo también se audita

- **WHEN** el `SkillRouter` decide `answer_directly`
- **THEN** el `AuditEvent` registrado para ese paso incluye la decisión `answer_directly`, su razón y el efecto `allow` del Policy Gate, aun cuando no se active ninguna skill

