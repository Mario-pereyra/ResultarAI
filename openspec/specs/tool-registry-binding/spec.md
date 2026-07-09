# tool-registry-binding Specification

## Purpose
TBD - created by archiving change c09-mcp-tools. Update Purpose after archive.
## Requirements
### Requirement: Solo las Tools declaradas en un ToolManifest activo existen para el runtime

El runtime SHALL exponer únicamente las Tools que estén declaradas en un `ToolManifest` con `status: active` en el `ToolRegistry` (`a02`). Una Tool que un MCP Server publique en `tools/list` pero que no tenga un `ToolManifest` activo MUST NOT existir para el runtime: no es invocable y el cliente MUST NOT emitir `tools/call` para ella (deny-by-default a nivel de registro). Sin manifiesto no existe (regla dura 6).

#### Scenario: Tool del server sin ToolManifest activo no existe

- **WHEN** un MCP Server expone una Tool que no está declarada en ningún `ToolManifest` activo del `ToolRegistry` y una Skill intenta usarla
- **THEN** el runtime la rechaza como inexistente antes de consultar al Policy Gate, no se emite `tools/call` y el intento queda registrado en un `AuditEvent`

#### Scenario: Tool con ToolManifest activo sí es invocable

- **WHEN** una Skill invoca una Tool cuyo `ToolManifest` está `active` y resuelve a un MCP Server + `tool_name`
- **THEN** el runtime la reconoce como existente y la somete al Policy Gate antes de cualquier `tools/call`

### Requirement: El ToolManifest fija MCP Server, tool_name y clasificación inmutable en runtime

El `ToolManifest` SHALL resolver cada Tool a un MCP Server + `tool_name` y fijar su clasificación `operation_type` (lectura/escritura) y su `risk.level`. Esa clasificación MUST quedar fija por `version` del manifiesto: cambiarla exige una nueva `version` (un PR) y MUST NOT poder mutarse en runtime. Las `annotations` que el MCP Server incluya en el descriptor de la Tool se tratan como **no confiables** (spec MCP §Tool Safety) y MUST NOT alterar la clasificación autoritativa del manifiesto.

#### Scenario: El binding resuelve server y tool_name desde el manifiesto

- **WHEN** el runtime carga un `ToolManifest` activo de tipo MCP
- **THEN** obtiene del manifiesto el identificador del MCP Server, el `tool_name`, el `operation_type` y el `risk.level`, y usa esa clasificación —no la del server— para gobernar la invocación

#### Scenario: La clasificación no se puede cambiar en runtime

- **WHEN** se intenta reclasificar una Tool (p. ej. de escritura a lectura, o bajar su `risk.level`) sin cambiar la `version` del `ToolManifest`
- **THEN** el cambio se rechaza: la clasificación solo cambia por una nueva `version` del manifiesto (PR), nunca por mutación en runtime

#### Scenario: Las annotations del server no alteran la clasificación

- **WHEN** un MCP Server declara `annotations` en el descriptor de una Tool que contradicen la clasificación de su `ToolManifest` (p. ej. anuncia una escritura como `readOnlyHint`)
- **THEN** el runtime ignora las `annotations` por no confiables y gobierna la invocación según el `operation_type` y `risk.level` del manifiesto

### Requirement: Validación cruzada del binding contra el MCP Server

El sistema SHALL validar que el `tool_name` referenciado por un `ToolManifest` de tipo MCP exista efectivamente en el `tools/list` de su MCP Server. Un `ToolManifest` que apunte a un `tool_name` inexistente en el server MUST NOT quedar `active` (falla de validación cruzada, coherente con el ciclo de vida `draft → validated → active`).

#### Scenario: tool_name inexistente en el server invalida el binding

- **WHEN** un `ToolManifest` referencia un `tool_name` que su MCP Server no expone en `tools/list`
- **THEN** la validación cruzada falla nombrando el `tool_name` ausente y el manifiesto no pasa a `active`

### Requirement: Ejecución gobernada por la clasificación con emisión de AuditEvent

Toda invocación de una Tool MCP SHALL autorizarse en el Policy Gate antes de emitir `tools/call`, usando la clasificación del `ToolManifest`. Las lecturas (`operation_type: read`) MUST obtener `allow` del Policy Gate cuando una Policy activa las permita; las escrituras (`operation_type: write`) MUST resultar SIEMPRE en `escalate_hitl`, aunque una Policy dijera `allow`, y en ese caso el cliente MUST NOT emitir `tools/call` (el evento de escritura queda en espera; la Tarjeta HITL llega en `d17`). Toda decisión del Policy Gate —`allow`, `deny` o `escalate_hitl`— MUST emitir un `AuditEvent`.

#### Scenario: Lectura permitida se ejecuta y se audita

- **WHEN** una Skill invoca una Tool de lectura y una Policy activa la permite
- **THEN** el Policy Gate devuelve `allow`, el cliente emite `tools/call` y se emite un `AuditEvent` con la decisión `allow` y el resultado resumido

#### Scenario: Lectura sin Policy que la permita se bloquea

- **WHEN** una Skill invoca una Tool de lectura para la que ninguna Policy activa concede `allow`
- **THEN** el Policy Gate devuelve `deny` (deny-by-default), el cliente NO emite `tools/call` y se emite un `AuditEvent` con la decisión `deny`

#### Scenario: Escritura escala a HITL siempre y no se ejecuta

- **WHEN** una Skill invoca una Tool cuyo `ToolManifest` la clasifica como `operation_type: write` (p. ej. la escritura simulada del server de ejemplo)
- **THEN** el Policy Gate devuelve `escalate_hitl` de forma incondicional, el cliente NO emite `tools/call`, el evento queda en espera de aprobación humana y se emite un `AuditEvent` con la decisión `escalate_hitl`

#### Scenario: La tool de lectura del server de ejemplo corre end-to-end

- **WHEN** el Default Chat activa la Skill de fábrica y esta invoca una Tool de lectura del MCP Server de ejemplo con Policy Gate `allow`
- **THEN** la Tool se ejecuta vía la Skill (regla dura 3), pasa por el Policy Gate y queda auditada con su `AuditEvent` (criterio de salida del roadmap para `c09`)

