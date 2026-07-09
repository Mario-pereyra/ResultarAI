# Tasks — d16-cuotas-liberaciones

## 1. Modelo y motor de la Cuota (core/governance)

- [ ] 1.1 Schema Pydantic de la Cuota en `core/governance/quota.py`: alcances `global`/`grupo`/`usuario`/`sesion`, límite en unidad de presupuesto de instancia, período, umbral de aviso, y resolución default/override (override prevalece). Test: `tests/core/test_quota_model.py` cubre "Entidad sin override toma el default de instancia" y "Override por entidad prevalece sobre el default". `[modelo: opus]`
- [ ] 1.2 Motor de evaluación jerárquica puro en `core/governance/quota_evaluation.py`: recibe consumo por alcance + límites + costo estimado, devuelve autoriza/bloquea + alcance bloqueante; deny si algún alcance sin margen; determinista, sin I/O ni reloj. Test: `tests/core/test_quota_evaluation.py` cubre "El alcance más restrictivo determina el margen", "Todos los alcances con margen permiten el turno", "Cuota diaria agotada con cuota mensual sana" y "Evaluación determinista". `[modelo: opus]`
- [ ] 1.3 Estimación de costo con tarifas de cache hit/miss separadas del perfil de modelo + reconciliación con el `usage` real, en `core/governance/quota_cost.py`. Test: `tests/core/test_quota_cost.py` cubre "La estimación aplica ambas tarifas del perfil" y "El consumo real reconcilia la reserva". `[modelo: opus]`
- [ ] 1.4 Renovación diaria a medianoche en zona horaria de instancia: el "inicio de período vigente" entra como parámetro puro al motor (sin leer reloj en core). Test: `tests/core/test_quota_renewal.py` cubre "A medianoche el consumo diario vuelve a cero" y "La renovación usa la zona horaria de la instancia, no UTC fija". `[modelo: opus]`

## 2. Reserva atómica, consumo y persistencia (app + adapters)

- [ ] 2.1 Reserva atómica reserve-then-reconcile contra los 4 alcances (decremento atómico / bloqueo optimista sobre `b04-persistencia-postgres`) en `app/use_cases/quotas/reserve.py`. Test de concurrencia: dos reservas concurrentes cerca del límite → exactamente una autoriza y el consumo del alcance nunca supera su límite (cubre "Dos llamadas concurrentes cerca del límite no sobregastan" y "La reserva atómica evita la condición de carrera"). `[modelo: opus]`
- [ ] 2.2 Caso de uso `check_and_reserve_quota` invocado ANTES de cada llamada al modelo, integrado con el gateway (`LLMPort`, `b05`); bloqueo → estado `QUOTA`, autoriza → emite la llamada. Test de contrato: cubre "Sin margen no se emite la llamada al modelo" y "Acción policy-allowed pero sin margen de Cuota". `[modelo: sonnet]`
- [ ] 2.3 Reconciliación del consumo real desde los contadores de cache hit/miss del `usage` tras la respuesta, en `app/use_cases/quotas/record.py`. Test de contrato: el consumo registrado usa las tarifas hit/miss del perfil y reemplaza la reserva estimada. `[modelo: sonnet]`
- [ ] 2.4 Migración Alembic: tablas de consumo por alcance/período y de reserva. Verificación: `alembic upgrade head` y `alembic downgrade -1` corren limpio sobre Postgres local. `[modelo: sonnet]`

## 3. Umbrales, aviso, bloqueo y textos

- [ ] 3.1 Defaults de instancia (límites por alcance, umbral 80%, zona horaria) como configuración leída, no constantes de código, en la config de instancia. Verificación: cambiar el umbral en config lo refleja en la evaluación sin tocar código. `[modelo: haiku]`
- [ ] 3.2 Emisión del estado de aviso al cruzar el umbral (por alcance) y del estado de bloqueo `QUOTA` al 100%, en `app/use_cases/quotas/thresholds.py`. Test de contrato: cubre "Aviso al cruzar el 80% sin bloquear", "Umbral configurado distinto del default" y "100% bloquea con estado QUOTA". `[modelo: sonnet]`
- [ ] 3.3 Textos accionables del estado `QUOTA` y del aviso 80% (ES voseo, externalizados en el catálogo i18n de `d10`; "se renueva a medianoche"; el código `QUOTA` no se traduce). Verificación: claves i18n presentes; lint de i18n en verde. `[modelo: haiku]`

## 4. Liberaciones (quota-releases)

- [ ] 4.1 Contrato de dominio de la Liberación en `core/governance/quota_release.py`: solicitud (solicitante, alcance bloqueado, consumo, motivo), tipo `puntual`/`permanente`, monto adicional, vencimiento, estados `pendiente`/`concedida`/`denegada`. Test: `tests/core/test_quota_release_model.py` cubre el ciclo de estados y el alcance/vencimiento de la ampliación. `[modelo: opus]`
- [ ] 4.2 Caso de uso "solicitar Liberación" desde el bloqueo (motivo obligatorio) → `AuditEvent` `QUOTA_RELEASE_REQUESTED` + `emit_notification(quota_release_requested, ...)` a cada Admin del tenant (contrato de `d12`). Test de contrato: cubre "El bloqueo permite solicitar con motivo" y "Motivo obligatorio". `[modelo: sonnet]`
- [ ] 4.3 Caso de uso "resolver Liberación" del Admin: aprobar `puntual`/`permanente` con monto (aplica alcance + vencimiento) o denegar con comentario obligatorio → `AuditEvent` `QUOTA_RELEASE_APPROVED`/`_DENIED` + `emit_notification(quota_release_resolved, ...)` al solicitante. Test de contrato: cubre "Aprobación puntual con monto adicional", "Denegación exige comentario", "Ampliación puntual vence al fin del período" y "Ampliación permanente eleva el límite hasta nuevo cambio". `[modelo: sonnet]`
- [ ] 4.4 Desbloqueo inmediato: la próxima evaluación de Cuota considera el monto adicional sin re-login. Test de contrato E2E: cubre "El próximo turno pasa el check tras aprobar". `[modelo: sonnet]`
- [ ] 4.5 Resolución única bajo Admins concurrentes: el segundo intento recibe conflicto ("ya resuelta por …") sin sobrescribir ni re-notificar. Test de concurrencia: cubre "Dos Admin resuelven la misma solicitud". `[modelo: opus]`
- [ ] 4.6 Re-solicitud tras agotar o denegar, referenciando la Liberación anterior del período. Test de contrato: cubre "Segunda solicitud referencia la anterior". `[modelo: sonnet]`

## 5. Mi consumo y endpoints (frontend, vista 23)

- [ ] 5.1 Endpoint de Mi consumo (día/mes contra Cuota, sesiones recientes, capa por rol) estrictamente personal por ownership. Test de contrato: cubre "Un usuario nunca ve el consumo de otro" y la capa por rol (Funcional sin tokens/cache/modelos; Técnico con tokens; Admin con telemetría). `[modelo: sonnet]`
- [ ] 5.2 Endpoint de Mis solicitudes de Liberación con su estado (`pendiente`/`concedida`/`denegada`) y motivo/comentario. Test de contrato: cubre "Concedida recalcula la barra; denegada muestra el motivo". `[modelo: sonnet]`
- [ ] 5.3 Vista 23 Mi consumo (`design/VISTAS/06-mi-espacio.md`): tarjetas hoy/mes, estados normal/aviso/bloqueado, capa por rol, `aria-live` al cruzar el 80%, acción "Solicitar liberación" y su estado en curso. Verificación: los 3 sets por rol renderizan lo esperado (Funcional sin columnas de tokens/cache); cubre "La barra pasa a aviso con la vista abierta" y "En bloqueo aparece la acción de Liberación". `[modelo: sonnet]`
- [ ] 5.4 Integración del aviso 80% (composer) y del bloqueo `QUOTA` con botón "Solicitar liberación" en el chat (`d13-chat-conversacion`, `design/FLUJOS.md` Flujo E pasos 1–3). Verificación: al 80% aviso no intrusivo; al 100% composer deshabilitado con estado `QUOTA`. `[modelo: sonnet]`
- [ ] 5.5 Bandeja del Admin (tabs **Solicitudes** e **Historial** de `design/VISTAS/07-admin-operacion.md` vista 33): cards con consumo/motivo, aprobar (puntual/permanente + monto) / denegar (comentario), contador en vivo e historial de resueltas. Verificación: aprobar mueve la solicitud a Historial y notifica; cubre el flujo del Flujo E pasos 5–6. `[modelo: sonnet]`

## 6. Cierre

- [ ] 6.1 Fixtures de desarrollo: cuotas de ejemplo por alcance, una sesión al 82% (aviso) y un usuario al 100% con una Liberación `pendiente`. Verificación: el seed corre sin error y reproduce los tres estados de barra. `[modelo: haiku]`
- [ ] 6.2 Prueba de aceptación E2E del Flujo E completo (`design/FLUJOS.md`): 80% aviso → 100% bloqueo `QUOTA` → solicitud con motivo → notificación al Admin → aprobación → desbloqueo inmediato → cadena auditada visible en Mi consumo. Verificación: el escenario E2E pasa de punta a punta. `[modelo: sonnet]`
- [ ] 6.3 Review final del change: consistencia proposal↔specs↔design↔tasks, `core/` sin frameworks, motor de evaluación puro y testeado sin red, concurrencia sin gasto doble, cadena de Liberación auditada, y reporte de términos nuevos para `docs/03-glosario-dominio.md` (Cuota, Liberación) para su incorporación. Verificación: checklist del reviewer en el PR. `[modelo: opus]`
