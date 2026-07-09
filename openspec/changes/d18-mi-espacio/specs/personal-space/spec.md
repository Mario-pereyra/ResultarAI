# personal-space — Delta Spec (d18-mi-espacio)

## ADDED Requirements

### Requirement: Ownership estricto derivado de la sesión

Todo endpoint de `personal-space` (Mi auditoría, Mis adjuntos, Configuración personal) SHALL derivar el `user_id` exclusivamente de la sesión autenticada (mismo contrato que `authentication` de `d11-identidad-acceso`). El sistema SHALL ignorar cualquier identificador de usuario recibido en el cuerpo, la query string o los parámetros de ruta de la petición, y SHALL denegar y auditar todo intento de resolver datos de un `user_id` distinto al de la sesión.

#### Scenario: Un parámetro de usuario ajeno en la URL es ignorado

- **WHEN** la sesión del usuario "lucia" solicita `GET /me/audit-events?user_id=carlos`
- **THEN** el sistema resuelve la consulta con el `user_id` de la sesión de "lucia", ignora el parámetro `user_id=carlos`, y la respuesta contiene únicamente eventos de "lucia"

#### Scenario: Intento de acceder a la auditoría o los adjuntos de otro usuario es denegado y auditado

- **WHEN** la sesión de "lucia" invoca un endpoint de `personal-space` (auditoría, adjuntos o descarga) con una referencia explícita al recurso de otro usuario (por ejemplo el `id` de un adjunto cuyo `uploaded_by` no es "lucia")
- **THEN** el sistema responde 403 sin exponer ningún dato del recurso ajeno, y registra un `AuditEvent` que identifica al usuario que intentó el acceso, el recurso solicitado y el resultado denegado

### Requirement: Mi auditoría — lectura filtrada del audit log propio

El sistema SHALL exponer una vista de solo lectura ("Mi auditoría", `design/VISTAS/06-mi-espacio.md` vista 25, ruta `/espacio/auditoria`) que consulta el Audit Log (`AuditEvent` de `audit-log` en `a03-core-gobernanza`) filtrado estrictamente por el `user_id` de la sesión. El catálogo mínimo de eventos visibles SHALL incluir: ejecuciones de tools propias, aprobaciones y rechazos HITL propios, confirmaciones N2 propias ("confirmo que son datos de prueba"), aceptaciones del acuerdo de uso propias, solicitudes de liberación de cuota propias y su resolución, inicios y cierres de sesión propios (exitosos y fallidos), cambios de memoria propios, y subidas de adjuntos propias.

#### Scenario: Un usuario ve solo sus propios eventos

- **WHEN** el usuario "lucia" abre Mi auditoría
- **THEN** la lista muestra exclusivamente eventos cuyo `user_id` es el de "lucia", incluyendo, si existen, sus tool calls, sus decisiones HITL, sus confirmaciones N2, su aceptación del acuerdo de uso y sus subidas de adjuntos, y ningún evento de otro usuario aparece en el resultado

#### Scenario: Mi auditoría no ofrece ninguna acción de escritura

- **WHEN** el usuario navega Mi auditoría
- **THEN** ninguna fila ofrece edición o borrado del evento (coherente con el invariante append-only del Audit Log); la única navegación permitida es hacia la tarjeta HITL resuelta que originó un evento de tipo aprobación

### Requirement: Mi auditoría — paginación y filtros server-side

El listado de Mi auditoría SHALL paginarse en el servidor y SHALL admitir filtro por tipo de evento y por rango de fecha, sin cargar el historial completo del usuario en una sola respuesta.

#### Scenario: Filtrar por tipo reconsulta y reinicia la paginación

- **WHEN** un usuario con 142 eventos selecciona el filtro de tipo `CUOTA`
- **THEN** el sistema reconsulta el servidor con ese filtro, vuelve a la página 1, y el contador de eventos totales refleja solo los eventos que coinciden con el filtro activo

#### Scenario: Filtro por fecha sin resultados

- **WHEN** un usuario filtra por un rango de fecha sin eventos propios
- **THEN** el sistema responde una página vacía con el total en cero, sin error

### Requirement: Mis adjuntos — listado propio dentro de retención

El sistema SHALL exponer un listado ("Mis adjuntos", `/espacio/adjuntos`) de los adjuntos cuyo `uploaded_by` es el `user_id` de la sesión y cuyo binario todavía está dentro de la retención configurada por instancia (default 90 días, `attachment-storage` de `b04-persistencia-postgres`). Cada fila SHALL mostrar como mínimo `original_name`, fecha de subida, tamaño, la sesión/conversación de origen y el estado de escaneo derivado de `scan_result` (`listo` / `bloqueado` por N3 / `advertencia N2 confirmada`).

#### Scenario: Un usuario ve sus adjuntos vigentes con su estado de escaneo

- **WHEN** el usuario "lucia" abre Mis adjuntos y tiene 3 archivos subidos dentro de la retención vigente
- **THEN** la lista muestra los 3 archivos con nombre, fecha, tamaño, sesión de origen y estado de escaneo (`ready`, `blocked` o advertencia N2 confirmada según su `scan_result`), y ningún adjunto de otro usuario aparece

#### Scenario: Un adjunto purgado por retención desaparece del listado sin romper la conversación

- **WHEN** un adjunto propio supera la retención configurada y el sistema purga su binario y su `full_text` (`attachment-storage` de `b04`)
- **THEN** el adjunto deja de listarse en Mis adjuntos como vigente (se muestra como expirado o se omite, según config de instancia), mientras que la conversación que lo usó permanece íntegra porque su `inserted_text` sigue existiendo con la sesión

### Requirement: Mis adjuntos — descarga auditada reutilizando el pipeline de attachments

La descarga de un adjunto propio desde Mis adjuntos SHALL reutilizar el endpoint de descarga auditada ya definido por `attachments-pipeline` de `d14-attachments` (acceso restringido a dueño y Admin, nunca URL pública) sin redefinir su mecanismo. Toda descarga ejecutada desde Mis adjuntos SHALL emitir su propio `AuditEvent`, visible a su vez en Mi auditoría del mismo usuario.

#### Scenario: Descargar un adjunto propio queda auditado y visible en Mi auditoría

- **WHEN** el usuario "lucia" descarga uno de sus propios adjuntos desde Mis adjuntos
- **THEN** el sistema entrega el archivo a través del endpoint auditado de `d14-attachments`, registra un `AuditEvent` de descarga con `user_id` de "lucia" y el `id` del adjunto, y ese evento aparece posteriormente en la Mi auditoría de "lucia"

### Requirement: Configuración personal — preferencias de tema e idioma persistidas por usuario

El sistema SHALL permitir a todo usuario configurar su tema (oscuro / claro / sistema) y su idioma de interfaz desde Configuración personal (`design/VISTAS/06-mi-espacio.md` vista 26, ruta `/espacio/configuracion`), persistidas por cuenta. El idioma `es-BO` SHALL estar disponible y activo; el idioma `pt-BR` SHALL aparecer en el selector mostrado como preparado pero deshabilitado hasta que la instancia lo active (Etapa P).

#### Scenario: Cambiar el tema aplica de inmediato y persiste

- **WHEN** un usuario selecciona el tema "Claro" en Configuración personal
- **THEN** la interfaz cambia de inmediato sin esperar el guardado, y al guardar la preferencia queda asociada a su cuenta para futuras sesiones

#### Scenario: pt-BR aparece deshabilitado hasta activación de instancia

- **WHEN** un usuario abre el selector de idioma en una instancia donde `pt-BR` no está activado
- **THEN** la opción `pt-BR` se muestra en el selector mostrando su nombre nativo, deshabilitada para selección, y `es-BO` es el único idioma seleccionable

### Requirement: Configuración personal — gestión de TOTP propio conforme al contrato de d11

Configuración personal SHALL exponer, para roles Técnico y Funcional, la activación, desactivación y regeneración de códigos de respaldo de TOTP reutilizando el flujo de enrolamiento guiado y la mecánica ya especificados por `authentication` de `d11-identidad-acceso` (QR, clave manual Base32, códigos de respaldo). Para el rol Admin, la opción "Desactivar TOTP" SHALL no renderizarse, y en su lugar SHALL mostrarse una nota explicando que TOTP es obligatorio para su rol.

#### Scenario: Un usuario Técnico o Funcional activa TOTP desde Configuración personal

- **WHEN** un usuario con rol Técnico o Funcional sin TOTP enrolado hace clic en "Activar" en Configuración personal
- **THEN** el sistema ejecuta el mismo flujo guiado de enrolamiento de `d11` (QR + clave manual + confirmación con código válido) y, al completarse, el estado pasa a ACTIVO y los logins futuros de esa cuenta exigen el segundo paso TOTP

#### Scenario: Un usuario Admin no puede desactivar TOTP desde Configuración personal

- **WHEN** una cuenta con rol Admin abre el panel de TOTP en Configuración personal
- **THEN** el botón "Desactivar TOTP" no se renderiza, y en su lugar se muestra una nota indicando que TOTP es obligatorio para el rol Admin

#### Scenario: Regenerar códigos de respaldo invalida los anteriores

- **WHEN** un usuario con TOTP activo regenera sus códigos de respaldo desde Configuración personal
- **THEN** el sistema invalida todos los códigos de respaldo anteriores, muestra los 10 nuevos códigos una única vez, y registra el evento en Mi auditoría

### Requirement: Configuración personal — cambio de contraseña propio conforme al contrato de d11

Configuración personal SHALL exponer el cambio de la contraseña propia reutilizando la política de contraseñas y la verificación Argon2id ya especificadas por `authentication` de `d11-identidad-acceso`, exigiendo la contraseña actual.

#### Scenario: Cambio de contraseña exitoso revoca las otras sesiones

- **WHEN** un usuario autenticado envía su contraseña actual correcta y una nueva contraseña que cumple la política vigente desde Configuración personal
- **THEN** el sistema actualiza el hash Argon2id, revoca las demás sesiones activas de ese usuario salvo la que originó el cambio, y muestra la confirmación de éxito

#### Scenario: Cambio de contraseña rechazado por incumplir la política no pierde el resto del formulario

- **WHEN** un usuario envía una nueva contraseña que no cumple la política vigente desde Configuración personal
- **THEN** el sistema rechaza el cambio, devuelve el detalle accionable de qué requisito falta, y no aplica ninguna modificación

### Requirement: Configuración personal — sesiones activas propias con cierre remoto

Configuración personal SHALL listar las sesiones activas propias del usuario (dispositivo, inicio, última actividad, si es la sesión actual) y SHALL permitir cerrar de forma remota una sesión propia individual o todas las demás sesiones propias a la vez, usando el mecanismo de revocación de sesión ya especificado por `authentication` de `d11-identidad-acceso`, restringido a las sesiones del propio usuario.

#### Scenario: Cerrar una sesión remota propia la revoca de inmediato

- **WHEN** el usuario "lucia" hace clic en "Cerrar sesión" sobre una de sus sesiones activas que no es la actual
- **THEN** el sistema revoca esa sesión de inmediato, la fila desaparece del listado, y cualquier petición posterior con esa sesión responde 401

#### Scenario: La sesión actual no ofrece cierre desde este listado

- **WHEN** el usuario ve el listado de sus sesiones activas en Configuración personal
- **THEN** la sesión marcada como actual no muestra la acción "Cerrar sesión" (para salir de la sesión actual existe el logout del menú de usuario)

#### Scenario: Un usuario no puede cerrar la sesión de otro usuario

- **WHEN** la sesión de "lucia" intenta cerrar un identificador de sesión que pertenece a otro usuario
- **THEN** el sistema deniega la operación, no revoca esa sesión, y registra el intento como evento denegado
