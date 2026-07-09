# context-compaction Specification

## Purpose
TBD - created by archiving change b06-runtime-grafos. Update Purpose after archive.
## Requirements
### Requirement: Compaction al 80% de la ventana de contexto, en frontera de turno

El runtime SHALL evaluar, únicamente en la frontera de turno (al iniciar el siguiente turno, nunca a mitad de uno en curso), si el contexto acumulado de la sesión alcanza o supera el 80% de la ventana de contexto del perfil de modelo activo de esa sesión. Si lo alcanza, dispara la compaction antes de procesar el nuevo turno. Disparar la compaction SHALL pasar por el Policy Gate como cualquier otro paso relevante del grafo (`agent-runtime`).

#### Scenario: Turno que cruza el 80% dispara compaction en la frontera siguiente

- **WHEN** el contexto acumulado tras completar un turno alcanza el 80% de la ventana de contexto del perfil de modelo activo
- **THEN** el runtime dispara la compaction al iniciar el siguiente turno, nunca durante el turno que cruzó el umbral

#### Scenario: Disparar la compaction pasa por el Policy Gate

- **WHEN** el runtime decide disparar la compaction en la frontera de turno
- **THEN** construye un `ActionRequest` para la operación de compaction, `PolicyPort` evalúa y devuelve `allow`, y el `AuditEvent` resultante registra la compaction como paso auditado

### Requirement: La compaction ocurre una sola vez por sesión

Una vez que una sesión fue compactada, el runtime SHALL no volver a disparar la compaction para esa misma sesión, aunque el contexto vuelva a alcanzar el 80% de la ventana en un turno posterior.

#### Scenario: Sesión ya compactada no vuelve a compactar

- **WHEN** una sesión que ya fue compactada alcanza nuevamente el 80% de su ventana de contexto en un turno posterior
- **THEN** el runtime no dispara una segunda compaction para esa sesión, y emite un evento trazable declarando que el umbral se alcanzó sin re-disparar

### Requirement: El resumen de compaction no reescribe mensajes previos

La compaction SHALL producir el contenido resumido como un mensaje o evento nuevo, append-only. Ningún mensaje previo de la sesión se modifica ni se elimina, conforme al principio branch-never-rewrite.

#### Scenario: Mensajes originales permanecen intactos tras compactar

- **WHEN** se ejecuta la compaction sobre una sesión
- **THEN** los mensajes previos conservan su contenido y `parent_id` originales, y el resumen se agrega como un mensaje nuevo sin sobrescribir ninguno existente

### Requirement: Indicador de compaction emitido

El runtime SHALL emitir, vía `TracePort`, un indicador que declare que la sesión fue compactada, incluyendo el rango de contenido resumido, consumible por la UI del chat (`d13-chat-conversacion`).

#### Scenario: La sesión compactada expone su indicador

- **WHEN** una compaction se completa
- **THEN** el runtime emite un evento trazable con `compacted=true` y el rango de mensajes resumidos, disponible para el turno siguiente

### Requirement: Contenido compactado se puede repedir como mensaje nuevo

El usuario SHALL poder solicitar contenido que fue compactado (por ejemplo, releer un adjunto). El runtime SHALL tratar esa solicitud como un mensaje nuevo de la sesión, nunca como una reversión de la compaction ya realizada.

#### Scenario: Repetir contenido compactado no revierte la compaction

- **WHEN** el usuario pide releer un adjunto cuyo contenido fue resumido por la compaction
- **THEN** el runtime procesa la solicitud como un mensaje nuevo append-only, y el resumen de la compaction permanece sin modificarse

