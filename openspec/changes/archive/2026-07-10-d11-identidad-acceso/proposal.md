# Proposal — d11-identidad-acceso

## Why

Hasta ahora ningún change entrega autenticación real: sin identidad no hay `userId` de sesión que el Policy Gate, el audit log ni ninguna vista puedan usar, y todo el resto de la Etapa D (notificaciones, chat, cuotas, HITL, mi espacio, administración) depende de un usuario autenticado con rol. `d11` cierra ese bloqueo entregando el primer slice vertical (backend + UI) de Etapa D: acceso, roles cerrados, gestión de cuentas por el Admin y el flujo de primer acceso completo conforme a `design/FLUJOS.md` Flujo A.

## What Changes

- Se implementa **autenticación** local usuario+contraseña (Argon2id) con sesiones server-side firmadas: revocación individual y total por Admin, timeout por inactividad, logout explícito, `userId` siempre derivado de la sesión (nunca del body de la petición), cambio de contraseña propio y errores de login genéricos (no revelan si la cuenta existe).
- Se implementa **TOTP** (pyotp): obligatorio y sin salida para cuentas Admin (enrolamiento guiado en el primer login: QR + códigos de respaldo), opcional y activable desde configuración personal para Técnico/Funcional.
- Se implementan **roles cerrados** Admin/Técnico/Funcional: el rol es un atributo de la cuenta asignado por el Admin, nunca elegido ni mutable por el propio usuario.
- Se implementa **gestión de usuarios y grupos** (consola Admin, slice de alta — el tablero completo llega en `d19-admin-operacion`): alta/baja/suspensión de cuentas, asignación de rol, reset de contraseña con contraseña temporal de un solo uso mostrada una única vez, revocación de sesiones, exigencia de TOTP, y grupos/equipos como base de las cuotas de `d16-cuotas-liberaciones`. Sin registro público: el alta es el único origen de cuentas.
- Se implementa el **wizard de primer acceso** (Flujo A, vista `02-primer-acceso.html`): cambio obligatorio de contraseña, selección de idioma y tema, y **acuerdo de uso auditado** (checkbox que bloquea el avance hasta marcarse; queda registrado usuario + versión del texto + timestamp; un cambio del texto fuerza re-aceptación).
- Se implementa la **UI** de las vistas `01-login` y `02-primer-acceso` conforme a `design/VISTAS/01-acceso-shell.md`, y las pantallas de alta de usuarios/grupos de la consola admin (mockups `31-admin-usuarios.html` / `32-admin-grupos.html`, solo la parte de alta — telemetría, cuotas y audit log global de esas vistas llegan en `d19`).
- Toda mutación de identidad (alta, baja, suspensión, cambio de rol, reset, revocación, exigencia de TOTP, aceptación del acuerdo) queda en el audit log (`AuditEvent`), aunque el visor global de auditoría es de `d19`.

## Capabilities

### New Capabilities

- `authentication`: login usuario+contraseña, sesiones server-side firmadas con revocación y timeout, TOTP, logout, cambio de contraseña propio.
- `user-management`: alta/baja/suspensión de cuentas, roles cerrados, grupos, reset de contraseña, revocación de sesiones, exigencia de TOTP — todo por el Admin.
- `usage-agreement`: acuerdo de uso auditado con versionado del texto y re-aceptación forzada ante cambios.

### Modified Capabilities

*(ninguna — no existen specs previas)*

## No-objetivos

- Sin SSO ni LDAP/Active Directory: autenticación local únicamente (`design/FUNCIONALIDADES.md` §1 — "Sin auth artesanal" se refiere a no reinventar primitivas criptográficas, no a delegar identidad a un proveedor externo).
- Sin registro público por diseño: el alta de cuentas es siempre un acto administrativo del Admin; no existe pantalla ni endpoint de self-signup.
- Sin matriz de visibilidad agente×rol ni matriz de capacidades por rol: esa configuración es de `d20-gobernanza-plataforma`; aquí el rol solo determina qué secciones de identidad ve cada usuario (p. ej. la consola admin).
- Sin notificaciones push ni email: la contraseña temporal se entrega por canal interno fuera del sistema (Flujo A paso 2); no se implementa envío de correo ni integración con el centro de notificaciones de `d12-notificaciones`.
- Sin el tablero completo de administración (telemetría, cuotas, audit log global, salud del sistema, retención/branding de instancia): eso es `d19-admin-operacion`. Aquí solo la gestión de cuentas/grupos en sí.
- Sin recuperación de contraseña self-service: el reset siempre lo ejecuta el Admin (`design/VISTAS/01-acceso-shell.md` — "la resetea el Admin, el hint lo dice").
- Sin memoria de usuario ni configuración personal más allá de idioma/tema/TOTP/contraseña del wizard: el resto de "Mi espacio" es de `d18-mi-espacio`.

## Bounded context afectado

`identity` (bounded context nuevo del producto, ver `docs/07-roadmap.md` tarea 1.2 de `a01-fundacion-repo`): vive en `resultarai/app/use_cases/identity/` (casos de uso de login, sesión, TOTP, gestión de usuarios) + `resultarai/adapters/persistence_postgres/` (tablas de cuentas, sesiones, grupos, audit log de identidad) + `frontend/` (vistas `01-login`, `02-primer-acceso`, alta de usuarios/grupos en consola admin). No toca `core/` como dominio de scaffolding (manifiestos/registries/Policy Gate) salvo para que el Policy Gate reciba `userId`/`rol` de sesión como parte del `ActionRequest`; esa integración es de consumo, no de definición, y no requiere cambios en `core/`.

## Impact

- Backend: `resultarai/app/use_cases/identity/` (login, gestión de sesión, TOTP, alta/gestión de usuarios y grupos, acuerdo de uso), `resultarai/app/api/` (endpoints REST de auth/identity), `resultarai/adapters/persistence_postgres/` (schema de cuentas/sesiones/grupos/acuerdos y su porción del audit log).
- Frontend: `frontend/` — vistas `01-login`, `02-primer-acceso`, componentes de alta de usuarios/grupos en la consola admin (`31-admin-usuarios`, `32-admin-grupos`, solo alta).
- ADR-0008 (`a01-fundacion-repo`): fija el stack de auth (sesiones server-side + Argon2id + TOTP con `pyotp`, librería Python mantenida) que este change implementa sin reabrir la decisión.
- Dependencias: requiere `a01-fundacion-repo` (esqueleto, ADR-0008), `a02-core-manifiestos` y `a03-core-gobernanza` (Policy Gate/`AuditEvent` que este change consume), `b04-persistencia-postgres` (Postgres + Alembic sobre los que se crean las tablas de identidad) y `d10-design-system-shell` (tokens, shell y componentes base que la UI de este change reutiliza) archivados o con su interfaz ya especificada.
- Habilita: `d12` a `d21` (todo requiere usuario autenticado con rol), `d16-cuotas-liberaciones` (grupos como base de cuotas), `d19-admin-operacion` (tablero admin completo sobre la base de gestión de usuarios aquí creada).
