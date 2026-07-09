# Tasks — d11-identidad-acceso

## 1. Modelo de datos (Postgres / Alembic)

- [x] 1.1 Migración Alembic: tabla `users` (id, username, display_name, email, role, group_id, password_hash, must_change_password, status, created_at, updated_at). Verificación: `alembic upgrade head` corre limpio y la tabla es consultable. `[modelo: sonnet]`
- [x] 1.2 Migración Alembic: tabla `sessions` (id, user_id, created_at, last_seen_at, expires_at, revoked_at, revoked_by) con índices por `user_id` y `expires_at`. Verificación: `alembic upgrade head` en verde; índice usado por el plan de consulta de validación de sesión. `[modelo: opus]`
- [x] 1.3 Migración Alembic: tablas `totp_secrets` (secret cifrado, enrolled_at) y `totp_backup_codes` (hash Argon2id, used_at). Verificación: migración en verde; columna del secreto nunca almacena texto plano (revisión de la migración). `[modelo: opus]`
- [x] 1.4 Migración Alembic: tabla `login_attempts` (account_ref, origin, failed_at) o contador equivalente para el rate limiting progresivo. Verificación: migración en verde. `[modelo: sonnet]`
- [x] 1.5 Migración Alembic: tablas `groups` y `group_members`. Verificación: migración en verde; constraint de unicidad de membresía. `[modelo: sonnet]`
- [x] 1.6 Migración Alembic: tablas `usage_agreement_versions` (id, text, published_at) y `usage_agreement_acceptances` (user_id, version_id, accepted_at). Verificación: migración en verde. `[modelo: sonnet]`
- [x] 1.7 Migración Alembic: mecanismo append-only de auditoría de identidad (extensión del `AuditEvent` de `a03` con `event_type`, o tabla `identity_audit_log` propia si `a03` no expone un tipo genérico — decisión de design.md #8). Verificación: migración en verde; sin `UPDATE`/`DELETE` posible por constraint o trigger. `[modelo: opus]`

## 2. Núcleo de sesión, contraseñas y TOTP (seguridad crítica)

- [x] 2.1 Módulo de hashing de contraseñas: Argon2id vía `argon2-cffi` con parámetros de costo vigentes (OWASP), verificación en tiempo constante provista por la librería. Verificación: test unitario hashea+verifica correctamente y rechaza un hash inválido, sin comparación manual de strings en el código. `[modelo: opus]`
- [x] 2.2 Módulo de sesión: generación de `session_id` de alta entropía, firma con `itsdangerous`, persistencia en `sessions`, validación de firma + revocación + expiración doble (inactividad y máximo absoluto). Verificación: tests cubren sesión válida, expirada por inactividad, expirada por máximo absoluto, revocada y cookie con firma corrupta — todas menos la válida terminan en 401. `[modelo: opus]`
- [x] 2.3 Dependency de FastAPI que resuelve `userId` exclusivamente desde la sesión validada, ignorando cualquier `userId` del body o los parámetros de la petición. Verificación: test de seguridad "body con userId ajeno es ignorado" (petición autenticada como usuario A con `userId` de usuario B en el body ejecuta como A). `[modelo: opus]`
- [x] 2.4 Rate limiting progresivo de login: umbral y ventana configurables, bloqueo `ACCOUNT_LOCKED` por cuenta, liberación por tiempo o por acción del Admin. Verificación: test simulando intentos fallidos consecutivos que dispara el bloqueo y verifica que se libera tras la ventana configurada. `[modelo: opus]`
- [x] 2.5 Módulo TOTP: enrolamiento con `pyotp` (QR `otpauth://`, clave Base32), verificación de código, generación de códigos de respaldo de un solo uso (hash Argon2id), cifrado del secreto TOTP en reposo con clave de entorno/secret manager. Verificación: test de enrolamiento + verificación exitosa; test de que un código de respaldo usado se invalida tras el primer uso. `[modelo: opus]`
- [x] 2.6 CSRF de doble envío para toda mutación autenticada: token en cookie no-`HttpOnly` comparado contra header `X-CSRF-Token`. Verificación: test que una mutación sin header CSRF válido es rechazada (403), y con header válido se ejecuta. `[modelo: opus]`

## 3. Casos de uso y endpoints — autenticación

- [ ] 3.1 Caso de uso + `POST /api/auth/login`: verifica credenciales, aplica rate limiting, crea sesión, detecta primer login. Verificación: tests de login exitoso, contraseña incorrecta, usuario inexistente y cuenta suspendida devuelven el mismo error genérico. `[modelo: sonnet]`
- [ ] 3.2 `POST /api/auth/totp/verify` (segundo paso, obligatorio para Admin): acepta código TOTP o código de respaldo, cuenta reintentos contra el rate limiter. Verificación: test de código correcto, incorrecto y de respaldo (con invalidación tras uso). `[modelo: sonnet]`
- [ ] 3.3 `POST /api/auth/logout`: revoca la sesión actual del lado del servidor. Verificación: test de logout seguido de una petición con la misma cookie → 401. `[modelo: sonnet]`
- [ ] 3.4 `POST /api/auth/password` (cambio propio): valida contraseña actual + política server-side de la nueva, revoca otras sesiones activas. Verificación: test de cambio exitoso con revocación de sesiones ajenas, y rechazo por incumplir política. `[modelo: sonnet]`
- [ ] 3.5 Endpoints de configuración personal de TOTP (activar/desactivar) para Técnico/Funcional, respetando `totp_required` fijado por el Admin. Verificación: test de activar/desactivar y de rechazo si `totp_required=true`. `[modelo: sonnet]`
- [ ] 3.6 Orquestación del wizard de primer acceso: endpoint(s) de estado de progreso y paso de preferencias (idioma/tema) persistidas en la cuenta. Verificación: test E2E del flujo completo (contraseña → TOTP según rol → acuerdo → shell) y de retomar el wizard en el paso pendiente tras cerrar sesión a mitad de camino. `[modelo: sonnet]`

## 4. Casos de uso y endpoints — gestión de usuarios y grupos (Admin)

- [ ] 4.1 `POST /api/admin/users` (alta): genera contraseña temporal de un solo uso, la devuelve solo en esta respuesta, marca la cuenta para forzar el wizard. Verificación: test de alta + que ninguna consulta posterior puede recuperar la contraseña temporal. `[modelo: sonnet]`
- [ ] 4.2 `POST /api/admin/users/{id}/suspend`: revoca todas las sesiones activas de la cuenta. Verificación: test de suspensión seguida de intento de login (mensaje genérico) y de petición con sesión previa (401). `[modelo: sonnet]`
- [ ] 4.3 `POST /api/admin/users/{id}/role`: cambia el rol, bloqueado si el actor es el propio usuario objetivo. Verificación: test "usuario no puede cambiar su propio rol" y test de cambio válido ejecutado por otro Admin. `[modelo: sonnet]`
- [ ] 4.4 `POST /api/admin/users/{id}/reset-password`: genera contraseña temporal de un solo uso, revoca sesiones activas, fuerza wizard en el siguiente login. Verificación: test de reset completo end-to-end. `[modelo: sonnet]`
- [ ] 4.5 `POST /api/admin/users/{id}/sessions/revoke` (individual o total). Verificación: test "sesión revocada → 401" para ambos casos. `[modelo: sonnet]`
- [ ] 4.6 `POST /api/admin/users/{id}/require-totp`: marca TOTP obligatorio y fuerza el enrolamiento en el siguiente login. Verificación: test de exigencia seguida de login que fuerza el paso TOTP sin opción de "más tarde". `[modelo: sonnet]`
- [ ] 4.7 Endpoints de grupos: crear grupo, agregar/quitar miembros. Verificación: test de creación, alta y baja de miembro. `[modelo: sonnet]`
- [ ] 4.8 Autorización de todos los endpoints `/api/admin/*` restringida a rol Admin, reutilizando el resolvedor de sesión de la tarea 2.3. Verificación: test "usuario no-Admin → 403" sobre cada grupo de endpoints de esta sección. `[modelo: sonnet]`

## 5. Acuerdo de uso auditado

- [ ] 5.1 `GET /api/me/agreement/status`: compara la última aceptación del usuario contra la versión vigente. Verificación: test devuelve "pendiente" sin aceptación previa o con versión desactualizada, "vigente" en caso contrario. `[modelo: sonnet]`
- [ ] 5.2 `POST /api/me/agreement/accept`: registra usuario (de sesión) + versión vigente + timestamp; rechaza si no llega una aceptación explícita. Verificación: test de aceptación exitosa y test de rechazo sin checkbox marcado (payload sin la aceptación explícita). `[modelo: sonnet]`
- [ ] 5.3 Endpoint Admin para publicar nueva versión del texto del acuerdo, marcando a los usuarios con aceptación previa como pendientes de re-aceptación. Verificación: test de publicación de versión nueva + usuarios existentes pasan a "pendiente". `[modelo: sonnet]`
- [ ] 5.4 Middleware/guard que bloquea cualquier ruta del shell fuera de login/wizard cuando la aceptación del usuario está desactualizada o ausente. Verificación: test de redirección forzada al paso de acuerdo. `[modelo: sonnet]`

## 6. Auditoría de identidad

- [ ] 6.1 Integrar el registro append-only de eventos de identidad (alta, baja, suspensión, cambio de rol, reset, revocación de sesiones, exigencia de TOTP, aceptación de acuerdo) sobre el mecanismo de la tarea 1.7. Verificación: test que cada mutación de las secciones 4 y 5 genera exactamente un evento auditado, y que el mecanismo no permite `UPDATE`/`DELETE`. `[modelo: sonnet]`

## 7. UI — Login y primer acceso

- [ ] 7.1 Vista Login (`01-login.html`) conforme a `design/VISTAS/01-acceso-shell.md`: formulario usuario/contraseña, paso TOTP, estados de carga/error genérico/`ACCOUNT_LOCKED`/`AUTH_OFFLINE`. Verificación: recorrido manual contra el mockup; cada estado de error del backend se refleja en la UI correspondiente. `[modelo: sonnet]`
- [ ] 7.2 Wizard Primer acceso (`02-primer-acceso.html`): paso 1 contraseña con medidor de fortaleza y checklist de requisitos, paso 2 TOTP (QR + clave manual + códigos de respaldo, saltable solo para no-Admin), paso 3 acuerdo de uso con checkbox bloqueante. Verificación: recorrido E2E de los 3 pasos contra el backend; botón "Aceptar y entrar" permanece deshabilitado sin checkbox marcado. `[modelo: sonnet]`
- [ ] 7.3 Persistencia de progreso del wizard entre sesiones (retoma en el paso pendiente). Verificación: test E2E de cerrar sesión a mitad del wizard y retomar sin repetir pasos completados. `[modelo: sonnet]`
- [ ] 7.4 Externalización i18n de los textos de login y wizard (mensajes de error, hints, política de contraseña, resumen del acuerdo) según `design/VISTAS/01-acceso-shell.md`, catálogo ES con reserva para PT-BR. Verificación: ningún string de estas vistas queda hardcodeado fuera del catálogo i18n. `[modelo: haiku]`

## 8. UI — Consola admin (alta de usuarios y grupos)

- [ ] 8.1 Modal "Crear usuario" (`31-admin-usuarios.html`) con pantalla de confirmación que muestra la contraseña temporal una única vez. Verificación: recorrido E2E de alta completo (Flujo A pasos 1–2). `[modelo: sonnet]`
- [ ] 8.2 Modal "Crear grupo" (`32-admin-grupos.html`) con asignación de miembros. Verificación: E2E de creación de grupo y alta/baja de miembro. `[modelo: sonnet]`
- [ ] 8.3 Lista funcional mínima de cuentas con acciones básicas (suspender, resetear, revocar sesiones, exigir TOTP) — sin el tablero completo de `d19-admin-operacion`. Verificación: cada acción dispara su endpoint y la lista refleja el nuevo estado sin recargar la página. `[modelo: sonnet]`
- [ ] 8.4 Externalización i18n de las pantallas de alta admin de esta sección. Verificación: ningún string hardcodeado fuera del catálogo i18n. `[modelo: haiku]`

## 9. Tests de seguridad explícitos

- [ ] 9.1 Test de fuerza bruta → rate limit: intentos fallidos consecutivos bloquean la cuenta (`ACCOUNT_LOCKED`) y se liberan por tiempo o por acción del Admin. Verificación: suite en verde, incluida la liberación por ambas vías. `[modelo: opus]`
- [ ] 9.2 Test de sesión revocada o expirada → 401 en cualquier endpoint autenticado de las secciones 3, 4 y 5. Verificación: suite en verde. `[modelo: opus]`
- [ ] 9.3 Test de body con `userId` ajeno → ignorado en al menos un endpoint de cada sección (auth, admin, acuerdo). Verificación: suite en verde. `[modelo: opus]`
- [ ] 9.4 Test de atributos de cookie (`Secure`/`HttpOnly`/`SameSite`) y de rechazo de mutaciones sin token CSRF válido. Verificación: suite en verde. `[modelo: opus]`

## 10. Cierre

- [ ] 10.1 Actualizar `docs/03-glosario-dominio.md`: agregar los términos nuevos de este change (Rol Admin/Técnico/Funcional, Sesión, TOTP, Acuerdo de uso, Cuenta, Grupo/equipo, Contraseña temporal de un solo uso) y, según lo resuelto en la tarea 1.7, documentar si `AuditEvent` amplía su definición o si `identity_audit_log` queda como término propio. Verificación: todos los términos usados en `specs/` de este change existen en el glosario. `[modelo: sonnet]`
- [ ] 10.2 Actualizar `CLAUDE.md`: avanzar la línea "Etapa activa" si corresponde al estado real del roadmap al momento de aplicar este change. Verificación: línea coherente con `docs/07-roadmap.md`. `[modelo: haiku]`
- [ ] 10.3 Review final del change: specs↔diseño↔código consistentes; los 4 escenarios de seguridad (fuerza bruta, sesión revocada, `userId` ajeno, CSRF/cookies) cubiertos por tests reales; Flujo A completo end-to-end (alta → primer login → acuerdo → shell); dependencias (`a01`–`a03`, `b04`, `d10`) archivadas antes de mergear. Verificación: checklist del reviewer en el PR. `[modelo: opus]`
