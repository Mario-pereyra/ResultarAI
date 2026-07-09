# hitl-approvals — Delta Spec (d17-hitl-aprobaciones)

> Vistas normativas: `design/VISTAS/05-hitl-validacion.md` (vistas 20/21/22 — se ignoran 27/28/29, Etapa P) · `design/FUNCIONALIDADES.md` §8 y §3 · `design/FLUJOS.md` Flujo C pasos 6–8 · `design/DESIGN-SYSTEM.md` §8.14 y §10. Todo lo aquí especificado es genérico: el "contexto de destino" es `tenant · environment · agent · skill · tool` del `ActionRequest` (`a03`), nunca cliente/ambiente Protheus.

## ADDED Requirements

### Requirement: La Tarjeta HITL materializa cada efecto escalate_hitl de una Tool de escritura

Cuando el Policy Gate devuelve `escalate_hitl` para una Tool de `operation_type: write` (`c09`), el sistema SHALL crear una **Solicitud de aprobación** (`ApprovalRequest`) en estado `pending` y presentarla como **Tarjeta HITL**. La Tarjeta muestra: qué se va a ejecutar en lenguaje claro, el payload completo, el contexto de destino (`tenant`, `environment`, `agent`, `skill`, `tool`), el nivel de riesgo y la expiración visible, con botones Aprobar/Rechazar. La Tool escalada MUST NOT ejecutarse mientras no exista una decisión humana (regla dura 4). Cada `ApprovalRequest` referencia el `AuditEvent` de la decisión `escalate_hitl` que la originó.

#### Scenario: Escritura escalada crea Tarjeta HITL pendiente

- **WHEN** una Skill invoca una Tool `operation_type: write` y el Policy Gate devuelve `escalate_hitl` (con su `AuditEvent`)
- **THEN** el sistema crea una `ApprovalRequest` en estado `pending`, presenta la Tarjeta HITL con payload completo, contexto de destino, riesgo y expiración, y la Tool NO se ejecuta (el cliente MCP no emite `tools/call`)

#### Scenario: Sin decisión humana no hay ejecución (regla dura)

- **WHEN** una `ApprovalRequest` originada por una decisión `escalate_hitl` permanece en estado `pending`
- **THEN** el runtime no emite `tools/call` y ningún sistema externo cambia hasta que exista una decisión (allow tras aprobación o deny tras rechazo/expiración)

### Requirement: La Tarjeta HITL aparece inline en el chat o pausa el flujo

La Tarjeta HITL originada por `escalate_hitl` SHALL presentarse inline en la sesión de chat (`d13`) cuando la escritura surge de una conversación, y SHALL mantener pausado el turno del runtime (`b06`) que la disparó hasta que exista decisión. El solicitante ve la MISMA Tarjeta en modo lectura (sin botones de decisión); el aprobador la ve con botones (`design/FLUJOS.md` Flujo C pasos 6–8).

#### Scenario: Tarjeta inline en el chat detiene el turno

- **WHEN** una escritura escalada a HITL surge dentro de una sesión de chat y el Policy Gate devolvió `escalate_hitl`
- **THEN** la Tarjeta HITL aparece inline en el chat en modo lectura para el solicitante, el turno queda "en espera de aprobación humana" (`b06`) y no se ejecuta nada hasta la decisión (allow tras aprobación / deny tras rechazo)

#### Scenario: El solicitante ve la tarjeta sin botones de decisión

- **WHEN** el solicitante abre su `ApprovalRequest` pendiente (efecto `escalate_hitl`) desde su chat
- **THEN** la ve en modo lectura con estado y expiración, sin botones Aprobar/Rechazar, y sigue el resultado (allow/deny) desde la misma tarjeta

### Requirement: Contenido autosuficiente de la Tarjeta HITL

La Tarjeta HITL SHALL ser autosuficiente: el aprobador decide sin navegar a otro lado (vista 21, `21-aprobacion-detalle.html`). Muestra el payload formateado legible SIEMPRE visible más el payload crudo colapsable, la clasificación de riesgo con su porqué (bullets generados por reglas, nunca por el LLM), la reversibilidad, la expiración en texto relativo y absoluto, y el registro de auditoría con la identidad del decisor. El aprobador NO edita el payload; si algo está mal, rechaza con razón y el agente propone de nuevo.

#### Scenario: La tarjeta expone payload completo y clasificación de riesgo

- **WHEN** un aprobador abre el detalle de una `ApprovalRequest` originada por `escalate_hitl`
- **THEN** ve el payload completo (formateado + crudo colapsable), el contexto de destino, el nivel de riesgo con su justificación por reglas, la reversibilidad y la expiración relativa+absoluta, sin poder editar el payload

### Requirement: Comentario obligatorio del aprobador en acciones críticas

Cuando la `PolicyDecision` de efecto `escalate_hitl` declara `requires_approver_comment = true` (riesgo `critical`, contrato de `a03`), el sistema SHALL exigir un comentario del aprobador antes de habilitar "Aprobar": el botón permanece deshabilitado con el motivo hasta que exista texto, y al confirmar exige confirmación reforzada (tipear la palabra de confirmación; Esc jamás confirma). Rechazar SHALL exigir comentario en todos los niveles de riesgo.

#### Scenario: Crítica sin comentario no permite aprobar

- **WHEN** una `ApprovalRequest` de riesgo `critical` (`escalate_hitl`, `requires_approver_comment = true`) se intenta aprobar sin comentario
- **THEN** "Aprobar" permanece deshabilitado con el motivo visible y la escritura no se ejecuta (sigue pendiente)

#### Scenario: Crítica con comentario y confirmación reforzada se aprueba

- **WHEN** el aprobador escribe el comentario obligatorio y completa la confirmación reforzada de una `ApprovalRequest` `critical` (`escalate_hitl`)
- **THEN** la decisión queda registrada con el comentario, el resultado es allow tras aprobación y la ejecución se reanuda

#### Scenario: Rechazo exige comentario en todo nivel de riesgo

- **WHEN** un aprobador rechaza cualquier `ApprovalRequest` (`escalate_hitl`) sin comentario
- **THEN** el rechazo no se registra hasta que haya comentario; con comentario, el resultado es deny tras rechazo y no hay ejecución

### Requirement: Segunda aprobación de 4 ojos en acciones irreversibles

Cuando la `PolicyDecision` declara `requires_second_approval = true` (crítica irreversible, contrato de `a03`), la primera aprobación SHALL llevar la `ApprovalRequest` al estado `awaiting_second_approval` (**Segunda aprobación** pendiente, "esperando segunda aprobación (1/2)" visible) y SHALL exigir una segunda aprobación de una persona distinta antes de ejecutar. El solicitante y el primer firmante NO pueden dar la segunda aprobación; el sistema RECHAZA el intento del mismo usuario. Ambas firmas quedan auditadas.

#### Scenario: Primera firma deja la solicitud esperando segunda aprobación

- **WHEN** un aprobador da la primera firma de una `ApprovalRequest` irreversible (`escalate_hitl`, `requires_second_approval = true`)
- **THEN** la `ApprovalRequest` pasa a `awaiting_second_approval` con el estado "esperando segunda aprobación (1/2)" visible y la Tool aún no se ejecuta

#### Scenario: Segunda firma de otra persona habilita la ejecución

- **WHEN** una persona distinta del solicitante y del primer firmante da la segunda aprobación de esa `ApprovalRequest` (`escalate_hitl`)
- **THEN** la `ApprovalRequest` pasa a `approved` con ambas firmas auditadas, el resultado es allow tras aprobación y la ejecución se reanuda

#### Scenario: El solicitante o primer firmante como segundo aprobador es rechazado

- **WHEN** el solicitante o el primer firmante intenta dar la segunda aprobación de su propia `ApprovalRequest` irreversible (`escalate_hitl`)
- **THEN** el sistema RECHAZA la acción (un mismo usuario no puede ser su propio segundo aprobador), la `ApprovalRequest` permanece en `awaiting_second_approval` y la escritura no se ejecuta

### Requirement: Expiración como rechazo automático auditado

Cada `ApprovalRequest` SHALL tener una expiración (`expires_at`) con tiempo de vida configurable, visible en la Tarjeta HITL. Al vencer sin decisión, el sistema SHALL transicionarla a `expired`, tratándola como rechazo automático (deny efectivo, sin ejecución) y emitiendo el `AuditEvent` de expiración. Una `ApprovalRequest` expirada no es aprobable.

#### Scenario: Vencimiento sin decisión es rechazo auditado

- **WHEN** una `ApprovalRequest` originada por `escalate_hitl` alcanza su `expires_at` sin aprobación ni rechazo
- **THEN** pasa a `expired`, se trata como deny (la escritura nunca se ejecuta) y se emite un `AuditEvent` de expiración inmutable

#### Scenario: Una solicitud expirada no es aprobable

- **WHEN** un aprobador intenta aprobar una `ApprovalRequest` en estado `expired` (originada por `escalate_hitl`)
- **THEN** la acción se rechaza (ya resuelta como deny por expiración) y no hay ejecución

### Requirement: Notificaciones del ciclo de aprobación

El sistema SHALL emitir la notificación `hitl_approval_pending` (registrada en `d12`) al crear una `ApprovalRequest` y al pasarla a `awaiting_second_approval`, dirigida a los aprobadores correspondientes —incluidas las segundas aprobaciones asignables—, con deep link a la Tarjeta HITL, contexto de destino y riesgo; y un aviso previo a la expiración a esos aprobadores. Al expirar, SHALL emitir `hitl_card_expired`.

#### Scenario: Nueva aprobación notifica a los aprobadores

- **WHEN** se crea una `ApprovalRequest` por una decisión `escalate_hitl`
- **THEN** se emite `hitl_approval_pending` a los aprobadores con deep link a la Tarjeta HITL, y la escritura sigue pendiente hasta la decisión (allow/deny)

#### Scenario: Aviso previo y notificación de expiración

- **WHEN** una `ApprovalRequest` pendiente (`escalate_hitl`) se acerca a su `expires_at` y luego vence
- **THEN** los aprobadores reciben un aviso previo antes del vencimiento y, al expirar, una notificación `hitl_card_expired` coherente con el rechazo automático auditado (deny)

### Requirement: Bandeja de aprobaciones

El sistema SHALL ofrecer una Bandeja de aprobaciones (vista 20, `20-aprobaciones-cola.html`) que lista las `ApprovalRequest` pendientes propias y las segundas aprobaciones asignables, ordenadas por expiración ascendente, mostrando riesgo, contexto de destino, solicitante y countdown de expiración, con un tag "esperando segunda aprobación" cuando aplique. La sección SHALL respetar la matriz de visibilidad: no se renderiza (ni su ítem de sidebar) para roles sin capacidad **aprobador** (Funcional).

#### Scenario: La bandeja lista las aprobaciones pendientes

- **WHEN** un aprobador abre la Bandeja de aprobaciones
- **THEN** ve las `ApprovalRequest` en estado `pending`/`awaiting_second_approval` (originadas por `escalate_hitl`) ordenadas por expiración, cada una con riesgo, contexto de destino y countdown, y "Revisar" abre el detalle (vista 21) donde decidirá (allow tras aprobación / deny tras rechazo)

#### Scenario: La sección no existe para roles sin capacidad aprobador

- **WHEN** un usuario sin capacidad aprobador (por ejemplo, un Funcional) navega la aplicación
- **THEN** la sección Aprobaciones no se renderiza (ni en el sidebar); solo sigue sus propias solicitudes escaladas (`escalate_hitl`) desde la Tarjeta HITL embebida en su chat

#### Scenario: Otra persona resuelve primero (concurrencia)

- **WHEN** dos aprobadores tienen abierta la misma `ApprovalRequest` (`escalate_hitl`) y una la resuelve (allow tras aprobación o deny tras rechazo)
- **THEN** la otra vista se actualiza a "resuelta" anunciándolo por `aria-live`, y una segunda decisión sobre la misma solicitud ya resuelta se rechaza sin ejecutar de nuevo

### Requirement: Historial de decisiones

El sistema SHALL ofrecer un Historial de decisiones (vista 22, `22-aprobaciones-historial.html`) que registra, por cada `ApprovalRequest` resuelta: quién decidió, cuándo, con qué comentario, el payload, la decisión (`APROBADA`, `APROBADA ×2`, `RECHAZADA`, `EXPIRADA`) y el resultado de ejecución. El historial es append-only e inmutable. El Técnico aprobador ve "Mis decisiones"; el Admin además "Todas" con export.

#### Scenario: Decisión resuelta queda en el historial con su rastro

- **WHEN** una `ApprovalRequest` (`escalate_hitl`) se resuelve como aprobada (allow), rechazada (deny) o expirada (deny)
- **THEN** aparece en el Historial de decisiones con quién/cuándo/comentario/payload y el resultado de ejecución, sin poder editarse ni borrarse (append-only)

### Requirement: Reanudación al aprobar y rechazo al flujo

La decisión humana registrada es la autorización que habilita o cancela la ejecución del paso previamente retenido por `escalate_hitl`. Al aprobarse (una firma, o dos en irreversibles), el sistema SHALL reanudar la ejecución emitiendo un evento hacia el runtime (`b06`) / la Tool (`c09`), que ahora ejecuta la escritura (`tools/call`) y registra su resultado. Al rechazarse, el sistema SHALL entregar el rechazo con su razón al flujo, que continúa sin ejecutar la escritura.

#### Scenario: Aprobar reanuda la ejecución de la escritura

- **WHEN** una `ApprovalRequest` originada por `escalate_hitl` pasa a `approved`
- **THEN** el runtime reanuda el paso retenido, el cliente MCP emite el `tools/call` antes retenido (allow tras aprobación) y el resultado de ejecución se registra en la Tarjeta HITL y en el historial

#### Scenario: Rechazar entrega el rechazo con razón al flujo

- **WHEN** una `ApprovalRequest` (`escalate_hitl`) pasa a `rejected` con su comentario obligatorio
- **THEN** el flujo recibe el rechazo con su razón (deny tras rechazo), la escritura no se ejecuta y no se emite `tools/call`

### Requirement: El kill-switch de agente congela las Tarjetas HITL pendientes

Cuando un kill-switch de agente (`d20`) suspende un Agent, el sistema SHALL congelar sus `ApprovalRequest` pendientes (`pending`/`awaiting_second_approval`) marcándolas "agente suspendido": no son aprobables mientras el Agent esté suspendido, preservando la decisión y la auditoría hasta su reactivación o expiración.

#### Scenario: Kill-switch congela las aprobaciones pendientes del agente

- **WHEN** un kill-switch (`d20`) suspende un Agent que tiene `ApprovalRequest` pendientes originadas por `escalate_hitl`
- **THEN** esas Tarjetas HITL se marcan "agente suspendido", no son aprobables (la escritura no se ejecuta) mientras dure la suspensión, y el cambio de estado queda auditado

### Requirement: Auditoría integral del ciclo de vida

Cada transición del ciclo de vida de una `ApprovalRequest` —creada, aprobada (cada firma), rechazada, expirada y congelada por kill-switch— SHALL emitir un `AuditEvent` inmutable (append-only; prohibido UPDATE/DELETE), coherente con el `AuditEvent` de la decisión `escalate_hitl` que la originó.

#### Scenario: Cada transición deja un AuditEvent inmutable

- **WHEN** una `ApprovalRequest` (`escalate_hitl`) transita por creada → aprobada / rechazada / expirada
- **THEN** cada transición emite exactamente un `AuditEvent` inmutable que referencia la decisión original y su resultado (allow tras aprobación / deny tras rechazo o expiración)

### Requirement: Accesibilidad AA de la Tarjeta HITL

La Tarjeta HITL —componente crítico (DESIGN-SYSTEM §8.14 y §10)— SHALL ser operable por teclado y lector de pantalla (WCAG 2.1 AA): `section` con `aria-labelledby`, orden de tabulación = orden visual, riesgo comunicado por texto además de color, expiración en texto absoluto y relativo, y el foco inicial NUNCA en "Aprobar" (anti-aprobación accidental). Los cambios de estado por concurrencia se anuncian por `aria-live`.

#### Scenario: La tarjeta es operable por teclado y lector, con foco fuera de Aprobar

- **WHEN** un aprobador abre por teclado y lector de pantalla una Tarjeta HITL originada por `escalate_hitl`
- **THEN** puede leer y decidir sin mouse, el riesgo se anuncia como texto+color, la expiración se lee en absoluto+relativo, y el foco inicial está en el cuerpo —jamás en "Aprobar"— antes de resolver (allow tras aprobación / deny tras rechazo)

### Requirement: Móvil primera clase

La Tarjeta HITL, la Bandeja y el Historial SHALL ser responsive de primera clase (decisión D4 del design, DESIGN-SYSTEM §11): en móvil la meta va a una columna, el payload con scroll, los botones a ancho completo con el primario abajo (zona del pulgar) y la tabla de la cola pasa a cards. Aprobar desde el celular es caso de uso real.

#### Scenario: Aprobar desde móvil funciona

- **WHEN** un aprobador resuelve en un viewport móvil (380 px) una `ApprovalRequest` originada por `escalate_hitl`
- **THEN** la Tarjeta HITL es plenamente funcional (payload con scroll, botones full-width, primario abajo) y la decisión (allow tras aprobación / deny tras rechazo) se registra igual que en escritorio
