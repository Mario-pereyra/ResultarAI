# observability-tracing — Delta Spec (b07-observabilidad)

## ADDED Requirements

### Requirement: Traza por turno completo

Cada Turno (mensaje del usuario → respuesta final entregada, incluidas todas las llamadas a modelo, activaciones de skill y decisiones de routing que ocurran dentro de ese turno) SHALL producir exactamente una traza en Langfuse a través del `TracePort`, identificable por un único `trace_id`. Una traza NUNCA representa una llamada LLM aislada.

#### Scenario: Turno con una sola llamada al modelo

- **WHEN** el Default Chat responde directo con una única llamada a modelo dentro del turno
- **THEN** se crea una traza con un `trace_id` que agrupa esa llamada y queda asociada al turno completo

#### Scenario: Turno con escalación a un perfil de modelo alterno

- **WHEN** el turno dispara el marcador de escalación y se re-ejecuta con un perfil de modelo distinto
- **THEN** ambas llamadas (la original y la escalada) quedan bajo el mismo `trace_id` del turno, no en trazas separadas

### Requirement: Costo con tarifas hit/miss separadas

La traza de cada turno SHALL registrar el costo desglosado en `usage_details`/`cost_details` con buckets separados para tokens de cache hit y cache miss, tal como los reporta `adapters/llm_litellm` (`b05-gateway-modelos`), y el total de tokens de entrada y salida.

#### Scenario: Turno con cache hit

- **WHEN** el gateway reporta `prompt_cache_hit_tokens` mayor a cero para el turno
- **THEN** la traza registra ese volumen y su costo en el bucket de hit, distinto del bucket de miss

#### Scenario: Turno con cache miss total

- **WHEN** el gateway reporta cache miss completo (primer turno de una sesión nueva)
- **THEN** la traza registra el costo íntegro en el bucket de miss y el bucket de hit queda en cero, sin mezclarse

### Requirement: Modelo/perfil y decisión de routing registrados

La traza SHALL registrar el perfil de modelo (`model_profile`) efectivamente usado, incluida la etiqueta de "modelo alterno" cuando hubo fallback, y la decisión del Skill Router para ese turno (respuesta directa, skill activada o delegación).

#### Scenario: Turno con modelo alterno por fallback

- **WHEN** la cascada de fallback de `b05-gateway-modelos` usa un perfil distinto al perfil primario configurado
- **THEN** la traza incluye la etiqueta de modelo alterno y el nombre del perfil realmente usado

#### Scenario: Turno que activa una skill

- **WHEN** el Skill Router decide activar una skill en lugar de responder directo
- **THEN** la traza registra el identificador de la skill activada y la razón de esa decisión de routing

### Requirement: Decisiones del Policy Gate registradas en la traza

Cada `PolicyDecision` emitida durante el turno (incluidas las de efecto `allow`) SHALL quedar registrada como parte de la traza del turno, referenciando el mismo evento que ya persiste el Audit Log (`a03-core-gobernanza`), sin duplicar su contenido normativo.

#### Scenario: Turno sin fricción de gobernanza

- **WHEN** el Policy Gate evalúa la única acción del turno y decide `allow`
- **THEN** la traza incluye esa decisión, la Policy aplicada y su razón

#### Scenario: Turno que escala a HITL

- **WHEN** el Policy Gate decide `escalate_hitl` para una acción del turno
- **THEN** la traza registra la decisión `escalate_hitl`, la razón y el nivel de riesgo, de forma reconstruible junto al `AuditEvent` correspondiente por su identificador común

### Requirement: Sesión y usuario enmascarado

La traza SHALL asociar el `session_id` de la Sesión en curso y el identificador del usuario, y el identificador del usuario SHALL pasar por la función `mask` configurada a nivel del cliente Langfuse antes de salir de la plataforma: la telemetría NUNCA expone identidad en claro.

#### Scenario: Traza asociada a su sesión

- **WHEN** se crea la traza de un turno dentro de una Sesión existente
- **THEN** la traza queda vinculada al `session_id` de esa Sesión, permitiendo reconstruir el historial completo de la sesión en Langfuse

#### Scenario: Usuario enmascarado en la telemetría

- **WHEN** la traza se envía a Langfuse con el identificador del usuario que originó el turno
- **THEN** el valor visible en Langfuse es el resultado de la función `mask` (nunca el identificador en claro del usuario)

### Requirement: Flags de adjuntos sospechosos en la traza

Cuando el turno incluya un adjunto, la traza SHALL registrar como metadata el resultado del escaneo (N2/N3) y el flag de la heurística de inyección del ANEXO §4.3 (`design/ANEXO-ATTACHMENTS.md`), referenciando el `scan_result` del adjunto sin duplicar su contenido.

#### Scenario: Turno con adjunto flageado por heurística de inyección

- **WHEN** el escaneo del adjunto (`d14-attachments`) marca un flag de inyección
- **THEN** la traza del turno incluye ese flag como metadata, visible junto al resto de la decisión de gobernanza del turno

#### Scenario: Turno con adjunto sin hallazgos

- **WHEN** el escaneo del adjunto no encuentra N2, N3 ni heurística de inyección
- **THEN** la traza registra el resultado limpio del escaneo, sin flags activos

### Requirement: Naming conventions enlazables desde la consola admin

Los identificadores de traza, sesión y las etiquetas (tags) usadas por el adapter SHALL seguir una convención de nombres estable y documentada, de forma que `d19-admin-operacion` pueda construir enlaces directos a la vista nativa de Langfuse de un turno, una sesión o un usuario sin llamar a ninguna API adicional del adapter ni reimplementar un dashboard.

#### Scenario: Admin abre la traza de un turno desde la consola

- **WHEN** el Admin tiene el `trace_id` de un turno mostrado en la consola admin
- **THEN** existe una convención de URL documentada que, aplicada a ese `trace_id`, abre directamente la traza correspondiente en Langfuse

#### Scenario: Admin abre el histórico de una sesión desde la consola

- **WHEN** el Admin tiene el `session_id` de una Sesión mostrado en la consola admin
- **THEN** existe una convención de URL documentada que, aplicada a ese `session_id`, abre directamente la vista de sesión en Langfuse con todos sus turnos
