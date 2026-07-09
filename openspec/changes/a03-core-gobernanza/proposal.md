# Proposal — a03-core-gobernanza

## Why

La regla dura 4 del proyecto exige un Policy Gate deny-by-default evaluado en cada paso, con toda decisión registrada en un Audit Log append-only. Sin el contrato de dominio que decide **si una acción está permitida, bloqueada o requiere aprobación humana** y sin el contrato del evento que lo prueba, ningún runtime posterior (`b06-runtime-grafos`) puede autorizar acciones ni dejar rastro auditable. Este change cierra la Etapa A entregando ese núcleo de gobernanza puro, más los Ports que desacoplan `core/` de todo adapter.

## What Changes

- Se añade el **Policy Gate** como función pura en `core/` (bounded context `governance`): recibe un `ActionRequest`, evalúa los Policy Manifests activos con semántica **deny-by-default** y devuelve un `PolicyDecision` con efecto `allow | deny | escalate_hitl`, la Policy aplicada y una razón legible. Sin I/O, sin estado oculto, evaluable en cada paso del runtime.
- Se añaden los **niveles de riesgo** `low | medium | high | critical` y su mapeo a HITL (`docs/06`): `high` escala a aprobación humana; `critical` (escrituras al ERP) exige el contrato reforzado —comentario obligatorio del aprobador y, para acciones irreversibles, segunda aprobación 4-ojos— expresado solo como contrato de dominio (los mecanismos de UI llegan en `d17-hitl-aprobaciones`).
- Se añade el **contrato `AuditEvent`**: quién, qué, cuándo, contexto, decisión, Policy aplicada y razón, con semántica **append-only** (ni UPDATE ni DELETE; corrección = evento nuevo que referencia al anterior). Toda decisión del Policy Gate —incluidas las `allow`— emite un `AuditEvent`.
- Se añaden los seis **Ports** (`typing.Protocol` en `core/ports/`): `LLMPort`, `ToolPort`, `TracePort`, `StatePort`, `PolicyPort` y `RetrievalPort`. `RetrievalPort` es un **placeholder RAG por diseño** (`docs/07`, decisión 5): contrato mínimo + Adapter nulo que devuelve vacío; puerta abierta declarada, RAG NO se implementa.

## Capabilities

### New Capabilities

- `policy-gate`: evaluación pura deny-by-default de `ActionRequest` → `PolicyDecision`; efectos `allow | deny | escalate_hitl`; niveles de riesgo y mapeo a HITL; razones legibles; tabla de decisión determinista evaluable en cada paso.
- `audit-log`: contrato `AuditEvent` (quién/qué/cuándo/contexto/decisión/razón), invariante append-only e inmutable, y cobertura (qué decisiones emiten evento — toda decisión del Policy Gate).
- `core-ports`: los seis Ports (`Protocol`) que `core/` define para que los adapters implementen; `RetrievalPort` como placeholder RAG con Adapter nulo y decisión explícita de no implementar.

### Modified Capabilities

*(ninguna — no existen specs previas en `openspec/specs/`)*

## No-objetivos

- **Sin persistencia**: no se crea tabla ni store del Audit Log (llega en `b04-persistencia-postgres`); aquí solo el contrato del evento y su invariante.
- **Sin UI de HITL**: no hay tarjeta de aprobación, cola, expiración ni segunda aprobación operativa (llegan en `d17-hitl-aprobaciones`); aquí solo el contrato de dominio de riesgo→HITL.
- **Sin RAG**: `RetrievalPort` queda como puerta abierta con Adapter nulo; no se implementa recuperación real (Etapa P).
- **Sin adapters reales**: `LLMPort`, `ToolPort`, `TracePort`, `StatePort`, `PolicyPort` se implementan contra tecnologías concretas en la Etapa B; aquí solo los `Protocol`.
- **Sin schemas de manifiestos**: los seis Manifest schemas los define `a02-core-manifiestos`; este change los consume, no los redefine.

## Bounded context afectado

`governance` en `core/` (Policy Gate, autorización runtime, HITL, Audit Log — `docs/02`, capas 1 y 11 del blueprint). Puro: solo stdlib + Pydantic, sin I/O ni frameworks. Además `core/ports/` (transversal): las interfaces que el núcleo define para todos los bounded contexts.

## Impact

- Nuevo código de dominio en `resultarai/core/`: `core/policy/` (Policy Gate, niveles de riesgo), `core/audit/` (`AuditEvent`), `core/ports/` (los seis `Protocol`), y un Adapter nulo de `RetrievalPort`.
- Tests de contrato y de tabla de decisión en `tests/core/` que corren **sin red ni frameworks** (regla de dependencia verificada por import-linter en `a01`).
- Consume los Policy Manifest schemas de `a02-core-manifiestos`; habilita `b06-runtime-grafos` (Policy Gate evaluado por paso) y `b04-persistencia-postgres` (persistencia del Audit Log).
- Referencia del blueprint: §2.4.4 Priorización de Implementación, prioridad **P0** (Policy Engine, Runtime Authorization, Evidence Store) — este change materializa el contrato de dominio de esa prioridad sin construir aún su persistencia ni sus adapters.
