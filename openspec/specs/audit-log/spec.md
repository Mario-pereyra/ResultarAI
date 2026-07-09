# audit-log Specification

## Purpose
TBD - created by archiving change a03-core-gobernanza. Update Purpose after archive.
## Requirements
### Requirement: Contrato del AuditEvent

El `AuditEvent` SHALL modelar, con un schema Pydantic en `core/`, un evento de auditoría con al menos: **quién** (`user`, `tenant`), **qué** (`agent`, `skill`, `tool`, `operation_type`, parámetros resumidos/enmascarados), **cuándo** (`timestamp`), **contexto** (`environment`), **decisión** (efecto del `PolicyDecision` y `PolicyManifest` aplicado) y **razón** (la razón legible del `PolicyDecision`). Los campos `result_summary`, `cost` y `trace_id` de Langfuse SHALL existir como opcionales reservados para changes posteriores (`b05`, `b07`), sin ser obligatorios en este contrato.

#### Scenario: Un AuditEvent registra quién, qué, cuándo, decisión y razón

- **WHEN** se construye un `AuditEvent` a partir de un `ActionRequest` y su `PolicyDecision`
- **THEN** el evento contiene `user`, `tenant`, `agent`, `skill`, `tool`, `operation_type`, `timestamp`, `environment`, el efecto de la decisión, el `PolicyManifest` aplicado y la razón legible

#### Scenario: Campos de observabilidad son opcionales en esta etapa

- **WHEN** se construye un `AuditEvent` sin `result_summary`, `cost` ni `trace_id`
- **THEN** la construcción es válida (esos campos quedan reservados para `b05`/`b07`)

### Requirement: Invariante append-only e inmutable

El `AuditEvent` SHALL ser inmutable una vez construido (modelo Pydantic congelado): no admite mutación de sus campos. El Audit Log SHALL tratarse como **append-only**: no se permite UPDATE ni DELETE de un evento existente. Una corrección SHALL expresarse como un `AuditEvent` nuevo que referencia al anterior mediante un campo `corrects` (el `id` del evento corregido), dejando intacto el original.

#### Scenario: Intento de mutación rechazado

- **WHEN** se intenta reasignar un campo de un `AuditEvent` ya construido
- **THEN** la operación falla (el modelo es inmutable/congelado) y el evento original permanece sin cambios

#### Scenario: Corrección crea un evento nuevo que referencia al anterior

- **WHEN** una decisión previa debe corregirse
- **THEN** se construye un `AuditEvent` nuevo con `corrects` apuntando al `id` del evento original, y el evento original se conserva sin modificación ni borrado

### Requirement: Parámetros resumidos y enmascarados

Los parámetros registrados en un `AuditEvent` SHALL almacenarse resumidos y con los campos sensibles enmascarados. Secretos y credenciales SHALL no aparecer nunca en un `AuditEvent`.

#### Scenario: Campos sensibles enmascarados en el evento

- **WHEN** se construye un `AuditEvent` para una acción de Tool cuyos parámetros incluyen campos sensibles
- **THEN** el evento almacena esos valores enmascarados y ningún secreto o credencial queda registrado en texto claro

### Requirement: Cobertura del Audit Log sobre las decisiones del Policy Gate

Toda decisión del Policy Gate —efecto `allow`, `deny` o `escalate_hitl`— SHALL tener su `AuditEvent` correspondiente. Ninguna decisión queda fuera del Audit Log.

#### Scenario: Cada efecto de decisión emite su evento

- **WHEN** el Policy Gate resuelve acciones con efecto `allow`, `deny` y `escalate_hitl`
- **THEN** cada una de esas decisiones produce su propio `AuditEvent` que registra su efecto y su razón

#### Scenario: Una decisión escalada a HITL queda auditada

- **WHEN** el Policy Gate resuelve una acción con efecto `escalate_hitl`
- **THEN** se produce un `AuditEvent` que registra la escalada, su `risk_level` y la razón, antes de cualquier aprobación humana

