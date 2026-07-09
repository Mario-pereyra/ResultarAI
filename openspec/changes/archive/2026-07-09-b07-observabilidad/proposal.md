# Proposal — b07-observabilidad

## Why

El roadmap (`docs/07-roadmap.md`, fila b07) exige que todo turno (mensaje del usuario → respuesta) quede trazado con costo, tokens, modelo y decisiones del Policy Gate, y que el feedback del usuario quede ligado a esa traza como materia prima para evals de regresión. Sin el adapter Langfuse detrás de `TracePort` (`a03-core-gobernanza`), ninguna decisión del sistema es reconstruible en la práctica pese a que el contrato de dominio ya exista; sin el contrato de feedback ligado a traza y versión de prompt, no hay insumo para `e25-evals-gates` cuando se ejecute. Decisión del product owner (nota de desacople, `docs/07-roadmap.md`): toda la instrumentación Langfuse (trazas completas + feedback) se cierra AHORA; lo único diferido es el runner de evals/golden sets.

## What Changes

- Se implementa `adapters/tracing_langfuse/` (bounded context `observability`) como la única implementación de `TracePort` (definido en `a03-core-gobernanza`): traza el **turno completo** (mensaje de usuario → respuesta final), no llamadas LLM aisladas.
- Cada traza registra: costo con tarifas hit/miss separadas del gateway (`b05-gateway-modelos`, vía `usage_details`/`cost_details` con buckets de cache hit/miss), tokens totales, el modelo/perfil de modelo usado (incluida la etiqueta "modelo alterno" cuando hubo fallback), la decisión de routing del Skill Router, cada `PolicyDecision` del turno (`allow`/`deny`/`escalate_hitl` + razón + Policy aplicada), el `session_id` y el `user_id` — este último **enmascarado** mediante la función `mask` configurada a nivel del cliente Langfuse: la telemetría nunca expone identidad en claro.
- Se añade el contrato de **feedback por respuesta**: 👍/👎 + comentario opcional, capturado como `score` de Langfuse ligado al `trace_id` del turno y a la versión de prompt activa (vínculo de Langfuse Prompt Management). El feedback se conserva **siempre**, exento de cualquier purga automática de la plataforma (a diferencia de los adjuntos, que sí purgan a 90 días — `d14-attachments`). Un 👎 con comentario queda marcado (tag/metadata del score) como **candidato a caso de regresión**: aquí solo se almacena y se expone esa marca; `e25-evals-gates` es quien la consumirá para construir el dataset.
- Se registran en la traza los flags de adjuntos sospechosos (heurística de inyección del ANEXO §4.3 y el resultado N2/N3 del escaneo) como metadata del turno, referenciando —sin duplicar— el `scan_result` que vive en la tabla `attachments` (`d14-attachments`).
- Se fijan las convenciones de nombres (naming conventions) de traces/sessions/tags para que la consola admin (`d19-admin-operacion`) enlace directamente a la vista nativa de Langfuse de un turno/sesión/usuario, sin reimplementar ningún dashboard.

## Capabilities

### New Capabilities

- `observability-tracing`: traza por turno vía `TracePort` → Langfuse, con costo (tarifas hit/miss), tokens, modelo/perfil usado, decisión de routing, decisiones del Policy Gate, sesión y usuario enmascarado, flags de adjuntos sospechosos y naming conventions enlazables desde `d19`.
- `response-feedback`: captura de 👍/👎 + comentario opcional como score de Langfuse ligado a la traza y a la versión de prompt activa; retención permanente (exenta de purgas); marca de candidato a caso de regresión.

### Modified Capabilities

*(ninguna — no existen specs previas para estas capabilities en `openspec/specs/`)*

## No-objetivos

- **Sin runner de evals, golden sets ni scores de evaluación** — es `e25-evals-gates`, ejecutado por el product owner al final; aquí un 👎 con comentario solo queda marcado como candidato, nunca procesado.
- **Sin dashboards propios de telemetría** — `d19-admin-operacion` enlaza a las vistas nativas de Langfuse; este change no reimplementa ninguna UI de analítica ni de FinOps.
- **Sin FinOps avanzado** (presupuestos, forecasting, alertas de gasto) — queda para la Etapa P.
- **Sin componentes de UI del chat** (botones 👍/👎, cuadro de comentario): la interfaz vive en `d13-chat-conversacion`; aquí solo el contrato y el servicio de captura/persistencia del feedback que esa UI invocará.
- **Sin persistencia propia en Postgres**: la traza y el score viven en Langfuse; el `AuditEvent` (`a03-core-gobernanza`, persistido en `b04-persistencia-postgres`) sigue siendo la fuente de verdad de las decisiones de gobernanza — este change solo aporta el `trace_id` de Langfuse que `AuditEvent` ya referencia según `docs/06-seguridad-gobernanza.md`.
- **Sin cambios al Policy Gate ni al modelo de riesgo** (`a03-core-gobernanza`): este change consume sus decisiones, no las redefine.

## Bounded context afectado

`observability` en `adapters/tracing_langfuse/` (`docs/02-arquitectura.md`, capa 13 del blueprint — Observability & Evidence). Implementa `TracePort` definido en `a03-core-gobernanza`; consume perfiles/costos de `b05-gateway-modelos` y decisiones de routing/Policy Gate de `b06-runtime-grafos`. No toca `core/`: solo lo consume vía el port (regla de dependencia intacta).

## Impact

- Nuevo código en `resultarai/adapters/tracing_langfuse/`: cliente Langfuse configurado con `mask`, instrumentación de traza por turno, servicio de captura de feedback (`create_score`/`score`).
- `tests/contracts/`: contract test de `TracePort` para el adapter Langfuse, con un proveedor Langfuse simulado (sin red).
- Consume: `TracePort` (`a03`), tarifas/perfil de modelo (`b05`), decisión de routing y Policy Gate por paso (`b06`).
- Habilita: `d19-admin-operacion` (enlaces a Langfuse), `e25-evals-gates` (consume la marca de candidato a regresión y el histórico de feedback).
- Referencia del blueprint: capa 13 (Observability & Evidence) — este change la materializa por completo salvo el runner de evals.
