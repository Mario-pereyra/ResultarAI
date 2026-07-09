# audit-persistence — Delta Spec (b04-persistencia-postgres)

## ADDED Requirements

### Requirement: Persistencia del AuditEvent

La base SHALL contener una tabla `audit_log` que persiste el contrato `AuditEvent` de `a03` con, como mínimo: clave primaria **UUIDv7**, timestamp, usuario, tenant, agente, skill, tool, parámetros (resumidos/enmascarados), decisión del Policy Gate, política aplicada, resultado (resumen), costo y `trace_id` de Langfuse ([docs/06-seguridad-gobernanza.md](../../../../docs/06-seguridad-gobernanza.md)). Toda decisión del Policy Gate —incluidas las `allow`— SHALL producir una fila.

#### Scenario: Cada decisión del Policy Gate deja un evento

- **WHEN** el runtime persiste una decisión del Policy Gate (allow, deny o escalate_hitl)
- **THEN** se inserta una fila en `audit_log` con el usuario, tenant, contexto de la acción, la decisión y la política aplicada

#### Scenario: Los parámetros sensibles se persisten enmascarados

- **WHEN** se persiste un `AuditEvent` cuya acción incluía parámetros sensibles
- **THEN** la fila almacena los parámetros resumidos/enmascarados y nunca secretos ni credenciales (data boundaries, [docs/06-seguridad-gobernanza.md](../../../../docs/06-seguridad-gobernanza.md))

### Requirement: Inmutabilidad física append-only

La tabla `audit_log` SHALL ser append-only con enforcement **físico** en la base: UPDATE y DELETE quedan prohibidos vía grants de rol y/o triggers, no solo por disciplina de aplicación. Una corrección SHALL ser un evento nuevo que referencia al anterior, nunca una mutación.

#### Scenario: La base rechaza un UPDATE sobre audit_log

- **WHEN** se intenta un UPDATE sobre cualquier fila de `audit_log`
- **THEN** la base lo rechaza con error y la fila permanece intacta

#### Scenario: La base rechaza un DELETE sobre audit_log

- **WHEN** se intenta un DELETE sobre cualquier fila de `audit_log`
- **THEN** la base lo rechaza con error y ninguna fila se elimina

#### Scenario: La corrección es un evento nuevo

- **WHEN** hace falta corregir un evento ya registrado
- **THEN** se inserta un evento nuevo que referencia al anterior, sin modificar ni borrar el original

### Requirement: Consulta del audit log por filtros

El adapter SHALL exponer consulta de `audit_log` por filtros: usuario, tenant, agente, skill, tool, rango temporal, decisión y `trace_id`, para reconstruir "quién hizo qué, cuándo y con qué decisión".

#### Scenario: Consulta por usuario y rango temporal

- **WHEN** se consulta el audit log filtrando por un usuario y un rango de fechas
- **THEN** se devuelven exactamente los eventos de ese usuario dentro del rango, ordenados temporalmente

#### Scenario: Reconstrucción por trace_id

- **WHEN** se consulta por un `trace_id` de Langfuse
- **THEN** se devuelven los eventos de auditoría ligados a esa traza, permitiendo reconstruir la ejecución
