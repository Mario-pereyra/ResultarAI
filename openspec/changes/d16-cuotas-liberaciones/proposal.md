# Proposal — d16-cuotas-liberaciones

## Why

La plataforma es cache-first y su economía depende de que el consumo por modelo esté acotado: sin cuotas, un usuario o una sesión puede vaciar el presupuesto de toda la instancia en una tarde, y hoy no existe ningún freno antes de llamar al modelo. El design (`design/FLUJOS.md` Flujo E, `design/FUNCIONALIDADES.md` §4/§10/§11) fija el mecanismo: cuota jerárquica evaluada ANTES de cada llamada LLM, aviso al 80%, bloqueo claro al 100% con una vía accionable —solicitar liberación— que el Admin resuelve y que desbloquea al instante. Este change materializa ese slice vertical (backend + UI) sobre los contadores de cache hit/miss ya expuestos por `b05-gateway-modelos`.

## What Changes

- Se introduce la **Cuota** jerárquica en cuatro alcances anidados (global → grupo → usuario → sesión), todos configurables; los defaults son configuración de instancia, no constantes de código.
- Se evalúa la cuota **antes de CADA llamada LLM** estimando el costo del turno con las tarifas de cache hit/miss separadas por perfil de modelo (contadores de `b05`); si algún alcance no alcanza, la llamada no se emite.
- Se agregan los **umbrales**: aviso no intrusivo al 80% (configurable por instancia) visible en el composer y en Mi consumo; al 100% el composer se bloquea con el estado `QUOTA` accionable y el botón "Solicitar liberación".
- Se introduce la **Liberación**: solicitud del usuario con motivo breve → notificación al Admin (vía `d12-notificaciones`) → bandeja de cuotas del Admin (aprobar ampliación puntual o permanente / denegar con motivo) → notificación al solicitante y desbloqueo inmediato; toda la cadena emite `AuditEvent`.
- Se agrega **renovación diaria a medianoche** en la zona horaria de la instancia para las cuotas de alcance diario.
- Se agrega **Mi consumo** (vista 23): consumo del día y del mes contra la cuota, con capa por rol (Funcional ve % y "espacio usado" sin tokens ni modelos; Técnico/Admin ven tokens y costo), más **Mis solicitudes de liberación** con su estado.

## Capabilities

### New Capabilities

- `quotas`: modelo de Cuota jerárquica (global/grupo/usuario/sesión) con defaults de instancia; motor de evaluación pre-llamada con estimación por tarifas hit/miss; umbrales de aviso (80%) y bloqueo (100%); renovación diaria a medianoche; consistencia bajo llamadas concurrentes cerca del límite.
- `quota-releases`: solicitud de Liberación con motivo, decisión del Admin (ampliación puntual o permanente / denegación con motivo), alcance y vencimiento de la ampliación, desbloqueo inmediato, y auditoría de toda la cadena.
- `consumption-view`: Mi consumo (día/mes contra cuota, capa por rol) y Mis solicitudes de liberación con estado, conforme a la vista 23.

### Modified Capabilities

*(ninguna — las tres capacidades son nuevas; `quotas` consume el contrato de tarifas hit/miss de `model-profiles`/`model-gateway` de `b05` y el contrato de emisión de `notifications` de `d12`, sin modificar sus requirements)*

## No-objetivos

- Sin FinOps avanzado ni chargeback por tenant (Etapa P): nada de facturación, reportes financieros ni imputación de costos entre clientes.
- Sin presupuestos por tenant en despliegues multi-instancia: la instancia es de un solo tenant operativo; la Cuota global es el techo de la instancia.
- Sin notificaciones nuevas: se usan los tipos `quota_release_requested` y `quota_release_resolved` ya definidos en `d12-notificaciones`; este change los dispara, no crea infraestructura de notificación.
- Sin telemetría/analítica agregada de consumo por Admin (consumo por grupo/agente/modelo, top sesiones caras, export CSV): eso vive en `d19-admin-operacion`. Aquí solo la capa personal de Mi consumo.
- Sin la consola de edición de cuotas del Admin (tab Cuotas de la vista 33 con overrides por fila): el alcance de este change es la bandeja de solicitudes/liberaciones; la CRUD de defaults y overrides por alcance se especifica junto a `d19-admin-operacion` / configuración de instancia. Este change asume las cuotas como configuración leída.
- Sin escalación a Pro ni fallback de modelo (viven en `b05`/`d13`); la Cuota solo lee las tarifas del perfil que efectivamente responderá.

## Bounded context afectado

- **`governance` en `core/`**: el modelo de dominio de la Cuota, la jerarquía de alcances, el motor de evaluación pre-llamada (función pura sobre snapshots de consumo y límites) y el contrato de la Liberación. Sin frameworks (solo stdlib + Pydantic), consistente con la regla de dependencia de `docs/02-arquitectura.md`.
- **`app/`**: casos de uso de reserva/registro de consumo, solicitud y resolución de liberación, y endpoints de Mi consumo; integra `LLMPort` (tarifas), el Audit Log (`AuditEvent`) y el contrato de emisión de notificaciones de `d12`.
- **`frontend/`**: aviso/bloqueo en el composer del chat (`d13`), la vista 23 Mi consumo y el estado de Mis solicitudes, conforme a `design/VISTAS/06-mi-espacio.md`.

## Impact

- `resultarai/core/governance/` (modelo de Cuota, motor de evaluación, contrato de Liberación) y sus tests puros en `tests/core/`.
- `resultarai/app/` (casos de uso y endpoints de consumo, solicitud y liberación) con tests de contrato.
- Depende de: `b05-gateway-modelos` (tarifas y contadores cache hit/miss), `b04-persistencia-postgres` (consumo y liberaciones persistidos append-only), `a03-core-gobernanza` (`AuditEvent`), `d12-notificaciones` (emisión) y `d13-chat-conversacion` (composer, estado `QUOTA`).
- `frontend/` (vista 23 y aviso/bloqueo del composer).
- Referencia del blueprint: §2.4 (economía cache-first y control de consumo por modelo) — se cita como motivación, sin copiar.
