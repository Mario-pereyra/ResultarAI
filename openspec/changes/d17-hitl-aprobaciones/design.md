# Design — d17-hitl-aprobaciones

## Context

`a03` definió el contrato de dominio de HITL (efecto `escalate_hitl`, `requires_approver_comment`, `requires_second_approval`, `AuditEvent`) y `c09` fijó que toda Tool de escritura escala SIEMPRE a HITL y el cliente MCP NO emite `tools/call` mientras no haya aprobación. `b06` deja el turno "en espera de aprobación humana". Nada de eso es todavía operable por un humano. Este change (slice vertical backend + UI, 100% genérico) construye la pieza que faltaba: la **Tarjeta HITL** y su ciclo de aprobación, ejercida contra la **escritura simulada** del MCP Server de ejemplo de `c09`. La fuente normativa de UX es `design/VISTAS/05-hitl-validacion.md` (vistas 20/21/22), depurada de todo lo Protheus (vistas 27/28/29 son Etapa P).

## Goals / Non-Goals

**Goals:**

- Materializar `escalate_hitl` en una decisión humana trazable: sin decisión, ninguna escritura se ejecuta (regla dura 4).
- Reglas por riesgo de `a03` operativas: comentario obligatorio en críticas, segunda aprobación de 4 ojos en irreversibles con el solicitante excluido.
- Expiración server-side = rechazo automático auditado; bandeja, detalle e historial; reanudación hacia el runtime; móvil primera clase; accesibilidad AA de la tarjeta.

**Non-Goals:**

- Selector cliente/ambiente, checklists y bridge (Etapa P); motor de workflows (`e22` reutiliza la MISMA tarjeta); Tools de escritura reales (solo la simulada de `c09`); definir la clasificación de riesgo o el efecto `escalate_hitl` (viven en `c09` / `a03`); push/email.

## Decisions

1. **La Solicitud de aprobación (`ApprovalRequest`) es un agregado de dominio con máquina de estados pura en `core/governance/`.** Estados: `pending → approved | rejected | expired`, más `pending → awaiting_second_approval → approved` (irreversibles) y `agent_suspended` (congelamiento por kill-switch, no terminal). La lógica (transiciones válidas, regla de 4 ojos, cálculo de expiración) es pura, sin I/O ni frameworks (regla dura 1); la persistencia (`b04`), los endpoints y la UI viven en `app/` y `frontend/`. Alternativa descartada: lógica en el servicio de aplicación — pierde testabilidad y viola la frontera del núcleo.

2. **La Tarjeta HITL es una única proyección de solo-lectura del `ApprovalRequest`, reusada en tres superficies.** La MISMA tarjeta se embebe inline en el chat (`d13`, solicitante en modo lectura), en el detalle de la cola (vista 21, aprobador con botones) y —a futuro— en la pausa de workflow (`e22`). Alternativa descartada: componentes separados por superficie — divergen y duplican la lógica de riesgo/expiración.

3. **La regla de 4 ojos se valida en el dominio, no en la UI.** El segundo aprobador debe ser distinto del solicitante Y del primer firmante; el intento del mismo usuario se RECHAZA en `core/governance`, no se limita a ocultar el botón. Ocultar botones (§9.7 del design) es refuerzo de UX, no la barrera de seguridad.

4. **La aprobación registrada ES la autorización que habilita la ejecución del paso retenido.** No se re-abre el Policy Gate para forzar un `allow` mágico: `c09` mantiene que una escritura siempre escala; lo que la aprobación produce es la señal de reanudación hacia el runtime (`b06`) para que el cliente MCP emita el `tools/call` antes retenido. El rechazo produce un deny efectivo que el flujo recibe con su razón. Desacople vía evento/port de reanudación, no llamada directa entre capas.

5. **La expiración es server-side y auditada.** El `expires_at` (TTL configurable por nivel de riesgo / instancia) se evalúa en el servidor; al vencer, una transición `expire` = rechazo automático que emite `AuditEvent`. El countdown de la UI es solo presentación; nunca la fuente de verdad. Aviso previo vía `d12`; expiración emite `hitl_card_expired`. Alternativa descartada: expiración solo en el cliente — no auditable y evadible.

6. **El kill-switch (`d20`) congela, no cancela.** Suspender un Agent marca sus `ApprovalRequest` pendientes "agente suspendido" (no aprobables) preservando payload, firmas y auditoría, en vez de rechazarlas en silencio. `d20` es posterior en el roadmap: este change define la reacción al evento de suspensión; `d20` provee el disparador.

7. **Móvil primera clase (decisión D4 del design) y accesibilidad AA como requisito, no adorno.** La Tarjeta HITL es el componente más crítico (§8.14): `section` con `aria-labelledby`, foco inicial fuera de "Aprobar", riesgo por texto+color, expiración absoluta+relativa, concurrencia por `aria-live`; en móvil botones full-width con primario abajo. La verificación AA (teclado + lector) es tarea propia, no un extra opcional.

## Risks / Trade-offs

- **[Aprobación accidental de una escritura]** → Mitigación: foco inicial fuera de "Aprobar", comentario obligatorio + confirmación reforzada en críticas, segunda aprobación en irreversibles.
- **[Drift entre el countdown de la UI y el `expires_at` real]** → Mitigación: la expiración es server-side y auditada; el countdown es solo visual y tolera degradación ("expiración sin sincronizar").
- **[Evasión de la regla de 4 ojos]** → Mitigación: se valida en `core/governance` (solicitante ≠ primer firmante ≠ segundo aprobador), cubierta por test; la UI solo refuerza.
- **[Acoplamiento de la reanudación con `b06`/`c09`]** → Mitigación: la reanudación se emite como evento hacia un port del runtime, no como llamada directa; el dominio no importa el runtime (regla dura 1).
- **[Condición de carrera en la segunda aprobación / concurrencia]** → Mitigación: la transición de estado es la única fuente de verdad (append-only); una segunda decisión sobre una solicitud ya resuelta se rechaza y se anuncia por `aria-live`.

## Open Questions

*(ninguna bloqueante — el mecanismo del scheduler de expiración y el esquema de persistencia se concretan sobre `b04`; el disparador del kill-switch llega con `d20`, cuyo contrato de evento este change ya honra.)*
