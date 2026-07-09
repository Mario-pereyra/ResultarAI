# quota-releases — Delta Spec (d16-cuotas-liberaciones)

## ADDED Requirements

### Requirement: Solicitud de Liberación desde el bloqueo

Un usuario bloqueado al 100% de un alcance de Cuota SHALL poder crear una **Liberación** (solicitud) con un motivo breve obligatorio. La solicitud SHALL registrar el solicitante, el alcance bloqueado, el consumo actual y el motivo, con estado inicial `pendiente`. Al crearse SHALL emitir un `AuditEvent` (`QUOTA_RELEASE_REQUESTED`) y una notificación `quota_release_requested` a través del contrato de emisión de `d12-notificaciones` (destinatario = Admin del tenant). Conforme a `design/FLUJOS.md` Flujo E y `design/FUNCIONALIDADES.md` §4/§11.

#### Scenario: El bloqueo permite solicitar con motivo

- **WHEN** un usuario con estado `QUOTA` pulsa "Solicitar liberación" y agrega un motivo breve
- **THEN** se crea una Liberación en estado `pendiente` con solicitante, alcance bloqueado, consumo actual y motivo, se emite el `AuditEvent` `QUOTA_RELEASE_REQUESTED` y se notifica a cada Admin del tenant vía `quota_release_requested`

#### Scenario: Motivo obligatorio

- **WHEN** un usuario intenta crear una Liberación sin motivo
- **THEN** la solicitud se rechaza con un error accionable y no se crea ninguna Liberación ni notificación

### Requirement: Decisión del Admin sobre la Liberación

Un Admin SHALL resolver una Liberación `pendiente` aprobándola o denegándola. La aprobación SHALL declarar el tipo de ampliación —`puntual` o `permanente`— y el monto adicional. La denegación SHALL exigir un comentario obligatorio (el solicitante lo ve). Toda resolución SHALL emitir un `AuditEvent` (`QUOTA_RELEASE_APPROVED` o `QUOTA_RELEASE_DENIED`) y una notificación `quota_release_resolved` al solicitante vía `d12-notificaciones`. Conforme a `design/VISTAS/07-admin-operacion.md` vista 33.

#### Scenario: Aprobación puntual con monto adicional

- **WHEN** un Admin aprueba una Liberación como `puntual` con un monto adicional
- **THEN** la Liberación pasa a `concedida`, se registra el tipo, el monto y su vencimiento, se emite `QUOTA_RELEASE_APPROVED` y el solicitante recibe `quota_release_resolved` con la decisión

#### Scenario: Denegación exige comentario

- **WHEN** un Admin deniega una Liberación
- **THEN** el comentario es obligatorio; sin él la denegación se rechaza; con él la Liberación pasa a `denegada`, se emite `QUOTA_RELEASE_DENIED` y el solicitante recibe `quota_release_resolved` con el comentario del Admin

### Requirement: Alcance y vencimiento de la ampliación

Una Liberación aprobada SHALL aplicarse al alcance de Cuota que estaba bloqueado (usuario o grupo). Una ampliación `puntual` SHALL tener vencimiento (fin del período vigente en v1); una ampliación `permanente` SHALL elevar el límite del alcance sin vencimiento hasta un cambio de configuración posterior. Al vencer una ampliación `puntual`, el límite del alcance SHALL volver a su valor normal sin avisos adicionales.

#### Scenario: Ampliación puntual vence al fin del período

- **WHEN** una ampliación `puntual` fue concedida y llega el fin de su período de vigencia
- **THEN** el límite del alcance vuelve a su valor normal, sin notificación adicional, y el usuario queda sujeto de nuevo a su Cuota base

#### Scenario: Ampliación permanente eleva el límite hasta nuevo cambio

- **WHEN** una ampliación `permanente` fue concedida sobre un alcance
- **THEN** el límite del alcance queda elevado en el monto adicional sin vencimiento, y solo un cambio de configuración posterior lo modifica

### Requirement: Desbloqueo inmediato tras la aprobación

Aprobar una Liberación SHALL desbloquear al usuario al instante, sin re-login: la siguiente evaluación de Cuota previa a la llamada al modelo SHALL contar con el monto adicional ya aplicado (regla dura de `CLAUDE.md`: la Cuota se evalúa ANTES de cada llamada). Conforme a `design/VISTAS/07-admin-operacion.md` vista 33 (interacciones).

#### Scenario: El próximo turno pasa el check tras aprobar

- **WHEN** un Admin aprueba una Liberación y el usuario, antes bloqueado, envía un nuevo turno
- **THEN** la evaluación de Cuota previa a la llamada al modelo ya considera el monto adicional, el turno se autoriza y el usuario no necesitó re-autenticarse

### Requirement: Resolución única bajo Admins concurrentes

Una Liberación SHALL resolverse una sola vez. Cuando dos Admin intentan resolver la misma solicitud, el segundo intento SHALL rechazarse con un conflicto explícito ("ya resuelta por …"), sin sobrescribir la resolución del primero ni emitir una segunda notificación al solicitante.

#### Scenario: Dos Admin resuelven la misma solicitud

- **WHEN** dos Admin resuelven la misma Liberación `pendiente` casi al mismo tiempo
- **THEN** solo la primera resolución se aplica; la segunda recibe un conflicto ("ya resuelta por …"), no altera la decisión, y el solicitante recibe una única notificación `quota_release_resolved`

### Requirement: Re-solicitud tras agotar o denegar una Liberación

Un usuario SHALL poder crear una nueva Liberación tras agotar una ampliación concedida o tras una denegación. La nueva solicitud SHALL referenciar la Liberación anterior del mismo período (por ejemplo, "2.ª solicitud del mes"). Conforme a `design/VISTAS/07-admin-operacion.md` vista 33 (casos borde).

#### Scenario: Segunda solicitud referencia la anterior

- **WHEN** un usuario agota la ampliación puntual concedida y vuelve a bloquearse en el mismo período
- **THEN** puede crear una nueva Liberación que referencia la anterior del período, y el Admin la ve identificada como solicitud subsiguiente

### Requirement: Auditoría append-only de toda la cadena de Liberación

Cada paso de la cadena —solicitud, aprobación y denegación— SHALL producir su propio `AuditEvent` en el Audit Log append-only (`a03-core-gobernanza`). Esos eventos SHALL ser visibles para el usuario en su auditoría personal (`d18-mi-espacio`) y para el Admin en el audit log global (`d19-admin-operacion`). Un evento de la cadena NO SHALL poder editarse ni borrarse.

#### Scenario: Cada paso deja su evento inmutable

- **WHEN** una Liberación recorre solicitud y luego aprobación (o denegación)
- **THEN** existen `AuditEvent` independientes para cada paso (`QUOTA_RELEASE_REQUESTED` y `QUOTA_RELEASE_APPROVED` o `_DENIED`), ninguno se edita ni borra, y todos referencian al solicitante y al alcance afectado

#### Scenario: El solicitante reconstruye su propia cadena

- **WHEN** el usuario solicitante consulta su auditoría personal
- **THEN** ve los eventos de sus propias Liberaciones (solicitud y resolución) y no los de otros usuarios
