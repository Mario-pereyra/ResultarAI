# Tasks — d12-notificaciones

## 1. Modelo y persistencia

- [x] 1.1 Migración Alembic: tabla `notifications` (`id` UUIDv7, `recipient_id`, `type`, `payload` JSONB, `deep_link`, `read_at` nullable, `created_at`) con índices por `(recipient_id, created_at)` y `(recipient_id, read_at)`. Verificación: `alembic upgrade head` and `alembic downgrade -1` corren limpio sobre Postgres local. `[modelo: sonnet]`
- [x] 1.2 Definir `NotificationRepository` (Protocol) en `app/use_cases/notifications/ports.py` e implementarlo en `adapters/persistence_postgres/notifications.py` (crear, listar paginado, contar no-leídas, marcar leída, marcar todas leídas), filtrando siempre por `recipient_id` del usuario autenticado. Verificación: contract test cubre las 5 operaciones contra Postgres real, incluido el escenario "Notificación creada con los campos mínimos". `[modelo: sonnet]`

## 2. Registro de tipos y contrato de emisión

- [x] 2.1 Crear `app/use_cases/notifications/types.py`: registro de los 6 tipos (`quota_release_requested`, `quota_release_resolved`, `hitl_approval_pending`, `hitl_card_expired`, `workflow_finished`, `catalog_news`) con `payload_schema` Pydantic, `recipient_resolver` y flag `implemented`. Verificación: test unitario recorre el registro y valida que los 2 primeros tienen `implemented=True` y los otros 4 `implemented=False` (escenarios "Consulta del registro..."). `[modelo: sonnet]`
- [x] 2.2 Implementar `emit_notification(type, recipient, payload, deep_link)` en `app/use_cases/notifications/emit.py`: valida `payload` contra el `payload_schema` del tipo y rechaza tipos no registrados. Verificación: test cubre "Emisión desde un caso de uso externo" y "Emisión rechazada para un tipo no registrado". `[modelo: sonnet]`

## 3. Extremo a extremo — liberación de cuota

- [x] 3.1 Caso de uso de prueba `request_quota_release_test_trigger` (sin motor de cuotas real, ver `design.md` decisión 6) que invoca `emit_notification(quota_release_requested, ...)` para cada Admin del tenant, con `payload` (solicitante, cuota afectada, consumo actual). Verificación: test cubre "Solicitud de liberación notifica a todos los Admin del tenant" con más de un Admin en el tenant. `[modelo: sonnet]`
- [x] 3.2 Caso de uso de prueba `resolve_quota_release_test_trigger` que invoca `emit_notification(quota_release_resolved, ...)` para el solicitante original con la decisión. Verificación: test cubre "El solicitante es notificado de la decisión" (concedida y denegada). `[modelo: sonnet]`

## 4. Endpoints `app/api`

- [x] 4.1 `GET /notifications` paginado (clásico) con filtro opcional `status=unread|read|all`, orden por `created_at` descendente, filtrado por `recipient_id = usuario autenticado`. Verificación: test cubre "Listar solo no leídas", "Paginación no devuelve todo el historial de una vez" y "Un usuario no ve las notificaciones de otro". `[modelo: sonnet]`
- [x] 4.2 `GET /notifications/unread-count`. Verificación: test cubre "El contador refleja el estado real de no-leídas". `[modelo: sonnet]`
- [x] 4.3 `POST /notifications/{id}/read`: marca leída si `recipient_id` coincide con el usuario autenticado; responde como recurso inexistente si no coincide (nunca filtra su existencia). Verificación: test cubre "Marcar una notificación como leída" y "Acceso directo a una notificación ajena es rechazado". `[modelo: sonnet]`
- [x] 4.4 `POST /notifications/read-all`: marca leídas todas las notificaciones visibles del usuario autenticado. Verificación: test cubre "Marcar todas las notificaciones como leídas". `[modelo: sonnet]`
- [x] 4.5 Verificar que la resolución de destinatario de tipos reservados a rol (p. ej. `quota_release_requested` → Admin) excluye a usuarios sin ese rol incluso si comparten tenant. Verificación: test cubre "Un usuario sin rol Admin nunca recibe una notificación reservada a Admin". `[modelo: sonnet]`

## 5. Frontend — campana y panel (Vista 3 y Vista 4)

- [x] 5.1 Componente `.notif-bell` con badge de no-leídas integrado a la topbar del shell (`d10-design-system-shell`), con polling de intervalo corto para refrescar el conteo (ver `design.md`: no es push). Verificación: cubre "El indicador se oculta en cero" y "Llegada en vivo actualiza el contador sin robar foco" con mock de polling. `[modelo: sonnet]`
- [x] 5.2 Panel dropdown de escritorio (380 px, max-height 70vh) agrupado por kicker de familia de tipo, con skeleton de carga y error-card con reintentar. Verificación: cubre "Los grupos sin elementos no aparecen" y "Estado vacío cuando no hay notificaciones". `[modelo: sonnet]`
- [x] 5.3 Sheet a pantalla completa en móvil (<768 px) con header fijo y cierre. Verificación: cubre "En móvil el panel ocupa toda la pantalla" con test responsive. `[modelo: sonnet]`
- [x] 5.4 Navegación por click/«Ver» hacia `deep_link` que marca la notificación como leída como efecto de la navegación; si el origen ya cambió de estado (resuelto/expirado), mostrar su estado final en vez de un error. Verificación: cubre "Click en una notificación navega y marca leído" y "El origen ya no existe en su estado original". `[modelo: sonnet]`
- [x] 5.5 Vista «Ver todas»: listado completo paginado más allá del máximo mostrado en el dropdown. Verificación: cubre "Ver todas abre el listado completo". `[modelo: sonnet]`
- [x] 5.6 Accesibilidad AA del panel: navegación por teclado (flechas entre ítems, Enter abre, Esc cierra y devuelve foco a la campana), región `aria-live` para llegadas en vivo. Verificación: cubre "Navegación completa por teclado" con test de teclado y auditoría axe sin violaciones AA. `[modelo: sonnet]`
- [x] 5.7 Externalizar los textos del panel (kickers, estado vacío, acciones) al catálogo i18n de `d10`, sin strings hardcodeados en componentes. Verificación: claves presentes en el catálogo ES; lint de i18n en verde. `[modelo: haiku]`

## 6. Retención

- [x] 6.1 Aplicar la ventana de retención configurable por instancia en `list`/`count_unread` del repositorio (excluye lo que la supera). Verificación: cubre "Notificaciones fuera de la ventana de retención no se listan". `[modelo: sonnet]`

## 7. Cierre

- [x] 7.1 Fixtures de notificaciones de ejemplo para desarrollo local (uno de cada tipo implementado, una leída y una no-leída). Verificación: el seed corre sin error y puebla ambos tipos implementados. `[modelo: haiku]`
- [x] 7.2 Review final del change: consistencia proposal↔specs↔design↔tasks, ownership verificado en cada endpoint, cero menciones a push/email/webhooks, y lista de términos nuevos para `docs/03-glosario-dominio.md` (Notificación, Centro de notificaciones, Liberación de cuota, Solicitud de liberación) reportada para su incorporación. Verificación: checklist del reviewer en el PR. `[modelo: opus]`
