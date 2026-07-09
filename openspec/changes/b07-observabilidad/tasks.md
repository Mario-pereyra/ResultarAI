# Tasks — b07-observabilidad

## 1. Cliente Langfuse y configuración

- [ ] 1.1 Agregar la dependencia `langfuse` al grupo de adapters en `pyproject.toml` (uv) y documentar `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_HOST` en `.env.example`. Verificación: `uv sync` instala sin error; `.env.example` documenta las 3 variables. `[modelo: haiku]`
- [ ] 1.2 Documentar la convención de naming (tags de traza, patrón de URL de traza y de sesión) en un README breve dentro de `adapters/tracing_langfuse/`, listo para que `d19-admin-operacion` lo referencie. Verificación: el README contiene los 2 patrones de URL de la decisión 7 de `design.md`. `[modelo: haiku]`

## 2. Contrato de traza por turno y enmascaramiento

- [ ] 2.1 Definir el contrato interno `TurnTrace` (Pydantic) que agrupa costo hit/miss, tokens, modelo/perfil, decisión de routing, lista de `PolicyDecision` del turno, `session_id`, `user_id` y flags de adjuntos, como único input al adapter, coherente con `TracePort` (`a03-core-gobernanza`). Verificación: test en `tests/contracts/test_trace_port_langfuse.py` instancia `TurnTrace` con todos los campos requeridos y falla si falta uno obligatorio. `[modelo: opus]`
- [ ] 2.2 Implementar `mask_user_identity` y su configuración como `mask` del cliente Langfuse, garantizando que ningún identificador de usuario en claro llegue al payload enviado. Verificación: test unitario que envía un `user_id` conocido y afirma que el payload capturado por un cliente Langfuse simulado nunca contiene el valor en claro. `[modelo: opus]`
- [ ] 2.3 Definir el contrato de vínculo traza↔versión de prompt: cómo el adapter recibe el objeto de prompt activo del turno y lo asocia a la generación, sin acoplarse al Registro de Prompts (llega en `d20-gobernanza-plataforma` — aquí solo el parámetro que el caso de uso deberá proveer). Verificación: test de contrato que pasa una versión de prompt simulada y confirma que queda accesible en el resultado de la traza. `[modelo: opus]`

## 3. Adapter Langfuse — traza

- [ ] 3.1 Implementar `adapters/tracing_langfuse/client.py`: instancia única del cliente Langfuse con `mask` configurado, lectura de credenciales desde entorno, fail-fast si faltan. Verificación: test que instancia el cliente sin credenciales lanza un error claro. `[modelo: sonnet]`
- [ ] 3.2 Implementar `adapters/tracing_langfuse/trace.py`: apertura/cierre de una traza por turno, mapeo de `TurnTrace` a `usage_details`/`cost_details` con buckets separados de cache hit/miss, y `session_id`/`user_id` propagados a la traza. Verificación: contract test cubre un turno con cache hit y uno con cache miss, con los buckets correctos. `[modelo: sonnet]`
- [ ] 3.3 Instrumentar el registro de la decisión de routing del Skill Router y de cada `PolicyDecision` del turno como observaciones anidadas de la traza. Verificación: contract test con un turno que activa skill y uno con `escalate_hitl` confirma que ambas decisiones aparecen en la traza simulada. `[modelo: sonnet]`
- [ ] 3.4 Instrumentar el registro de flags de adjuntos sospechosos (N2/N3 + heurística de inyección del ANEXO §4.3) como metadata de la traza, leyendo el `scan_result` que provee el caso de uso (parámetro opcional, sin acoplar a `d14-attachments` que aún no existe). Verificación: contract test con turno con adjunto flageado y turno sin adjunto. `[modelo: sonnet]`
- [ ] 3.5 Implementar la etiqueta de "modelo alterno" en la traza cuando el perfil usado difiere del perfil primario configurado (fallback de `b05-gateway-modelos`). Verificación: contract test con fallback activo confirma la etiqueta presente; sin fallback, ausente. `[modelo: sonnet]`

## 4. Adapter Langfuse — feedback

- [ ] 4.1 Implementar `adapters/tracing_langfuse/feedback.py`: `submit_feedback(trace_id, value, comment)` que crea el score `user-thumbs` (`dataType="BOOLEAN"`) ligado al `trace_id`. Verificación: contract test crea feedback positivo y negativo y verifica los campos del score simulado. `[modelo: sonnet]`
- [ ] 4.2 Implementar la marca de candidato a caso de regresión: 👎 con comentario agrega el tag `regression-candidate`; 👎 sin comentario no lo agrega. Verificación: contract test cubre ambos casos y afirma presencia/ausencia del tag. `[modelo: sonnet]`
- [ ] 4.3 Implementar la consulta de candidatos a regresión (filtro por tag `regression-candidate`) sin dependencia de ningún componente de evals. Verificación: contract test consulta candidatos sin que exista `e25-evals-gates` y no falla. `[modelo: sonnet]`
- [ ] 4.4 Verificar que `submit_feedback` nunca expone una operación de edición/borrado sobre un score existente (append-only): una corrección solo puede crear un score nuevo. Verificación: test que intenta reenviar feedback sobre el mismo `trace_id` y confirma que se crea un score adicional, no una mutación. `[modelo: sonnet]`

## 5. Tests y verificación de fronteras

- [ ] 5.1 Completar `tests/contracts/test_trace_port_langfuse.py` cubriendo todos los escenarios de `observability-tracing` (turno simple, escalación con modelo alterno, cache hit, cache miss, routing directo/skill, Policy Gate `allow`/`escalate_hitl`, adjunto flageado/limpio, patrones de URL de naming convention). Verificación: `uv run pytest tests/contracts/test_trace_port_langfuse.py` en verde, sin red real (cliente Langfuse simulado). `[modelo: sonnet]`
- [ ] 5.2 Completar `tests/contracts/test_response_feedback.py` cubriendo todos los escenarios de `response-feedback` (positivo/negativo, con/sin comentario, ligado a `trace_id` y versión de prompt, no purgable, corrección como score nuevo, consulta de candidatos). Verificación: `uv run pytest tests/contracts/test_response_feedback.py` en verde. `[modelo: sonnet]`
- [ ] 5.3 Verificar con `uv run lint-imports` que `resultarai.adapters.tracing_langfuse` no es importado por ningún otro adapter (contrato de independencia de `a01-fundacion-repo`) y que `resultarai.core` sigue sin importar `langfuse`. Verificación: los 3 contratos de import-linter reportan "KEPT". `[modelo: sonnet]`

## 6. Cierre

- [ ] 6.1 Confirmar que `docs/02-arquitectura.md` (bounded context `observability`) y `docs/06-seguridad-gobernanza.md` (mención de `trace_id` en `AuditEvent`) no contradicen lo implementado; ajustar solo si hace falta precisión, sin reescribir secciones enteras. Verificación: diff nulo o mínimo. `[modelo: haiku]`
- [ ] 6.2 Review final del change: consistencia proposal↔specs↔design↔tasks, términos del glosario usados correctamente, No-objetivos respetados (sin código de `e25`, sin dashboards propios, sin UI de chat), cero acoplamiento innecesario a `d14`/`d19`/`d20` más allá de los contratos y convenciones documentados. Verificación: checklist del reviewer en el PR. `[modelo: opus]`
