# tool-call-visibility — Delta Spec (c09-mcp-tools)

## ADDED Requirements

### Requirement: Contrato de datos de la Tool call visible

El sistema SHALL producir, por cada invocación de una Tool MCP, un registro de "Tool call visible" para que la UI la muestre colapsada por defecto y expandible bajo demanda, conforme a `design/FUNCIONALIDADES.md` §4 (Tool calls visibles). El registro MUST incluir, como mínimo: el nombre de la Tool, los argumentos, el resultado truncado y la duración de la invocación. El registro MUST derivarse de la invocación y de su `AuditEvent`; el `AuditEvent` (append-only) es la fuente de verdad, y este registro es una proyección de lectura.

#### Scenario: Cada invocación produce un registro visible colapsable

- **WHEN** una Skill invoca una Tool de lectura con Policy Gate `allow` y el cliente recibe el `CallToolResult`
- **THEN** se produce un registro visible con nombre de Tool, argumentos, resultado truncado y duración, presentado colapsado y expandible, coherente con el `AuditEvent` de esa invocación

#### Scenario: Truncado del resultado en el registro visible

- **WHEN** el resultado de una Tool (Policy Gate `allow`) excede el largo mostrable
- **THEN** el registro visible incluye el resultado truncado con marca explícita de truncado, sin alterar el `AuditEvent` de origen

### Requirement: Capa de visualización por rol

El registro de Tool call visible SHALL exponerse con una capa por rol, conforme a `design/FUNCIONALIDADES.md` §4 y §12: para el rol **Funcional** la vista expandida MUST usar lenguaje simple y NO mostrar los parámetros técnicos completos; para los roles **Técnico** y **Admin** MUST mostrar los parámetros completos de la invocación. La capa por rol MUST ser una diferencia de presentación sobre el mismo `AuditEvent`, no dos registros distintos.

#### Scenario: Funcional ve lenguaje simple

- **WHEN** un usuario con rol Funcional expande una Tool call de lectura ejecutada con Policy Gate `allow`
- **THEN** ve una descripción en lenguaje simple (qué se consultó y un resultado resumido) sin los parámetros técnicos completos

#### Scenario: Técnico y Admin ven parámetros completos

- **WHEN** un usuario con rol Técnico o Admin expande la misma Tool call (Policy Gate `allow`)
- **THEN** ve los parámetros completos de la invocación y el detalle técnico del resultado, derivados del mismo `AuditEvent`

### Requirement: Estado de gobernanza reflejado en el registro visible

El registro de Tool call visible SHALL reflejar la decisión del Policy Gate de esa invocación. Una lectura con `allow` MUST mostrarse como ejecutada; una escritura con `escalate_hitl` MUST mostrarse como en espera de aprobación humana (sin efecto real ejecutado) y NO como completada, coherente con que la Tarjeta HITL operativa llega en `d17`.

#### Scenario: Escritura escalada se muestra en espera de aprobación

- **WHEN** una Skill invoca una Tool de escritura y el Policy Gate devuelve `escalate_hitl`
- **THEN** el registro visible la muestra como "en espera de aprobación", no como ejecutada, y su estado es coherente con el `AuditEvent` de decisión `escalate_hitl`

#### Scenario: Lectura permitida se muestra como ejecutada

- **WHEN** una Skill invoca una Tool de lectura y el Policy Gate devuelve `allow`
- **THEN** el registro visible la muestra como ejecutada, con su resultado truncado y duración
