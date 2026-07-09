# Design — b07-observabilidad

## Context

`a03-core-gobernanza` define `TracePort` como `Protocol` puro en `core/ports/`, sin ninguna implementación. `b05-gateway-modelos` ya reporta tarifas hit/miss desde el adapter LiteLLM y `b06-runtime-grafos` ya emite decisiones de routing y del Policy Gate por paso. Este change cierra la Etapa B implementando el único adapter que traduce todo ese flujo a trazas y feedback reconstruibles en Langfuse, conforme a `docs/02-arquitectura.md` (bounded context `observability`, capa 13 del blueprint) y a la nota de desacople de `docs/07-roadmap.md`: toda la instrumentación se completa aquí, solo el runner de evals (`e25-evals-gates`) queda diferido para que lo ejecute el product owner al final.

El SDK de referencia es `langfuse` (Python) en su versión vigente al momento de implementar; los mecanismos usados en este diseño (`mask`, `propagate_attributes`, `usage_details`/`cost_details`, `score`/`create_score`, vínculo `prompt=` de Prompt Management) están verificados contra la documentación oficial de Langfuse al escribir este change.

## Goals / Non-Goals

**Goals:**

- Una traza por turno (no por llamada LLM aislada), con costo hit/miss, tokens, modelo/perfil, routing, decisiones del Policy Gate, sesión y usuario enmascarado.
- Feedback 👍/👎 + comentario persistido como `score` de Langfuse, ligado a `trace_id` y versión de prompt, con retención permanente y marca de candidato a regresión.
- Naming conventions estables para que `d19-admin-operacion` construya enlaces directos a Langfuse.

**Non-Goals:**

- Ejecutar o construir el runner de evals (`e25`).
- Construir dashboards propios de analítica (`d19` solo enlaza).
- Persistir la traza o el feedback en Postgres: viven en Langfuse; `AuditEvent` solo referencia el `trace_id`.

## Decisions

1. **Instrumentación a nivel de turno, no de llamada LLM.** El adapter abre una traza (`start_as_current_observation`/equivalente) al inicio del turno en `app/use_cases` y la cierra al entregar la respuesta final; todas las llamadas a modelo, activaciones de skill y evaluaciones del Policy Gate que ocurran dentro quedan como observaciones anidadas bajo el mismo `trace_id`. Alternativa descartada: una traza por llamada LLM — rompe la reconstrucción de "qué costó y qué decidió el sistema para responder a este mensaje", que es el requisito explícito del roadmap ("un turno cualquiera es reconstruible en Langfuse con su costo").

2. **Enmascaramiento vía `mask` a nivel de cliente.** El cliente Langfuse se instancia una sola vez en `adapters/tracing_langfuse/client.py` con `mask=mask_user_identity`, una función que reemplaza el identificador de usuario en claro por un valor enmascarado (hash estable o alias) antes de que cualquier dato salga por las APIs de Langfuse (`start_observation`, `update`, `set_trace_io`). El `user_id` en sí se propaga con `propagate_attributes(user_id=..., session_id=...)` al entrar al caso de uso del turno, de forma que todas las observaciones anidadas lo heredan sin que cada capa tenga que pasarlo explícitamente. Alternativa descartada: enmascarar en el caso de uso antes de llamar al adapter — duplica la lógica de enmascaramiento fuera del punto único de configuración del cliente y arriesga fugas si un caller nuevo olvida aplicarla.

3. **Costo hit/miss vía `usage_details`/`cost_details`.** El adapter traduce los contadores que ya expone `b05-gateway-modelos` (`prompt_cache_hit_tokens`/`prompt_cache_miss_tokens` y sus tarifas) a las claves de bucket de Langfuse (p. ej. `input`, `cache_read_input_tokens`, `output`) en `usage_details`, y sus costos en USD en `cost_details`, respetando la regla de Langfuse de que cada token se cuenta en exactamente una clave. El `model` se pasa con el nombre del perfil de modelo tal como lo resuelve LiteLLM, para que Langfuse pueda hacer el *pricing lookup* automático como respaldo si el gateway no trae costo explícito. Alternativa descartada: calcular el costo total en el adapter y enviarlo como un único número — pierde el desglose hit/miss que el roadmap pide explícitamente y que ya es la base de la economía cache-first del proyecto (ADR-0001).

4. **Feedback como `score` ligado a traza y prompt.** El servicio de feedback (`adapters/tracing_langfuse/feedback.py`) recibe `trace_id`, valor (👍/👎), comentario opcional, y crea un score vía `create_score`/`score()` con `name="user-thumbs"` (nombre único y consistente en toda la app, coherente con la práctica recomendada de Langfuse de nombrar el score por la señal, no por lo que se espera medir), `dataType="BOOLEAN"`, `value` (1/0) y `comment`. La versión de prompt activa se captura porque la generación del turno ya se instrumentó con el objeto `prompt` obtenido de `langfuse.get_prompt(...)` (vínculo nativo de Prompt Management); el score, al estar ligado al mismo `trace_id`, hereda esa asociación sin necesidad de guardar la versión por separado. Alternativa descartada: registrar la versión de prompt como campo propio del score — redundante, Langfuse ya resuelve "qué versión generó esta traza" a través del vínculo `prompt=` existente en la generación.

5. **Marca de candidato a regresión como tag del score.** Un 👎 con comentario agrega el tag `regression-candidate` (o metadata equivalente) al score en el mismo `create_score`; no dispara ningún proceso adicional. `e25-evals-gates`, cuando exista, consulta scores por ese tag. Alternativa descartada: escribir una tabla propia de "candidatos a regresión" en Postgres — viola el No-objetivo de este change (sin persistencia propia) y duplica una fuente de verdad que Langfuse ya ofrece consultar por filtro.

6. **Retención permanente del feedback.** El feedback vive en Langfuse igual que las trazas; no existe hoy un mecanismo de purga automatizado de trazas/scores en la plataforma (la retención de 90 días de `d14-attachments` es específica de adjuntos en Postgres/volumen de archivos, un sistema distinto). El requisito de "conservación permanente" se satisface por diseño al no construir ningún job de purga sobre Langfuse en este change; si en el futuro se configura una política de retención a nivel de proyecto Langfuse (Etapa P / operación), esa configuración deberá excluir explícitamente los scores de feedback — se deja anotado como riesgo operativo, no como código de este change.

7. **Naming conventions para enlaces desde `d19`.** Se documentan aquí (y se referencian desde `d19-admin-operacion` cuando se implemente) los patrones de URL de Langfuse basados en `trace_id` y `session_id` (p. ej. `{LANGFUSE_HOST}/project/{project_id}/traces/{trace_id}` y `.../sessions/{session_id}`), más la convención de tags usada (`regression-candidate`, flags de adjuntos). `d19` solo necesita interpolar estos identificadores, que ya se muestran en la consola por otras razones (auditoría, telemetría de consumo); no se agrega ninguna API nueva del adapter para ese enlace.

## Risks / Trade-offs

- [El SDK/API exacta de Langfuse puede cambiar entre el diseño y la implementación] → Mitigación: la tarea de implementación del adapter (tasks.md) exige releer la documentación oficial vigente al momento de codear, no confiar en los nombres de campo fijados aquí como definitivos.
- [Sin un mecanismo propio de purga a prueba de fallos, un cambio de configuración futuro en Langfuse podría purgar feedback junto con trazas viejas] → Mitigación: se documenta el riesgo explícitamente (decisión 6); `e24-despliegue-operacion`/Etapa P deben verificar la configuración de retención del proyecto Langfuse antes de operar en producción.
- [Enmascarar el `user_id` a nivel de cliente depende de que todo caller use `propagate_attributes`; un caller que setee el atributo por otra vía podría fugar identidad en claro] → Mitigación: el contract test de `TracePort` (tasks.md) incluye un caso que verifica que ningún identificador en claro llegue al payload enviado a Langfuse.
- [Sobrecargar la traza del turno con demasiada metadata (Policy Gate + flags de adjuntos + routing) puede degradar la legibilidad en la UI de Langfuse] → Mitigación: se usa la estructura de observaciones anidadas de Langfuse (una observación por decisión relevante) en vez de aplanar todo en un solo blob de metadata.

## Open Questions

*(ninguna — las decisiones quedan tomadas arriba; la implementación debe verificar los nombres exactos de campos contra la documentación de Langfuse vigente al codear, según el riesgo anotado)*
