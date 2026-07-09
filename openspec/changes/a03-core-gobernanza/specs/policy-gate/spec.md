# policy-gate — Delta Spec (a03-core-gobernanza)

## ADDED Requirements

### Requirement: Evaluación pura deny-by-default

El Policy Gate (`PolicyGate`) SHALL ser una función pura que recibe un `ActionRequest` y devuelve un `PolicyDecision`, sin I/O, sin red, sin estado oculto y determinista para el mismo `ActionRequest` y el mismo conjunto de Policy Manifests activos. Rige **deny-by-default**: toda acción que ningún `PolicyManifest` activo permita explícitamente SHALL resolverse con efecto `deny`.

#### Scenario: Acción permitida por una Policy activa

- **WHEN** un `ActionRequest` de `operation_type: read`, `risk_level: low` y `tenant` habilitado coincide con la condición `allow` de un `PolicyManifest` activo
- **THEN** el Policy Gate devuelve un `PolicyDecision` con efecto `allow`

#### Scenario: Ausencia de Policy permisiva bloquea

- **WHEN** un `ActionRequest` no coincide con ninguna condición `allow` de los Policy Manifests activos
- **THEN** el Policy Gate devuelve un `PolicyDecision` con efecto `deny` por deny-by-default

#### Scenario: Evaluación determinista

- **WHEN** el mismo `ActionRequest` se evalúa dos veces contra el mismo conjunto de Policy Manifests activos
- **THEN** ambas llamadas devuelven un `PolicyDecision` idéntico (mismo efecto, misma Policy aplicada, misma razón), sin depender de reloj, red ni estado externo

### Requirement: Efectos de la decisión

`PolicyDecision.effect` SHALL ser exactamente uno de `allow`, `deny` o `escalate_hitl`. No existe otro efecto; `escalate_hitl` significa que la acción requiere HITL (aprobación humana previa) antes de poder ejecutarse.

#### Scenario: Efecto fuera del conjunto es imposible

- **WHEN** se construye un `PolicyDecision`
- **THEN** su `effect` solo admite los valores `allow`, `deny` o `escalate_hitl` y cualquier otro valor es rechazado por el schema Pydantic

#### Scenario: Riesgo alto escala a HITL

- **WHEN** un `ActionRequest` de `risk_level: high` es evaluado por el Policy Gate
- **THEN** el `PolicyDecision` tiene efecto `escalate_hitl` y la acción no se ejecuta hasta la aprobación humana

### Requirement: Contrato del ActionRequest y aislamiento por tenant

El `ActionRequest` SHALL portar como mínimo: `user`, `tenant`, `agent`, `skill`, `tool`, `operation_type` (`read` | `write`), `risk_level` y `environment`. El Policy Gate SHALL validar la autorización usuario↔tenant: una acción cuyo `user` no esté autorizado para el `tenant` solicitado SHALL resolverse con efecto `deny`.

#### Scenario: Cruce entre tenants bloqueado

- **WHEN** un `user` autorizado para el tenant `totalpec` emite un `ActionRequest` sobre el tenant `union`
- **THEN** el Policy Gate devuelve un `PolicyDecision` con efecto `deny` y razón que indica falta de autorización usuario↔tenant

#### Scenario: ActionRequest incompleto es inválido

- **WHEN** se intenta construir un `ActionRequest` sin `tenant` para una acción de Tool del ERP
- **THEN** el schema Pydantic rechaza la construcción (el `tenant` es obligatorio en toda acción de Tool del ERP)

### Requirement: Razón legible y Policy aplicada en cada decisión

Todo `PolicyDecision` SHALL incluir una razón legible por humanos y el identificador del `PolicyManifest` aplicado. Cuando el efecto sea `deny` por ausencia de Policy permisiva, el campo de Policy aplicada SHALL contener el marcador `deny_by_default`.

#### Scenario: Allow reporta la Policy aplicada

- **WHEN** el Policy Gate resuelve una acción con efecto `allow`
- **THEN** el `PolicyDecision` incluye el `id` del `PolicyManifest` que la permitió y una razón legible

#### Scenario: Deny por defecto reporta el marcador

- **WHEN** el Policy Gate resuelve una acción con efecto `deny` porque ninguna Policy la permitió
- **THEN** el `PolicyDecision` incluye el marcador `deny_by_default` como Policy aplicada y una razón legible que explica el bloqueo

### Requirement: Niveles de riesgo y su mapeo a HITL

El Policy Gate SHALL reconocer los niveles de riesgo `low`, `medium`, `high` y `critical` (`docs/06`) y mapearlos a decisiones así: `low` → `allow` si una Policy lo permite; `medium` → `allow` con límites declarados en la decisión (por ejemplo `max_rows`, paginación o resumen); `high` → `escalate_hitl`; `critical` → `escalate_hitl` con el contrato reforzado de HITL.

#### Scenario: Riesgo low permitido por Policy

- **WHEN** un `ActionRequest` de `risk_level: low` coincide con una condición `allow`
- **THEN** el `PolicyDecision` tiene efecto `allow`

#### Scenario: Riesgo medium permitido con límites

- **WHEN** un `ActionRequest` de `risk_level: medium` (por ejemplo, una lectura masiva) es permitido por una Policy
- **THEN** el `PolicyDecision` tiene efecto `allow` y declara los límites aplicables (`max_rows`, paginación o resumen)

#### Scenario: Riesgo high escala a HITL

- **WHEN** un `ActionRequest` de `risk_level: high` es evaluado
- **THEN** el `PolicyDecision` tiene efecto `escalate_hitl`

#### Scenario: Riesgo critical escala a HITL

- **WHEN** un `ActionRequest` de `risk_level: critical` (por ejemplo, una escritura al ERP) es evaluado
- **THEN** el `PolicyDecision` tiene efecto `escalate_hitl` con el contrato reforzado de HITL

### Requirement: Contrato reforzado de HITL para riesgo critical

Para acciones de `risk_level: critical`, el `PolicyDecision` con efecto `escalate_hitl` SHALL declarar que la aprobación exige comentario del aprobador; y cuando la acción sea irreversible SHALL declarar además que exige una segunda aprobación (4-ojos). Este change define únicamente el contrato de dominio; los mecanismos de UI (tarjeta, cola, expiración) llegan en `d17-hitl-aprobaciones`.

#### Scenario: Crítico exige comentario del aprobador

- **WHEN** el Policy Gate resuelve una acción `critical` con efecto `escalate_hitl`
- **THEN** el `PolicyDecision` declara `requires_approver_comment = true`

#### Scenario: Crítico irreversible exige segunda aprobación

- **WHEN** el Policy Gate resuelve una acción `critical` marcada como irreversible con efecto `escalate_hitl`
- **THEN** el `PolicyDecision` declara `requires_approver_comment = true` y `requires_second_approval = true`

### Requirement: Evaluación en cada paso (Runtime Authorization per Step)

El Policy Gate SHALL ser evaluable en cada paso del runtime, no solo al inicio de la sesión (blueprint §2.4.4, P0 Runtime Authorization). Cada paso produce su propio `PolicyDecision` a partir de su propio `ActionRequest`, con independencia de las decisiones de pasos anteriores (la función no acumula estado entre llamadas).

#### Scenario: Pasos consecutivos con decisiones independientes

- **WHEN** un primer `ActionRequest` de `risk_level: low` se resuelve como `allow` y a continuación un segundo `ActionRequest` de `risk_level: high` sobre el mismo contexto se evalúa
- **THEN** el segundo `PolicyDecision` es `escalate_hitl`, sin verse afectado por el `allow` previo

### Requirement: Toda decisión del Policy Gate produce un AuditEvent

Toda evaluación del Policy Gate —incluidas las de efecto `allow`— SHALL producir de forma determinista exactamente un `AuditEvent` (contrato en la capacidad `audit-log`) que registra el `ActionRequest`, el `PolicyDecision` y su razón. La construcción del `AuditEvent` es un mapeo puro; su persistencia es responsabilidad de un change posterior (`b04-persistencia-postgres`).

#### Scenario: La decisión allow también deja rastro

- **WHEN** el Policy Gate resuelve una acción con efecto `allow`
- **THEN** se produce un `AuditEvent` correspondiente a esa decisión (una decisión `allow` no queda sin auditar)

#### Scenario: Correspondencia uno a uno decisión↔evento

- **WHEN** el Policy Gate emite un `PolicyDecision` de efecto `deny` o `escalate_hitl`
- **THEN** se produce exactamente un `AuditEvent` que referencia ese `PolicyDecision`, su efecto y su razón
