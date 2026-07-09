# Proposal — d18-mi-espacio

## Why

El principio de diseño D8 (`design/README.md`) exige que "cada usuario ve su propio rastro": hasta este change, ningún usuario tiene forma de reconstruir qué tools se ejecutaron en su nombre, qué aprobó o rechazó, qué archivos subió, ni de controlar sus propias preferencias de cuenta sin pasar por el Admin. Sin esta vista personal, la transparencia que sostiene la confianza en HITL, en el escaneo N2/N3 de adjuntos y en el acuerdo de uso queda solo del lado del sistema (audit log interno) y nunca llega al usuario. `d18` cierra ese vacío con el tercer slice vertical de "Mi espacio" (los otros dos — Mi consumo y Mi memoria — ya están asignados a `d16` y `e23`).

## What Changes

- Se implementa **Mi auditoría** (vista `25-mi-auditoria`, `/espacio/auditoria`): subconjunto del audit log global (`AuditEvent` de `a03-core-gobernanza`) filtrado estrictamente por `user_id = usuario autenticado`, de solo lectura, paginado server-side, con filtro por tipo de evento y rango de fecha. Catálogo mínimo de eventos visibles: ejecuciones de tools propias, aprobaciones/rechazos HITL propios, confirmaciones N2 ("confirmo que son datos de prueba"), aceptaciones del acuerdo de uso, solicitudes de liberación de cuota propias y sus resoluciones, inicios/cierres de sesión propios, cambios de memoria propios, subidas de adjuntos propias.
- Se implementa **Mis adjuntos** (`/espacio/adjuntos`, vista nueva sin mockup previo — se documenta aquí sobre la base del ANEXO): listado de los adjuntos propios (`uploaded_by = usuario autenticado`) vivos dentro de la retención de la instancia (90 días default, `b04-persistencia-postgres`), con `original_name`, fecha de subida, tamaño, sesión/conversación de origen y estado de escaneo (`ready` / `blocked` (N3) / advertencia N2 confirmada). La descarga reutiliza el endpoint auditado ya definido por `d14-attachments` (dueño y Admin, nunca URL pública): este change no redefine el mecanismo de descarga, solo lo expone en un listado propio y agrega su `AuditEvent` de acceso vía Mi espacio. Cuando la retención purga el binario, el ítem se muestra como expirado — la conversación que lo usó sigue íntegra porque `inserted_text` sobrevive al binario (invariante ya garantizada por `attachment-storage` de `b04`).
- Se implementa **Configuración personal** (vista `26-configuracion`, `/espacio/configuracion`): preferencias de tema (oscuro/claro/sistema) e idioma (`es-BO` activo; `pt-BR` presente en el selector pero deshabilitado hasta activación de instancia en Etapa P), gestión de TOTP propio (activar/desactivar/regenerar códigos de respaldo para Técnico y Funcional; para Admin la opción "Desactivar" no se renderiza — TOTP es obligatorio por `d11-identidad-acceso`), cambio de contraseña propia, y listado de sesiones activas propias con cierre remoto individual y masivo ("cerrar todas las demás"). Este change construye la UI y los endpoints de listado/preferencia; la mecánica de hash Argon2id, el enrolamiento TOTP (QR + códigos de respaldo) y la invalidación de sesiones ya están especificados por `authentication` de `d11-identidad-acceso` y se consumen sin reabrirlos.
- Toda lectura de Mi auditoría, toda descarga desde Mis adjuntos y toda mutación de Configuración personal (cambio de tema/idioma, TOTP, contraseña, cierre de sesión) queda registrada como `AuditEvent` propio, visible a su vez en Mi auditoría.
- Se aplica **ownership estricto** en las tres áreas: ningún endpoint acepta un identificador de usuario ajeno desde el cliente — el `user_id` siempre se deriva de la sesión autenticada (mismo contrato que `d11`); todo intento de acceder al rastro de otro usuario se deniega y queda auditado como intento denegado.

## Capabilities

### New Capabilities

- `personal-space`: las tres áreas de autoservicio personal —Mi auditoría (lectura filtrada del audit log propio), Mis adjuntos (listado propio dentro de retención + descarga auditada reutilizando `d14`) y Configuración personal (tema, idioma, TOTP propio, contraseña propia, sesiones activas propias)— con ownership estricto verificado en cada endpoint y capa por rol limitada a la restricción de TOTP obligatorio de Admin.

### Modified Capabilities

*(ninguna — `personal-space` es nueva; consume sin modificar `audit-log` de `a03-core-gobernanza`, `attachment-storage` de `b04-persistencia-postgres`, `attachments-pipeline` de `d14-attachments` y `authentication` de `d11-identidad-acceso`)*

## No-objetivos

- **Sin Mi consumo** (`d16-cuotas-liberaciones`): consumo del día/mes contra cuota y "Mis solicitudes de liberación" viven en la vista 23 y la capability `consumption-view` de `d16`; `d18` no las duplica.
- **Sin Mi memoria** (`e23-memoria-usuario`): ver/editar/borrar memoria personal, su validador anti-PII/credenciales y su historial de cambios son alcance de `e23`; `d18` solo muestra, dentro de Mi auditoría, el evento ya registrado de un cambio de memoria (lectura del rastro, no la funcionalidad de memoria en sí).
- **Sin memoria de proyecto/cliente**: memoria compartida por equipo administrada por Técnicos queda para Etapa P.
- **Sin audit log global ni telemetría agregada** (`d19-admin-operacion`): Mi auditoría es exclusivamente el subconjunto del propio usuario; el Admin no puede ver el rastro de otro usuario desde este módulo (su consola global es otro módulo, otro change).
- **Sin redefinir el pipeline ni el escaneo de adjuntos** (`d14-attachments`): Mis adjuntos consume el schema de `b04` y el endpoint de descarga auditada de `d14` tal cual; no valida, extrae, sanea ni escanea archivos.
- **Sin redefinir autenticación, hashing ni enrolamiento TOTP** (`d11-identidad-acceso`): Configuración personal reutiliza Argon2id, la política de contraseñas y el flujo guiado de TOTP (QR + códigos de respaldo) ya especificados por `d11`; aquí solo se expone la superficie de autoservicio (activar/desactivar/regenerar/cambiar) fuera del wizard de primer acceso.
- **Sin eliminación manual de adjuntos por el usuario**: el ciclo de vida de "Mis adjuntos" es de solo lectura + descarga; la única baja es la purga automática por retención de instancia (`b04`), no una acción de borrado expuesta en esta vista.
- **Sin gestión de usuarios/grupos ni reset ajeno de contraseña**: eso es `d11`/`d19` (consola Admin); `d18` es estrictamente autoservicio sobre la propia cuenta.

## Bounded context afectado

Slice vertical de producto: `resultarai/app/` (casos de uso de lectura del audit log propio, listado de adjuntos propios, preferencias de cuenta, delegación a `authentication` de `d11` para TOTP/contraseña/sesiones) + `frontend/` (vistas `25-mi-auditoria`, `26-configuracion` y la vista nueva de listado de adjuntos, bajo la sección "Mi espacio" del shell). No introduce lógica de dominio nueva en `core/`: reutiliza los ports y modelos ya definidos por `a03-core-gobernanza` (`AuditEvent`), `b04-persistencia-postgres` (schema de attachments) y `d11-identidad-acceso` (identidad/sesión), aplicando sobre ellos un filtro de ownership en la capa `app/`.

## Impact

- `resultarai/app/personal_space/` (o equivalente): casos de uso de consulta paginada del audit log propio, listado de adjuntos propios con estado de escaneo, y endpoints de preferencias (tema/idioma), delegando TOTP/contraseña/sesiones a los casos de uso ya expuestos por `identity` de `d11`.
- `resultarai/app/api/`: endpoints REST `GET /me/audit-events`, `GET /me/attachments`, `GET /me/attachments/{id}/download` (proxy auditado al endpoint de `d14`), `GET/PUT /me/preferences`, más los ya existentes de `d11` reutilizados desde esta UI (TOTP, contraseña, sesiones).
- `frontend/`: vistas `25-mi-auditoria`, `26-configuracion` conforme a `design/VISTAS/06-mi-espacio.md`, y una vista de listado de adjuntos propios (sin mockup dedicado en `design/`; se sigue el patrón visual de tabla+filtro+paginación de `25-mi-auditoria` y los estados de escaneo del ANEXO §4.4/§10).
- Depende de (archivados o con interfaz ya especificada): `a01-fundacion-repo` (esqueleto), `a03-core-gobernanza` (`AuditEvent`), `b04-persistencia-postgres` (schema de attachments, audit persistence), `d10-design-system-shell` (shell, tokens, componentes base), `d11-identidad-acceso` (sesión, TOTP, contraseña, roles), `d14-attachments` (pipeline y descarga auditada).
- Referencia normativa: `design/VISTAS/06-mi-espacio.md` (vistas 25 y 26), `design/FUNCIONALIDADES.md` §10, `design/README.md` (decisión D8), `design/ANEXO-ATTACHMENTS.md` §4.4/§5/§7 (estado de escaneo y retención citados, no redefinidos).
