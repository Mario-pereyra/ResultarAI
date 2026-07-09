# Tasks — a03-core-gobernanza

## 1. Ports del núcleo (core/ports/)

- [x] 1.1 Definir `LLMPort`, `ToolPort`, `TracePort` y `StatePort` como `typing.Protocol` en `core/ports/`, con el contrato mínimo por port y docstring que nombra su Adapter futuro (`b05`/`b06`/`b07`/`b04`). Verificación: `mypy` estricto pasa y `tests/core/ports/test_protocols.py` afirma que los cuatro `Protocol` existen y aceptan una implementación fake por estructura; corre sin red. `[modelo: opus]`
- [x] 1.2 Definir `PolicyPort` como `Protocol` que abstrae la evaluación de políticas (permite reemplazar el Policy Gate por OPA/Cedar sin tocar llamadores). Verificación: `tests/core/ports/test_policy_port.py` — una implementación fake conforma sin herencia explícita; sin red. `[modelo: opus]`
- [x] 1.3 Definir `RetrievalPort` (`Protocol`, contrato mínimo de recuperación) y su Adapter nulo que devuelve secuencia vacía, con docstring que declara "RAG no implementado — puerta abierta (docs/07 decisión 5)". Verificación: `tests/core/ports/test_retrieval_null.py` — el Adapter nulo devuelve vacío para cualquier consulta y no hace I/O; sin red. `[modelo: opus]`
- [x] 1.4 Verificar la frontera de `core/ports/`: ningún port importa `adapters`, `app` ni frameworks (langgraph, litellm, langfuse, fastapi, httpx). Verificación: `uv run lint-imports` reporta KEPT los 3 contratos de a01 y `mypy` en verde. `[modelo: sonnet]`

## 2. Niveles de riesgo y contrato de acción (core/policy/)

- [x] 2.1 Definir el enum de dominio `RiskLevel` (`low | medium | high | critical`) y el `ActionRequest` (Pydantic) con `user`, `tenant`, `agent`, `skill`, `tool`, `operation_type` (`read | write`), `risk_level` y `environment`; `tenant` obligatorio en acciones de Tool del ERP. Verificación: `tests/core/policy/test_action_request.py` — construcción válida y rechazo sin `tenant` (ValidationError); sin red. `[modelo: opus]`
- [x] 2.2 Definir `PolicyDecision` (Pydantic) con `effect` (`allow | deny | escalate_hitl`), `reason`, `applied_policy` (id de `PolicyManifest` o marcador `deny_by_default`), `limits` opcionales y flags HITL `requires_approver_comment` y `requires_second_approval`. Verificación: `tests/core/policy/test_policy_decision.py` — `effect` fuera del enum rechazado y flags por defecto en `false`; sin red. `[modelo: opus]`

## 3. Policy Gate (core/policy/)

- [x] 3.1 Implementar `PolicyGate` como función pura `ActionRequest × Policy Manifests activos → PolicyDecision`, deny-by-default estructural (arranca en `deny`; solo un match explícito cambia el efecto), con razón legible y Policy aplicada. Verificación: `tests/core/policy/test_gate_pure.py` — `allow` con Policy permisiva, `deny` por ausencia con marcador `deny_by_default`, y determinismo (misma entrada → misma salida); sin red ni frameworks. `[modelo: opus]`
- [x] 3.2 Implementar en el gate el mapeo riesgo→HITL (low→`allow`; medium→`allow` con límites; high→`escalate_hitl`; critical→`escalate_hitl` con `requires_approver_comment`, e irreversible→`requires_second_approval`) y el aislamiento usuario↔tenant (cruce entre tenants → `deny`). Verificación: `tests/core/policy/test_gate_risk_hitl.py` cubre los cuatro niveles y el cruce de tenants; sin red. `[modelo: opus]`
- [x] 3.3 Escribir el test de **tabla de decisión** del gate: matriz (`operation_type` × `risk_level` × match de Policy × autorización de tenant) → efecto esperado, incluyendo dos `ActionRequest` consecutivos con decisiones independientes (Runtime Authorization per Step). Verificación: `tests/core/policy/test_decision_table.py` en verde, corre sin red ni frameworks. `[modelo: sonnet]`
- [x] 3.4 Crear los fixtures de Policy Manifests de ejemplo (`erp_read_only_policy` y uno con `escalate_hitl` por riesgo `high`) y los `ActionRequest` que alimentan la tabla de decisión; validar cada YAML contra el schema `PolicyManifest` de `a02`. Verificación: `tests/core/policy/conftest.py` expone los fixtures, los YAML validan contra el schema y `test_decision_table.py` los consume; sin red. `[modelo: haiku]`

## 4. AuditEvent (core/audit/)

- [x] 4.1 Definir `AuditEvent` (modelo Pydantic congelado/frozen) con quién (`user`, `tenant`), qué (`agent`, `skill`, `tool`, `operation_type`, parámetros resumidos/enmascarados), cuándo (`timestamp`), contexto (`environment`), decisión (efecto + `PolicyManifest` aplicado) y razón; más `corrects` opcional y los opcionales reservados `result_summary`, `cost`, `trace_id`. Verificación: `tests/core/audit/test_audit_event.py` — la mutación de un campo falla (inmutable) y los opcionales pueden omitirse; sin red. `[modelo: opus]`
- [x] 4.2 Implementar el mapeo puro `(ActionRequest, PolicyDecision) → AuditEvent` y la cobertura: toda decisión (`allow` | `deny` | `escalate_hitl`) produce exactamente un `AuditEvent`; una corrección es un evento nuevo con `corrects` al `id` del original, sin mutar ni borrar el anterior. Verificación: `tests/core/audit/test_audit_coverage.py` — un evento por decisión (incluida `allow`), enmascarado de campos sensibles y corrección que referencia al original; sin red. `[modelo: opus]`
- [x] 4.3 Crear el fixture de parámetros con campos sensibles y secretos para el test de enmascarado. Verificación: el fixture es consumido por `test_audit_coverage.py` and ningún secreto aparece en el `AuditEvent` resultante; sin red. `[modelo: haiku]`

## 5. Cierre

- [x] 5.1 Review final del change: contrato coherente con `docs/06` (niveles de riesgo, mapeo a HITL, append-only del Audit Log), términos exactos del glosario (`docs/03`), cero I/O y cero frameworks en `core/`, y `RetrievalPort` sin implementación real. Verificación: `uv run pytest tests/core`, `uv run mypy .` y `uv run lint-imports` en verde, más el checklist del reviewer en el PR. `[modelo: opus]`
