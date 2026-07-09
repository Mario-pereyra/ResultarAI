# Tasks — d17-hitl-aprobaciones

## 1. Dominio de aprobación (core/governance — sin frameworks)

- [ ] 1.1 Definir el agregado `ApprovalRequest` (Pydantic) con sus campos: payload completo, contexto de destino (`tenant`/`environment`/`agent`/`skill`/`tool`), `risk_level`, `requires_approver_comment`, `requires_second_approval`, `expires_at`, firmas y decisión; referencia al `AuditEvent` de la decisión `escalate_hitl` origen. Verificación: `tests/core/governance/test_approval_request.py` valida construcción y campos obligatorios. `[modelo: opus]`
- [ ] 1.2 Implementar la máquina de estados pura: `pending → approved | rejected | expired`, `pending → awaiting_second_approval → approved` y `agent_suspended` (no terminal); toda transición inválida se rechaza. Verificación: `tests/core/governance/test_approval_state_machine.py` cubre la tabla de transiciones (una transición inválida levanta error). `[modelo: opus]`
- [ ] 1.3 Codificar la regla de 4 ojos y el comentario obligatorio: segundo aprobador distinto del solicitante y del primer firmante; comentario exigido en aprobación `critical` y en todo rechazo. Verificación: `tests/core/governance/test_four_eyes.py` incluye el escenario "solicitante/primer firmante como segundo aprobador → rechazado". `[modelo: opus]`
- [ ] 1.4 Implementar la política de expiración pura: cálculo de `expires_at` por TTL configurable y transición `expire` = rechazo automático. Verificación: `tests/core/governance/test_expiration.py` comprueba que el vencimiento produce estado `expired` tratado como deny. `[modelo: opus]`
- [ ] 1.5 Mapear cada transición del ciclo de vida a un `AuditEvent` inmutable (creada/aprobada por firma/rechazada/expirada/congelada). Verificación: `tests/core/governance/test_approval_audit.py` comprueba 1 `AuditEvent` por transición y ausencia de mutación. `[modelo: opus]`

## 2. Persistencia y casos de uso (app)

- [ ] 2.1 Persistencia append-only del `ApprovalRequest`, firmas y decisiones sobre el schema de `b04` (migración Alembic). Verificación: test de escritura/lectura + invariante "sin UPDATE/DELETE sobre decisiones". `[modelo: sonnet]`
- [ ] 2.2 Caso de uso "crear solicitud desde `escalate_hitl`": consume la escritura retenida de `c09` (server de ejemplo), crea el `ApprovalRequest` en `pending`, emite `AuditEvent` y notificación. Verificación: test de integración escritura simulada de `c09` → `ApprovalRequest` pendiente sin `tools/call`. `[modelo: sonnet]`
- [ ] 2.3 Casos de uso aprobar/rechazar (delegando la validación de comentario y 4 ojos al dominio) y reanudación hacia el runtime (`b06`/`c09`). Verificación: test "aprobar → se emite el `tools/call` retenido"; "rechazar → el flujo recibe el rechazo, sin ejecución". `[modelo: sonnet]`
- [ ] 2.4 Scheduler de expiración server-side: al vencer, transición `expired` + `AuditEvent` + notificación `hitl_card_expired`; aviso previo antes del vencimiento. Verificación: test con reloj simulado → `expired` auditado y notificado. `[modelo: sonnet]`
- [ ] 2.5 Reacción al kill-switch de agente (`d20`): congelar las `ApprovalRequest` pendientes del Agent marcándolas "agente suspendido" (no aprobables), preservando payload/firmas/auditoría. Verificación: test suspensión → tarjetas no aprobables y estado auditado. `[modelo: sonnet]`
- [ ] 2.6 Emisión de `hitl_approval_pending` (`d12`) al crear la solicitud y al pasar a `awaiting_second_approval`, con deep link a la Tarjeta HITL, contexto de destino y riesgo. Verificación: test que la notificación se emite al aprobador con su deep link. `[modelo: sonnet]`

## 3. Endpoints API (app)

- [ ] 3.1 Endpoints REST `/approvals`: cola (pendientes propias + segundas asignables), detalle, aprobar, rechazar e historial; autorización por capacidad **aprobador** y ownership. Verificación: tests de endpoint por rol (aprobador ve; Funcional no accede) y por estado (expirada no aprobable). `[modelo: sonnet]`

## 4. Frontend — Tarjeta HITL y vistas

- [ ] 4.1 Componente Tarjeta HITL (proyección de solo-lectura) desde `21-aprobacion-detalle.html`: payload formateado + crudo colapsable, contexto de destino, riesgo con porqué, reversibilidad, expiración abs+rel, registro de auditoría; modos lectura (solicitante) y decisión (aprobador). Verificación: render correcto por estado (`pending`, `awaiting_second_approval`, `approved`, `rejected`, `expired`). `[modelo: sonnet]`
- [ ] 4.2 Reglas por riesgo en la tarjeta: comentario obligatorio con botón "Aprobar" deshabilitado + motivo, confirmación reforzada en críticas, banda "esperando segunda aprobación (1/2)" con primera firma, y botones ocultos si el viewer ya firmó. Verificación: crítica sin comentario no habilita "Aprobar"; el primer firmante no ve botones de segunda firma. `[modelo: sonnet]`
- [ ] 4.3 Tarjeta HITL inline en el chat (`d13`) en modo lectura para el solicitante, con seguimiento de estado y resultado. Verificación: la tarjeta aparece inline y el turno queda pausado hasta la decisión. `[modelo: sonnet]`
- [ ] 4.4 Vista 20 Bandeja de aprobaciones (`20-aprobaciones-cola.html`): tabla densa/cards, orden por expiración ascendente, filtros, countdown, tag "2ª firma", y actualización por concurrencia (`aria-live`). Verificación: lista las pendientes; la sección no se renderiza para Funcional. `[modelo: sonnet]`
- [ ] 4.5 Vista 22 Historial de decisiones (`22-aprobaciones-historial.html`): columnas decisión/ejecución/comentario/payload, tabs "Mis decisiones"/"Todas" (Admin) y export CSV. Verificación: una decisión resuelta aparece con quién/cuándo/comentario/payload y resultado. `[modelo: sonnet]`
- [ ] 4.6 Portar textos UI, tags de riesgo y estados como glosario cerrado (es-BO) e i18n externalizado, usando los términos exactos del glosario (Tarjeta HITL, Segunda aprobación). Verificación: cero strings hardcodeados; claves de i18n presentes. `[modelo: haiku]`

## 5. Accesibilidad y móvil

- [ ] 5.1 Accesibilidad AA de la Tarjeta HITL (crítica, DESIGN-SYSTEM §8.14 y §10): `section` con `aria-labelledby`, foco inicial fuera de "Aprobar", riesgo por texto+color, expiración abs+rel, concurrencia por `aria-live` y operación completa por teclado y lector. Verificación: recorrido teclado + lector documentado en el PR; el foco inicial nunca cae en "Aprobar". `[modelo: sonnet]`
- [ ] 5.2 Móvil primera clase (decisión D4, DESIGN-SYSTEM §11): tarjeta y cola con botones full-width y primario abajo, payload con scroll, tabla → cards. Verificación: aprobar una solicitud en viewport 380 px registra la decisión igual que en escritorio. `[modelo: sonnet]`

## 6. Cierre

- [ ] 6.1 Test E2E del slice genérico: escritura simulada de `c09` → `escalate_hitl` → Tarjeta HITL → aprobar → reanuda ejecución (`tools/call`); y las ramas rechazo y expiración quedan auditadas. Verificación: suite E2E en verde cubriendo aprobar/rechazar/expirar. `[modelo: sonnet]`
- [ ] 6.2 Review final del change: reglas duras (core sin frameworks; escritura jamás sin aprobación; append-only), términos del glosario, cobertura de todos los escenarios de la spec y accesibilidad AA de la tarjeta. Verificación: checklist del reviewer en el PR. `[modelo: opus]`
