# Proposal — d12-notificaciones

## Why

`d16-cuotas-liberaciones` necesita avisar al Admin cuando alguien solicita liberar una cuota bloqueada y avisar al solicitante de la decisión; `d17-hitl-aprobaciones`, `e22-workflows-deterministas` y `d15-catalogo-agentes` necesitan el mismo mecanismo para sus propios eventos. Sin un centro de notificaciones genérico ni un contrato de emisión compartido, cada change futuro reinventaría su propio canal de aviso, con filtrado por rol/ownership inconsistente. Este change entrega ese mecanismo ahora, como pieza de plataforma reutilizable, siguiendo [design/FUNCIONALIDADES.md](../../../design/FUNCIONALIDADES.md) §3 y la vista 4 de [design/VISTAS/01-acceso-shell.md](../../../design/VISTAS/01-acceso-shell.md).

## What Changes

- Se añade el **modelo de notificación** (`Notification`): tipo, destinatario (`user_id`), payload estructurado, estado leída/no-leída, deep link al origen (sesión, tarjeta HITL, solicitud), timestamps.
- Se añade el **contrato genérico de emisión** que cualquier bounded context de la plataforma usa para crear una notificación (tipo + destinatario + payload + deep link), sin acoplarse a cómo se renderiza ni se entrega.
- Se define el **registro de tipos de notificación**: los dos tipos que este change emite de punta a punta (`quota_release_requested` → Admin, `quota_release_resolved` → solicitante) y los tipos que solo se **registran** aquí (payload y destinatario documentados) para que `d17-hitl-aprobaciones`, `e22-workflows-deterministas` y `d15-catalogo-agentes` los emitan cuando existan: aprobación HITL pendiente, expiración de tarjeta HITL, workflow terminado/fallido, novedad de catálogo.
- Se añaden **endpoints** (`app/api`): listar notificaciones propias (paginado, filtrado por leída/no-leída), contar no-leídas, marcar leída (individual y masiva), sin exponer nunca notificaciones de otro usuario.
- Se añade la **UI** (`frontend/`): campana con indicador de no-leídas integrada en el shell (`d10-design-system-shell`), panel dropdown (vista 4) con lista agrupada, marcar leído, click-para-ir-al-origen; sheet a pantalla completa en móvil.
- Se aplican **retención y paginación** (notificaciones antiguas no crecen sin límite) y **accesibilidad AA** del panel (teclado, foco, `aria-live` para llegadas en vivo).

## Capabilities

### New Capabilities

- `notifications`: modelo de notificación, contrato genérico de emisión, registro de tipos (implementados y solo-registrados), endpoints de lectura/marcado con filtrado por rol y ownership, UI de campana y panel, retención/paginación y accesibilidad AA.

### Modified Capabilities

*(ninguna — `openspec/specs/` está vacío; no existen specs previas)*

## No-objetivos

- **Sin push ni email ni webhooks**: exclusión explícita del design (§3 "Sin push ni email en MVP: todo es in-app"). Ningún canal fuera de la app.
- **Sin preferencias de notificación avanzadas** (opt-out granular por tipo, digest, horarios de silencio): la única configuración de instancia prevista en el design es el on/off de "novedades de catálogo" (F2), fuera de alcance de este change.
- **Sin los emisores específicos de HITL/workflows/catálogo**: sus eventos reales los disparan `d17-hitl-aprobaciones`, `e22-workflows-deterministas` y `d15-catalogo-agentes` respectivamente, usando el contrato de emisión de este change. Aquí solo quedan registrados como tipos con su payload y destinatario documentados.
- **Sin motor de cuotas**: `d16-cuotas-liberaciones` define cuándo y con qué datos reales se dispara `quota_release_requested`/`quota_release_resolved`; este change entrega el tipo, su contrato de payload y una emisión de extremo a extremo verificable con un disparador de prueba, no el cálculo de cuotas.
- **Sin telemetría ni analítica de notificaciones** (tasas de apertura, etc.): fuera del alcance de `d12`.

## Bounded context afectado

`app/` (casos de uso y `app/api` de notificaciones) y `frontend/` (campana + panel del shell). El modelo `Notification` y el registro de tipos son estado de aplicación, no política ni negocio de `core/`: no se toca `core/`, `adapters/` ni `manifests/`. Depende de la persistencia de `b04-persistencia-postgres` (tabla propia) y del shell de `d10-design-system-shell` (slot de la campana en la topbar).

## Impact

- `resultarai/app/use_cases/notifications/`: casos de uso de emisión, listado, conteo y marcado; registro de tipos con su payload y regla de destinatario.
- `resultarai/app/api/`: endpoints REST de notificaciones (listar, contar no-leídas, marcar leída individual/masiva).
- `resultarai/adapters/persistence_postgres/`: tabla `notifications` + repositorio (migración Alembic).
- `frontend/`: componente `.notif-bell` + panel dropdown/sheet (vista 4 de `design/VISTAS/01-acceso-shell.md`), integrado al shell de `d10`.
- Referencia de diseño: `design/FUNCIONALIDADES.md` §3 (Notificaciones) y `design/VISTAS/01-acceso-shell.md` Vista 4 (Panel de notificaciones), fuentes normativas de este change.
