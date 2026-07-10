# Design — d11-identidad-acceso

## Context

Este es el primer change de la Etapa D que entrega producto de punta a punta (backend + UI). Todo lo que viene después de `d11` asume un usuario autenticado con rol resuelto de sesión: sin este change, `d12` a `d21` no tienen sobre qué construir. `d11` depende de la fundación (`a01`, ADR-0008: sesiones server-side + Argon2id + TOTP pyotp), del núcleo de gobernanza (`a02`/`a03`: manifiestos, Policy Gate, `AuditEvent`), de la persistencia (`b04`: Postgres + Alembic, tablas append-only) y del shell (`d10`: tokens, layout, componentes base). Como ninguno de esos changes está implementado todavía (repo greenfield), este design fija las decisiones necesarias para que la implementación de `d11` sea directa una vez esas dependencias estén archivadas, sin reabrir debates ya cerrados en `a01`.

Fuente de UX normativa: `design/VISTAS/01-acceso-shell.md` (vistas 1 y 2), `design/FLUJOS.md` Flujo A, `design/FUNCIONALIDADES.md` §1 y §11.

## Goals / Non-Goals

**Goals:**

- Login, sesión server-side revocable, TOTP y cambio de contraseña conformes a OWASP ASVS (gestión de sesiones) y sin criptografía artesanal.
- Gestión de cuentas y grupos por el Admin, con toda mutación auditada.
- Wizard de primer acceso completo (contraseña, TOTP según rol, idioma/tema, acuerdo de uso auditado) que cierra el Flujo A de punta a punta.
- `userId` derivado exclusivamente de la sesión en todo el backend de identidad, sentando el patrón que el resto de la plataforma (`d12`–`d21`) debe replicar.

**Non-Goals:**

- Tablero completo de administración (listado paginado/filtrable, telemetría, audit log global con filtros, salud del sistema) — eso es `d19-admin-operacion`. `d11` entrega el modal de alta de usuario/grupo (vistas 31/32) y las acciones de gestión (suspender, resetear, revocar, exigir TOTP) como endpoints con tests y una lista funcional mínima de cuentas para operarlas, sin el pulido visual completo del mockup.
- Matriz de visibilidad agente×rol y matriz de capacidades por rol (`d20-gobernanza-plataforma`).
- SSO/LDAP, registro público, recuperación de contraseña self-service, notificaciones push/email.
- Configuración personal más allá de lo que exige el wizard (memoria, auditoría personal completa) — `d18-mi-espacio`.

## Decisions

1. **Capa propia delgada sobre `argon2-cffi` + `itsdangerous` + `pyotp`, no `fastapi-users`.** Ratifica la evaluación de ADR-0008 (`a01`) a favor de la opción de control fino: el producto exige alta exclusivamente por Admin (sin registro), TOTP obligatorio condicional por rol, bloqueo progresivo, contraseña temporal de un solo uso y grupos — reglas de negocio específicas que pelean contra las convenciones de `fastapi-users` (pensado para self-signup con email). *(Nota: ADR-0008 todavía no existe como archivo porque `a01` no está implementado; este design asume que su texto final ratifica esta elección — ver Open Questions.)*

2. **Sesión = cookie firmada opaca + fila server-side, no JWT stateless.** La cookie contiene un `session_id` de alta entropía firmado con `itsdangerous` (detecta manipulación sin roundtrip a DB), pero la validez real (revocada / expirada / activa) se resuelve contra una fila en `adapters/persistence_postgres` (`sessions`: `id`, `user_id`, `created_at`, `last_seen_at`, `expires_at`, `revoked_at`, `revoked_by`). Un JWT autocontenido no permite revocación inmediata sin lista de bloqueo adicional — la fila server-side es más simple y ya es requisito explícito (design: "reemplaza cualquier cookie sin firmar"). Cookie con `Secure`, `HttpOnly`, `SameSite=Lax`.

3. **Expiración doble: inactividad (sliding) + máximo absoluto.** Cada petición autenticada actualiza `last_seen_at`; la sesión expira si `now - last_seen_at > idle_timeout` **o** si `now - created_at > absolute_lifetime`, lo que ocurra primero. Evita que una sesión activa indefinidamente por refresco continuo viva para siempre.

4. **Rate limiting progresivo respaldado en Postgres, no en memoria de proceso ni Redis.** Tabla `login_attempts` (o contador por cuenta) registrada en `adapters/persistence_postgres`, consistente aunque corran múltiples réplicas de la app. Alternativa Redis descartada: no está en el stack todavía y agregaría una dependencia nueva solo para esto; alternativa en memoria de proceso descartada porque no es consistente entre réplicas. Umbral y ventana (ej. 15 min, per mockup `01-login.html`) configurables por instancia.

5. **CSRF: `SameSite=Lax` + token de doble envío para mutaciones.** Como la sesión vive en cookie (no en un bearer token que el frontend adjunta explícitamente), toda mutación (`POST`/`PUT`/`DELETE`) exige un header `X-CSRF-Token` que el backend compara contra un valor en una cookie no-`HttpOnly` separada, emitida junto con la sesión. Cumple OWASP ASVS V4 sin depender solo de `SameSite` (que no cubre todos los navegadores/escenarios).

6. **Secreto TOTP cifrado en reposo; códigos de respaldo hasheados como contraseñas.** El secreto TOTP (Base32) se cifra a nivel de aplicación con una clave de entorno/secret manager antes de persistir — nunca en texto plano, nunca en logs ni en `AuditEvent`. Los códigos de respaldo se generan, se muestran una vez y se almacenan como hash Argon2id (igual que una contraseña), marcados `used_at` al consumirse.

7. **Política de contraseña aplicada en el servidor, no solo en el medidor de UX.** El medidor de fortaleza de `02-primer-acceso.html` es ayuda visual; la validación real (≥12 caracteres, mayúscula+minúscula+número+símbolo) vive en el backend y es la única fuente de verdad.

8. **Auditoría de identidad reutiliza el patrón append-only, con un tipo de evento propio.** El glosario define `AuditEvent` como "decisiones del Policy Gate y tool calls" — más angosto que lo que `design/FUNCIONALIDADES.md` §11 pide para el audit log global (incluye "aceptaciones de acuerdo" y "mutaciones de config"). `d11` registra sus eventos (alta, baja, suspensión, cambio de rol, reset, revocación, exigencia TOTP, aceptación de acuerdo) con un `event_type` discriminador dentro del mismo mecanismo append-only que expondrá `a03-core-gobernanza`. Si el `AuditEvent` de `a03` no admite un tipo genérico al momento de implementar, la alternativa de repliegue es una tabla `identity_audit_log` propia con el mismo contrato (append-only, sin UPDATE/DELETE) — decisión final se toma en la tarea de integración, no aquí (ver Open Questions y nota de términos en el resumen final).

9. **Alcance de UI admin: alta completa, resto funcional sin pulido.** El modal "Crear usuario" (`31-admin-usuarios.html`) y "Crear grupo" (`32-admin-grupos.html`) se implementan completos porque el Flujo A los requiere. Las acciones de suspender/resetear/revocar/exigir TOTP quedan expuestas como endpoints con tests de contrato y una fila de acciones mínima en una lista simple de cuentas — el tablero con filtros, búsqueda y analítica de `31`/`32` completos es de `d19`.

10. **Bounded context `identity` no toca `core/`.** El Policy Gate y sus `ActionRequest` (definidos en `a03`) siguen orientados a acciones de skill/tool; las operaciones de identidad (login, gestión de cuentas) usan autorización por rol a nivel de `app/use_cases/identity`, sin pasar por el Policy Gate. Cuando una skill necesite el `userId`/rol de la sesión (changes posteriores), lo recibe ya resuelto — `d11` no modifica `core/policy` ni sus contratos.

## Risks / Trade-offs

- [UI de gestión de usuarios queda parcial hasta `d19`] → Mitigación: backend completo y testeado desde ya; el Admin puede operar suspensión/reset/revocación/TOTP vía la lista mínima, sin esperar a `d19` para tener la capacidad, solo el pulido visual.
- [Rate limiting en Postgres agrega una consulta por intento de login] → Mitigación: aceptable al volumen inicial (~30 consultores, instancia por cliente); documentar migración a un backend de cache si el volumen crece (trigger explícito, no prematuro).
- [Secreto TOTP cifrado a nivel de aplicación depende de gestión correcta de la clave de cifrado] → Mitigación: clave fuera del repo (env/secret manager), rotación documentada en el runbook de `e24-despliegue-operacion`; nunca se seedea en manifiestos ni fixtures versionadas.
- [Contraseña temporal de un solo uso viaja en la respuesta HTTP de creación] → Mitigación: TLS obligatorio end-to-end, nunca logueada (ni en audit log ni en trazas), UI la borra de la vista al navegar fuera del modal.
- [`AuditEvent` de `a03` puede no ser lo bastante genérico para eventos de identidad] → Mitigación: diseño con tipo discriminador desde ya; repliegue documentado a tabla propia con el mismo contrato append-only si hace falta.
- [Cookies asumen mismo origen frontend/backend] → Mitigación: ver Open Questions; si `d10`/`e24` terminan definiendo orígenes distintos, este change necesita revisar `SameSite`/CORS antes de cerrarse como "hecho".

## Migration Plan

Greenfield: no hay datos previos que migrar. Orden de despliegue dentro del change: (1) tablas de `adapters/persistence_postgres` (`users`, `sessions`, `groups`, `group_members`, `login_attempts`, `usage_agreement_versions`, `usage_agreement_acceptances`, y el mecanismo de auditoría de identidad) vía Alembic; (2) casos de uso de `app/use_cases/identity`; (3) endpoints de `app/api`; (4) UI de `frontend/`. Rollback = revertir la migración Alembic del change completo (no hay usuarios reales todavía en la primera instancia).

## Open Questions

1. ADR-0008 todavía no existe como archivo (`a01` sin implementar). Este design asume "capa propia delgada" — confirmar contra el texto final de la ADR antes de codear la tarea de sesión/TOTP.
2. Topología de despliegue frontend/backend (mismo origen vs. orígenes distintos) no está fijada todavía (`d10`/`e24`). Si termina siendo cross-origin, `SameSite=Lax` + CSRF de doble envío debe revisarse (`SameSite=None` + `Secure` y ajuste de CORS).
3. ¿El `AuditEvent` de `a03-core-gobernanza` admite un `event_type` genérico para mutaciones de identidad y aceptaciones de acuerdo, o `d11` necesita una tabla de auditoría propia con el mismo contrato? Se resuelve al implementar, con `a03` ya archivado.
4. Umbral y ventana exactos del rate limiting (el mockup sugiere 15 min) — ¿fijo en código o configuración de instancia como el resto de defaults de `design/FUNCIONALIDADES.md` §11? Por defecto se implementa como configuración de instancia, a confirmar con producto.
