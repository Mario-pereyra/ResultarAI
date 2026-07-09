# Tasks — d18-mi-espacio

## 1. Mi auditoría — backend

- [ ] 1.1 Caso de uso `list_own_audit_events` en `resultarai/app/personal_space/`: consulta `AuditEvent` filtrado por `user_id` de sesión, paginación server-side. Verificación: escenario "Un usuario ve solo sus propios eventos" pasa con datos de 2 usuarios distintos. `[modelo: sonnet]`
- [ ] 1.2 Endpoint `GET /me/audit-events` con parámetros `type`, `from`, `to`, `page`: aplica los filtros al caso de uso 1.1 y reinicia la página al cambiar filtro. Verificación: escenarios "Filtrar por tipo reconsulta y reinicia la paginación" y "Filtro por fecha sin resultados". `[modelo: sonnet]`
- [ ] 1.3 Test de contrato: `user_id` de la sesión ignora cualquier `user_id` recibido en query params del endpoint 1.2. Verificación: escenario "Un parámetro de usuario ajeno en la URL es ignorado". `[modelo: sonnet]`
- [ ] 1.4 Test de ownership cruzado: usuario A no puede leer eventos de usuario B por ningún filtro combinado; el intento queda registrado como `AuditEvent` denegado. Verificación: escenario "Intento de acceder a la auditoría o los adjuntos de otro usuario es denegado y auditado" (parte auditoría). `[modelo: sonnet]`

## 2. Mi auditoría — frontend

- [ ] 2.1 Vista `/espacio/auditoria` conforme a `design/VISTAS/06-mi-espacio.md` vista 25: nota de inmutabilidad, filtro por tipo, tabla paginada con `fecha_hora`/`tipo`/`detalle`/`contexto`. Verificación: captura visual coincide con el wireframe de la vista 25 (paneles, tags por tipo). `[modelo: sonnet]`
- [ ] 2.2 Estados de la vista: carga (skeleton), vacío (cuenta nueva), vacío por filtro, error con reintento, parcial con warning. Verificación: cada estado de la sección "Estados" de la vista 25 se reproduce con datos mockeados. `[modelo: sonnet]`
- [ ] 2.3 Enlace desde evento tipo APROBACIÓN hacia la tarjeta HITL resuelta (solo lectura). Verificación: clic en una fila APROBACIÓN navega a la tarjeta correspondiente sin permitir edición. `[modelo: sonnet]`
- [ ] 2.4 Textos UI de Mi auditoría externalizados bajo la clave `espacio.auditoria.*`, plantillas de `detalle` con placeholders nombrados (no concatenación). Verificación: ningún string de detalle está hardcodeado; los 8 tipos de evento del catálogo mínimo tienen su plantilla. `[modelo: haiku]`

## 3. Mis adjuntos — backend

- [ ] 3.1 Caso de uso `list_own_attachments` en `resultarai/app/personal_space/`: consulta adjuntos con `uploaded_by` de sesión y binario vigente dentro de la retención de instancia, proyectando `original_name`, fecha, tamaño, sesión de origen y estado derivado de `scan_result`. Verificación: escenario "Un usuario ve sus adjuntos vigentes con su estado de escaneo". `[modelo: sonnet]`
- [ ] 3.2 Endpoint `GET /me/attachments`. Verificación: respuesta solo incluye adjuntos del usuario de sesión; adjunto de otro usuario en la misma sesión de prueba nunca aparece. `[modelo: sonnet]`
- [ ] 3.3 Endpoint `GET /me/attachments/{id}/download` como proxy auditado hacia el endpoint de descarga de `attachments-pipeline` (`d14-attachments`): valida ownership, delega la entrega del archivo, y emite `AuditEvent` propio de descarga desde Mi espacio. Verificación: escenario "Descargar un adjunto propio queda auditado y visible en Mi auditoría" (incluye verificar que el evento aparece luego vía el endpoint 1.2). `[modelo: sonnet]`
- [ ] 3.4 Test de invariante de retención: un adjunto purgado (binario + `full_text` eliminados por `b04`) deja de listarse como vigente en 3.1 sin afectar la integridad de la conversación que lo referenció. Verificación: escenario "Un adjunto purgado por retención desaparece del listado sin romper la conversación". `[modelo: sonnet]`
- [ ] 3.5 Test de ownership: descarga de un adjunto ajeno vía 3.3 responde 403 y queda auditada como intento denegado, sin filtrar contenido del archivo. Verificación: escenario "Intento de acceder a la auditoría o los adjuntos de otro usuario es denegado y auditado" (parte adjuntos). `[modelo: sonnet]`

## 4. Mis adjuntos — frontend

- [ ] 4.1 Vista `/espacio/adjuntos` siguiendo el patrón visual de la vista 25 (panel + tabla en `.panel--flush` + paginación clásica): columnas nombre, fecha, tamaño, sesión de origen, estado de escaneo con `.tag`, acción de descarga por fila. Verificación: estado de escaneo se distingue visualmente (`listo`/`bloqueado`/advertencia N2) reutilizando los tokens ya definidos por el ANEXO §4.4/§10. `[modelo: sonnet]`
- [ ] 4.2 Estados de la vista: carga, vacío (sin adjuntos), error con reintento, ítem expirado por retención mostrado como no descargable. Verificación: los 4 estados se reproducen con datos mockeados, incluido el caso de adjunto expirado. `[modelo: sonnet]`
- [ ] 4.3 Textos UI de Mis adjuntos externalizados bajo la clave `espacio.adjuntos.*`. Verificación: ningún string hardcodeado; nombres de estado de escaneo reutilizan las claves ya definidas por `d14-attachments` cuando existen. `[modelo: haiku]`

## 5. Configuración personal — backend

- [ ] 5.1 Caso de uso y endpoint `GET/PUT /me/preferences` (tema, idioma) persistidos por cuenta; `pt-BR` se acepta en el modelo pero queda marcado `disabled` hasta activación de instancia. Verificación: escenarios "Cambiar el tema aplica de inmediato y persiste" y "pt-BR aparece deshabilitado hasta activación de instancia". `[modelo: sonnet]`
- [ ] 5.2 Endpoint `GET /me/sessions`: lista las sesiones activas propias (dispositivo, inicio, última actividad, `es_actual`) reutilizando el almacenamiento de sesiones de `authentication` (`d11-identidad-acceso`) sin duplicar su schema. Verificación: solo se listan sesiones del usuario de la petición. `[modelo: sonnet]`
- [ ] 5.3 Endpoint `POST /me/sessions/{id}/revoke` y `POST /me/sessions/revoke-others`: delegan al mecanismo de revocación ya especificado por `d11`, restringidos a sesiones del propio usuario. Verificación: escenarios "Cerrar una sesión remota propia la revoca de inmediato" y "Un usuario no puede cerrar la sesión de otro usuario". `[modelo: sonnet]`
- [ ] 5.4 Integración de Configuración personal con los casos de uso ya existentes de `d11` para activar/desactivar TOTP, regenerar códigos de respaldo y cambiar contraseña, sin reimplementarlos (solo la capa de endpoint/orquestación propia de esta vista si `d11` no los expone ya como API reutilizable). Verificación: escenarios "Un usuario Técnico o Funcional activa TOTP...", "Regenerar códigos de respaldo invalida los anteriores", "Cambio de contraseña exitoso revoca las otras sesiones" y "Cambio de contraseña rechazado...". `[modelo: sonnet]`
- [ ] 5.5 Test de restricción de rol: la mutación "desactivar TOTP" es rechazada por el backend si la cuenta es Admin, incluso si la UI no la ofreciera. Verificación: escenario "Un usuario Admin no puede desactivar TOTP desde Configuración personal" probado a nivel de API, no solo de UI. `[modelo: sonnet]`

## 6. Configuración personal — frontend

- [ ] 6.1 Vista `/espacio/configuracion` conforme a `design/VISTAS/06-mi-espacio.md` vista 26: panel Preferencias (idioma/tema), panel TOTP, panel Sesiones activas, panel Contraseña. Verificación: los 4 paneles renderizan según el wireframe y `.field`/`.table`/`.tag` reutilizan componentes del design system. `[modelo: sonnet]`
- [ ] 6.2 Flujo de activación de TOTP (QR + clave manual + confirmación) y modal de códigos de respaldo (mostrados una sola vez, con "Descargar .txt"/"Copiar"). Verificación: abandonar el flujo a mitad deja TOTP en estado INACTIVO (activación atómica). `[modelo: sonnet]`
- [ ] 6.3 Para rol Admin, el botón "Desactivar TOTP" no se renderiza; se muestra la nota de obligatoriedad. Verificación: snapshot de la vista con sesión Admin vs. no-Admin difiere exactamente en ese elemento. `[modelo: sonnet]`
- [ ] 6.4 Formulario de cambio de contraseña con requisitos siempre visibles y validación inline al blur; formulario de sesiones activas con confirmación simple para "Cerrar todas las demás". Verificación: casos borde de la vista 26 (única sesión activa → el botón masivo no se renderiza). `[modelo: sonnet]`
- [ ] 6.5 Textos UI de Configuración personal externalizados bajo `espacio.config.*`, incluyendo nombres de idioma en su propio idioma y la nota de obligatoriedad de TOTP para Admin. Verificación: ningún string hardcodeado; nombres de idioma no se traducen. `[modelo: haiku]`

## 7. Ownership transversal y auditoría

- [ ] 7.1 Middleware o dependencia compartida en `resultarai/app/personal_space/` que resuelve `user_id` desde la sesión validada y lo inyecta en los tres casos de uso (1.1, 3.1, 5.1–5.3), rechazando cualquier `user_id` alternativo recibido en la petición. Verificación: escenario "Un parámetro de usuario ajeno en la URL es ignorado" cubre los tres endpoints de lectura, no solo auditoría. `[modelo: sonnet]`
- [ ] 7.2 Emisión uniforme de `AuditEvent` de intento denegado por ownership desde el middleware de 7.1, reutilizable por los tres endpoints protegidos. Verificación: forzar un acceso cruzado en cada una de las tres áreas produce exactamente un `AuditEvent` con el recurso solicitado y el resultado denegado. `[modelo: sonnet]`
- [ ] 7.3 Test end-to-end de la matriz Vista × Rol para "Mi espacio — auditoría personal" y "Mi espacio — configuración" (`design/FUNCIONALIDADES.md`): Admin, Técnico y Funcional acceden a las tres vistas sin diferencias de estructura, solo la restricción de TOTP de Admin. Verificación: los 3 roles pasan el mismo flujo salvo esa única divergencia documentada. `[modelo: sonnet]`

## 8. Cierre

- [ ] 8.1 Revisión de consistencia visual de Mis adjuntos contra el patrón de Mi auditoría (no hay mockup dedicado, ver `design.md` decisión 3): confirmar que tokens, tags de estado y paginación son coherentes con el resto de "Mi espacio". Verificación: checklist de componentes reutilizados vs. componentes nuevos, documentado en el PR. `[modelo: sonnet]`
- [ ] 8.2 Review final del change: ownership verificado en los tres endpoints, ningún endpoint acepta `user_id` externo, cero lógica nueva en `core/`, dependencias con `a03`/`b04`/`d11`/`d14` consumidas sin modificar sus specs. Verificación: checklist del reviewer en el PR. `[modelo: opus]`
