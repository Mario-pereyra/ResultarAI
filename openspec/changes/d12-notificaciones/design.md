# Design — d12-notificaciones

## Context

`b04-persistencia-postgres` ya entrega Postgres + Alembic, sesiones/mensajes append-only y el `audit_log`, pero ningún change anterior modela un evento dirigido a un usuario concreto que deba mostrarse fuera del flujo de chat. `d10-design-system-shell` reserva el slot de la campana en la topbar (Vista 3) pero no implementa su contenido. Este change entrega el modelo de notificación, su API y su UI, y dos tipos completos de punta a punta (liberación de cuota) aunque el motor de cuotas real (`d16`) todavía no existe: el contrato debe ser estable para que `d16`, `d17`, `e22` y `d15` lo consuman sin reabrirlo.

## Goals / Non-Goals

**Goals:**

- Modelo y persistencia de `Notification` reutilizable por cualquier bounded context futuro, sin acoplar el emisor al almacenamiento ni a la UI.
- Filtrado por ownership y por rol verificado a nivel de consulta, no solo de UI (regla dura 4: toda decisión de acceso debe ser real, no cosmética).
- Registro de tipos extensible en código, para que `d16/d17/e22/d15` agreguen su tipo sin tocar el modelo base.
- UI conforme a Vista 3 (campana) y Vista 4 (panel) de `design/VISTAS/01-acceso-shell.md`, con accesibilidad AA.

**Non-Goals:**

- Push (OS/navegador), email o webhooks — exclusión explícita del design (§3).
- Canal de entrega en tiempo real tipo WebSocket/SSE dedicado a notificaciones: este change usa **polling de intervalo corto** para el contador y el panel; no es "push", es refresco casi-en-vivo de una UI que el usuario ya tiene abierta. Se revisita si `d13-chat-conversacion` deja un canal SSE reutilizable.
- Motor de cuotas (`d16`), tarjetas HITL (`d17`), workflows (`e22`) y catálogo (`d15`): sus emisores reales.
- Purga física de notificaciones fuera de la ventana de retención (housekeeping de despliegue).
- Preferencias de notificación por usuario (opt-out por tipo, digest).

## Decisions

1. **Puerto de persistencia en `app/`, no en `core/`.** Se define `NotificationRepository` (Protocol) dentro de `app/use_cases/notifications/`, implementado por `adapters/persistence_postgres/`, en vez de ampliar `StatePort` de `core/` (definido en `a03-core-gobernanza`). Alternativa descartada: extender `StatePort` — se rechaza porque `StatePort` existe para estado sobre el que el Policy Gate y el motor de conversación razonan (sesiones, ramas, audit); una notificación no lleva ninguna decisión de política, es proyección de un evento ya autorizado. Ampliar un Protocol de `core/` para un concern sin política infla la superficie que `import-linter` y los tests de `core/` tienen que proteger, sin beneficio. Si en el futuro una notificación necesitara pasar por el Policy Gate, se mueve a `core/` en un change propio.
2. **Tabla `notifications` propia**, con `id` UUIDv7 (mismo criterio de `b04` para ordenar por clave sin depender del reloj de aplicación), `recipient_id`, `type` (texto validado contra el registro, no enum de Postgres — evita migración de esquema cada vez que `d16/d17/e22/d15` agreguen un tipo), `payload` JSONB, `deep_link` (texto o estructura mínima `{resource, id}`), `read_at` nullable (`NULL` = no leída), `created_at`.
3. **Registro de tipos en código** (`app/use_cases/notifications/types.py`): diccionario `type → (payload_schema: BaseModel, recipient_resolver, implemented: bool)`. Alternativa manifiesto YAML versionado (como agentes/skills/tools) descartada: los 6 tipos de este change no son contratos de gobernanza que un Admin publique o versione en runtime, son un catálogo interno de eventos; forzarlos al mecanismo de manifiestos sería sobre-ingeniería para el alcance actual. Se reconsidera si el catálogo de tipos necesita alguna vez edición en runtime.
4. **Emisión síncrona dentro de la misma transacción del caso de uso emisor** (por ejemplo, resolver una solicitud de liberación crea la notificación en la misma unidad de trabajo), para que nunca quede un evento de dominio sin su notificación por una falla posterior. Alternativa cola/outbox asíncrona descartada por ahora: el volumen esperado (eventos de plataforma, no eventos de negocio de alto volumen) no lo justifica; se revisita si `e22-workflows-deterministas` genera volumen alto.
5. **Retención por consulta, no por borrado físico.** El repositorio excluye de listado/conteo lo que exceda la ventana de retención de la instancia; el borrado físico (housekeeping) se deja para el runbook de `e24-despliegue-operacion`, igual que otras políticas de retención de la plataforma.
6. **Endpoint de emisión de prueba solo en tests, no en la API pública.** El escenario de extremo a extremo de `quota_release_requested`/`quota_release_resolved` (criterio "hecho cuando" de `d12` en el roadmap) se verifica invocando el contrato de emisión directamente desde un test de casos de uso, simulando el disparador que `d16` implementará; no se expone un endpoint HTTP de emisión manual en producción.

## Risks / Trade-offs

- [Polling en vez de canal en vivo] → Mitigación: intervalo corto con backoff si la pestaña está en segundo plano; el contador nunca es la única fuente de verdad crítica (a diferencia del badge de aprobaciones, que cuenta pendientes reales, no no-leídos).
- [Registro de tipos en código se vuelve inconsistente entre changes que lo extienden en paralelo] → Mitigación: cada change que agrega un tipo (`d16`, `d17`, `e22`, `d15`) lo hace en su propio PR contra `app/use_cases/notifications/types.py`, con test que verifica que el `payload_schema` declarado coincide con lo que el emisor envía.
- [El tipo `quota_release_requested`/`quota_release_resolved` se definió antes de que exista el motor de cuotas real] → Mitigación: el contrato (payload + resolución de destinatario) es lo único que este change fija; `d16` solo cambia el disparador (de un test a la ruta real de negocio), no el contrato.
- [Ventana de retención configurable pero sin purga física en este change] → Mitigación: documentado como Non-Goal explícito; la consulta ya respeta el límite, así que ningún usuario ve más allá de lo permitido aunque el dato físico persista más tiempo.

## Open Questions

- ¿El toggle de instancia para "novedades de catálogo" (apagado por defecto, mencionado en `design/FUNCIONALIDADES.md` §3) se implementa en `d20-gobernanza-plataforma` (configuración de instancia) o en `d15-catalogo-agentes` (que es quien emite el tipo)? Queda abierto para quien tome ese change; `d12` no lo decide, solo registra el tipo `catalog_news`.
- ¿La purga física de notificaciones fuera de retención se agrega a `e24-despliegue-operacion` como tarea genérica de housekeeping (junto con adjuntos) o merece su propio job? Se deja para cuando `e24` se especifique.
