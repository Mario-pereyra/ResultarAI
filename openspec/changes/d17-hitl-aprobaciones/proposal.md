# Proposal — d17-hitl-aprobaciones

## Why

El Policy Gate (`a03`) ya devuelve `escalate_hitl` para toda Tool de escritura (`c09`) y el runtime (`b06`) deja el turno "en espera de aprobación humana", pero nadie materializa esa espera: hoy una escritura escalada queda retenida sin forma de que un humano la resuelva de manera trazable. Este change construye la **Tarjeta HITL** operativa —el componente más crítico del producto (DESIGN-SYSTEM §8.14)— que convierte cada `escalate_hitl` en una decisión humana auditada, sin la cual ninguna escritura se ejecuta (regla dura 4).

## What Changes

- Se crea la capacidad `hitl-approvals`: dominio de aprobación (una **Solicitud de aprobación** con máquina de estados pura en `core/governance`), casos de uso, endpoints y frontend, 100% genérico (sin nada Protheus).
- **Tarjeta HITL**: qué se va a ejecutar en lenguaje claro, payload completo, contexto de destino (tenant · environment · agent · skill · tool), nivel de riesgo con su porqué, expiración visible y botones Aprobar/Rechazar; aparece inline en el chat (`d13`) o pausa el flujo (`b06`); la ejecución NUNCA ocurre sin decisión.
- **Reglas por riesgo** (contratos de `a03`): comentario del aprobador obligatorio en acciones críticas (`requires_approver_comment`); **segunda aprobación de 4 ojos** en irreversibles (`requires_second_approval`), con el solicitante y el primer firmante excluidos; estado "esperando segunda aprobación" visible.
- **Expiración**: tiempo de vida configurable; al vencer = rechazo automático auditado; aviso previo vía notificaciones (`d12`).
- **Bandeja de aprobaciones** (vista 20), **detalle** (vista 21) e **Historial de decisiones** (vista 22) con quién/cuándo/comentario/payload y resultado de ejecución; **móvil primera clase** (decisión D4); sección oculta para roles sin capacidad aprobador (matriz de visibilidad).
- **Reanudación**: al aprobar, la ejecución continúa (evento hacia runtime `b06` / Tool `c09`); al rechazar, el flujo recibe el rechazo con su razón; el kill-switch de agente (`d20`) congela sus tarjetas pendientes marcándolas "agente suspendido".
- **Auditoría integral**: creada/aprobada/rechazada/expirada → `AuditEvent` inmutable.
- Se emiten los tipos de notificación `hitl_approval_pending` y `hitl_card_expired` registrados en `d12`.

## Capabilities

### New Capabilities

- `hitl-approvals`: Tarjeta HITL, reglas por riesgo (comentario obligatorio, 4 ojos), expiración como rechazo auditado, bandeja e historial, reanudación hacia el runtime y auditoría integral del ciclo de vida de la aprobación.

### Modified Capabilities

*(ninguna — `a03`, `c09`, `b06` y `d12` solo se referencian: este change materializa sus contratos, no cambia sus requirements)*

## No-objetivos

- Sin selector cliente/ambiente (vista 27), checklists (vistas 28/29) ni bridge tat-mcp — todo eso es **Etapa P**.
- Sin motor de workflows: `e22-workflows-deterministas` reutiliza la MISMA Tarjeta HITL para su pausa; este change no construye workflows.
- Sin Tools de escritura reales: la única escritura ejercida es la **escritura simulada del MCP Server de ejemplo** de `c09`.
- No define la clasificación lectura/escritura/riesgo (vive fija por versión en `c09`) ni el efecto `escalate_hitl` ni el contrato reforzado de riesgo (viven en `a03`).
- Sin niveles N por ambiente, sin SQL, sin ERP.
- Sin push ni email: las notificaciones son in-app (`d12`); este change solo emite sus tipos ya registrados.

## Bounded context afectado

`governance`, en tres capas:

- **core** (`resultarai/core/governance/`): la máquina de estados de la Solicitud de aprobación, la regla de 4 ojos y la política de expiración como lógica pura, sin frameworks (regla dura 1).
- **app** (`resultarai/app/`): casos de uso, endpoints de aprobaciones, reanudación hacia el runtime y emisión de notificaciones.
- **frontend**: Tarjeta HITL inline en el chat, cola (vista 20), detalle (vista 21) e historial (vista 22).

## Impact

- `resultarai/core/governance/` (dominio de aprobación), `resultarai/app/` (endpoints `/approvals`, casos de uso, reanudación), `frontend/` (3 vistas + tarjeta inline en chat).
- Consume contratos de `a03` (`PolicyDecision.effect`, `requires_approver_comment`, `requires_second_approval`, `AuditEvent`), `c09` (escritura escalada retenida), `b06` (turno en espera / reanudación), `d12` (notificaciones `hitl_approval_pending` / `hitl_card_expired`), `d13` (chat inline) y `d20` (kill-switch de agente).
- Referencia del blueprint: capa 1 (gobernanza) y el patrón P0 "Human-in-the-loop approval" — este change lo materializa como producto sin implementar aún ninguna escritura real de negocio.
