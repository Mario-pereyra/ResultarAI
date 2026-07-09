# Design — a03-core-gobernanza

## Context

Tras `a01-fundacion-repo` (esqueleto y fronteras) y `a02-core-manifiestos` (schemas de los 6 manifiestos, incluido el `PolicyManifest`), la Etapa A cierra con el núcleo de gobernanza: el contrato que decide si una acción se permite, bloquea o escala, y el evento que lo prueba. Es el bounded context `governance` de `docs/02` (capas 1 y 11 del blueprint) y la materialización de la prioridad **P0** del blueprint §2.4.4 (Policy Engine, Runtime Authorization, Evidence Store). Todo vive en `core/`: puro, solo stdlib + Pydantic, sin I/O ni frameworks, verificado por import-linter. La persistencia (`b04`), el runtime que lo invoca por paso (`b06`) y la UI de HITL (`d17`) son changes posteriores; aquí solo el contrato de dominio.

## Goals / Non-Goals

**Goals:**

- Policy Gate como **función pura** `ActionRequest → PolicyDecision`, deny-by-default, con efectos `allow | deny | escalate_hitl`, razón legible y Policy aplicada, determinista y evaluable en cada paso.
- Niveles de riesgo `low | medium | high | critical` y su mapeo a HITL como contrato de dominio (incluido el contrato reforzado de crítico: comentario obligatorio; irreversible: segunda aprobación).
- `AuditEvent` inmutable con invariante append-only; toda decisión del gate produce exactamente uno.
- Los seis Ports como `typing.Protocol`, con `RetrievalPort` placeholder + Adapter nulo (puerta abierta a RAG, sin implementarlo).
- Tests de tabla de decisión y de contrato que corren sin red ni frameworks.

**Non-Goals:**

- Persistencia del Audit Log (`b04`), adapters reales de los ports (`b05`/`b06`/`b07`), UI de HITL (`d17`), RAG real (Etapa P).

## Decisions

1. **Policy Gate como función pura, no como servicio.** Recibe `ActionRequest` + el conjunto de Policy Manifests activos (inyectado, no leído por I/O) y devuelve `PolicyDecision`. Alternativa descartada: un servicio con acceso al registry por dentro — rompería la pureza, dificultaría el test de tabla de decisión y acoplaría `core/` a la carga de manifiestos. El `PolicyPort` deja la puerta abierta a reemplazar la implementación por OPA/Cedar sin tocar llamadores.

2. **Deny-by-default como regla estructural, no como último `else`.** La evaluación arranca en `deny` y solo un match `allow` o `escalate_hitl` explícito la cambia; la ausencia de match permanece `deny` con Policy aplicada `deny_by_default`. Esto hace el sesgo seguro comprobable por tabla.

3. **Riesgo modelado como enum de dominio con mapeo declarado en la decisión.** `low/medium/high/critical` viven en `core/policy`; el mapeo a HITL (high→escalate, critical→escalate reforzado) es parte del contrato del gate, no de la UI. El `PolicyDecision` de `escalate_hitl` porta flags `requires_approver_comment` y `requires_second_approval` (para irreversibles). Alternativa descartada: dejar el mapeo a `d17` — perdería la garantía de dominio y volvería la política dependiente de la capa de presentación.

4. **`AuditEvent` como modelo Pydantic congelado (frozen), no como fila de tabla.** La inmutabilidad se garantiza en el tipo; el append-only se documenta como invariante del futuro store (`b04`). La corrección es un evento nuevo con `corrects` = id del anterior (event sourcing acotado de `docs/02`). Alternativa descartada: definir ya el esquema SQL — viola el no-objetivo de persistencia y adelanta decisiones de `b04`.

5. **La construcción del `AuditEvent` es un mapeo puro derivado de `(ActionRequest, PolicyDecision)`.** El gate no hace I/O; produce el valor del evento y la persistencia queda para un adapter (`StatePort`/store de `b04`). Así toda decisión —incluida `allow`— deja rastro sin romper la pureza.

6. **Seis Ports como `typing.Protocol` (structural typing), sin ABC.** Los adapters conforman por estructura, sin herencia; encaja con mypy estricto y con la regla de que `core/` no importa adapters. `RetrievalPort` se entrega con un Adapter nulo (devuelve vacío, sin I/O) — la única implementación de port incluida en este change, justificada por ser la marca explícita de "RAG no implementado".

7. **`RetrievalPort` es la puerta abierta a RAG, decidida explícitamente.** Contrato mínimo + Adapter nulo + constancia en spec y tasks de que no hay recuperación real. Alternativa descartada: omitir el port hasta la Etapa P — dejaría el hueco sin contrato y obligaría a refactorizar `core/` cuando llegue RAG.

## Risks / Trade-offs

- [El contrato de HITL de dominio (flags de crítico/irreversible) podría divergir de la UI de `d17`] → Mitigación: los flags son el contrato normativo; `d17` los consume, no los redefine; la review final (tarea opus) verifica coherencia con `docs/06`.
- [Modelar `AuditEvent` sin persistencia puede omitir campos que `b04` necesitará] → Mitigación: se reservan opcionales `result_summary`, `cost`, `trace_id` alineados con la lista de `docs/06`; `b04` los promueve sin romper el contrato.
- [Sobre-especificar los ports antes de tener adapters] → Mitigación: contrato mínimo por port (solo la firma imprescindible); cada change de la Etapa B endurece el suyo al implementarlo.
- [`RetrievalPort` placeholder invita a implementar RAG antes de tiempo] → Mitigación: Adapter nulo + escenario de spec que fija "no hay recuperación real" + no-objetivo explícito.

## Migration Plan

No aplica migración de datos (no hay persistencia previa ni en este change). Despliegue: es código de dominio nuevo en `core/`; se integra vía los ports cuando la Etapa B aporte adapters. Rollback: revertir el change no afecta datos (no los hay); solo retira contratos aún no consumidos por runtime.

## Open Questions

*(ninguna — el mapeo riesgo→HITL, el contrato de `AuditEvent` y la lista de ports quedan fijados por `docs/06` y `docs/07`; las decisiones de persistencia y UI pertenecen a `b04` y `d17`)*
