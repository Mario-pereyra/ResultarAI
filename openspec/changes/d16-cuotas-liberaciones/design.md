# Design — d16-cuotas-liberaciones

## Context

La plataforma es cache-first y su viabilidad económica depende de acotar el consumo por modelo. `b05-gateway-modelos` ya expone contadores de cache hit/miss y tarifas separadas por perfil de modelo; `b04-persistencia-postgres` ya da persistencia append-only; `a03-core-gobernanza` ya define el `AuditEvent`; `d12-notificaciones` ya emite `quota_release_requested`/`quota_release_resolved`. Falta el freno: un mecanismo que, ANTES de cada llamada al modelo, decida si el turno cabe en las Cuotas del usuario, y una vía accionable cuando no cabe. El design (`design/FLUJOS.md` Flujo E, `design/FUNCIONALIDADES.md` §4/§10/§11, `design/VISTAS/06-mi-espacio.md` vista 23, `design/VISTAS/07-admin-operacion.md` vista 33) fija el comportamiento; este change lo materializa como slice vertical (core + app + frontend).

## Goals / Non-Goals

**Goals:**

- Cuota jerárquica (global → grupo → usuario → sesión) evaluada como función pura ANTES de cada llamada al modelo, con estimación por tarifas hit/miss.
- Umbral de aviso al 80% (configurable) y bloqueo al 100% con estado `QUOTA` accionable.
- Cadena de Liberación completa (solicitud → decisión Admin → desbloqueo inmediato) auditada de punta a punta.
- Mi consumo (vista 23) con capa por rol y Mis solicitudes de Liberación.
- Consistencia bajo concurrencia: nunca gasto doble por encima del tope.

**Non-Goals:**

- FinOps avanzado / chargeback / presupuestos multi-instancia por tenant (Etapa P).
- Telemetría/analítica agregada de consumo y consola de edición de cuotas por alcance (`d19-admin-operacion`).
- Infraestructura de notificaciones (se reutiliza `d12`).

## Decisions

1. **El motor de evaluación vive en `core/governance/` como función pura.** Recibe snapshots de consumo por alcance, límites resueltos y el costo estimado del turno; devuelve autoriza/bloquea con el alcance bloqueante. Sin I/O ni reloj: la lectura de consumo y la hora de renovación entran como parámetros. Alternativa descartada: evaluar en el adapter del gateway — rompería la regla de dependencia y haría el núcleo no testeable sin red.

2. **Reserve-then-reconcile para la concurrencia.** Antes de llamar al modelo se **reserva** atómicamente el costo estimado del turno contra los cuatro alcances (decremento atómico / fila con bloqueo optimista en Postgres, `b04`); tras la respuesta se **reconcilia** con el costo real de los contadores hit/miss del `usage`. Así dos llamadas concurrentes cerca del límite nunca sobregastan: la segunda observa la reserva de la primera. Alternativa descartada: check-then-act sin reserva — condición de carrera que permite gasto doble por encima del tope.

3. **Estimación conservadora con ambas tarifas.** El costo estimado usa las tarifas hit/miss del perfil que atenderá el turno sobre los tokens de prompt conocidos más una asignación de salida; nunca una tarifa promedio única. El costo definitivo lo fija la reconciliación con el `usage`. Alternativa descartada: estimar con tarifa miss uniforme — sobreestima y bloquea antes de tiempo en sesiones muy cacheadas.

4. **La Cuota es un gate ortogonal al Policy Gate, no un `PolicyDecision`.** El Policy Gate autoriza la acción; la Cuota autoriza el gasto. Un turno pasa ambos. Un bloqueo por Cuota se representa con el estado `QUOTA`, no con un efecto del Policy Gate; así el Audit Log distingue "denegado por política" de "sin presupuesto". Alternativa descartada: modelar la Cuota como una Policy — mezclaría dos ejes de decisión y ensuciaría la tabla de decisión pura del gate.

5. **Renovación diaria a medianoche en la zona horaria de instancia.** El período diario se ancla a la medianoche local configurada, no a UTC fija; el motor recibe el "inicio de período vigente" como parámetro para no leer el reloj dentro del núcleo. Alternativa descartada: medianoche UTC — desfasa el corte respecto de la jornada real del cliente en Bolivia.

6. **Defaults como configuración de instancia.** Límites y umbral (80%) son configuración leída, no constantes de código; overrides por entidad prevalecen sobre defaults. La CRUD de esos valores (tab Cuotas de la vista 33) queda fuera de alcance; aquí se consumen como config leída y se dispara la cadena de Liberación.

7. **Notificaciones y auditoría por reutilización.** La solicitud y la resolución invocan el contrato de emisión de `d12` (`quota_release_requested`/`quota_release_resolved`) y emiten `AuditEvent` (`QUOTA_RELEASE_REQUESTED/_APPROVED/_DENIED`) al Audit Log append-only de `a03`/`b04`. Este change no crea tipos de notificación ni infraestructura de audit.

## Risks / Trade-offs

- [Estimación imprecisa del costo del turno antes de conocer la salida] → Mitigación: reserva conservadora + reconciliación con el `usage` real; el margen se corrige tras cada turno, no se arrastra error.
- [Contención en el decremento atómico bajo alta concurrencia] → Mitigación: reserva por alcance con bloqueo de corta duración; el caso patológico (muchos turnos simultáneos del mismo alcance al borde del límite) es raro y correctitud > throughput cerca del tope.
- [Discrepancia documental: `design/FUNCIONALIDADES.md` §10 dice que Funcional no ve moneda, pero la vista 23 detalla que el costo en presupuesto es visible para todos los roles en Mi consumo] → Mitigación: se adopta la vista 23 (fuente detallada y normativa, que documenta el override con justificación); Funcional nunca ve tokens, cache ni modelos. Señalado para revisión humana.
- [Ampliación puntual que expira a mitad de sesión] → Mitigación: al vencer, el límite vuelve al valor normal sin avisos adicionales (comportamiento de la vista 23); el siguiente turno reevalúa contra la Cuota base.

## Migration Plan

Change nuevo sin migración de datos previa: introduce las tablas de consumo y de Liberación (append-only) vía Alembic (`b04`). No altera contratos existentes de `b05`/`a03`/`d12` (solo los consume). Rollback: revertir la migración y el registro de casos de uso deja la plataforma sin cuotas (estado anterior), sin corromper datos de otros contextos.

## Open Questions

- ¿La ampliación `permanente` de una Liberación debe reflejarse como override editable en la futura consola de cuotas (`d19`), o permanece como registro de Liberación consultado por el motor? Se asume lo segundo en v1; a confirmar al especificar `d19`.
