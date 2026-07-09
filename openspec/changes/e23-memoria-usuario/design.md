# Design — e23-memoria-usuario

## Context

La plataforma ya tiene chat completo (`d13`), persistencia append-only con ramas (`b04`), gateway con marcador de escalación y exclusión anti-injection (`b05`), runtime con ciclo de vida de sesión (`b06`), auditoría (`a03`/`b04`) y el shell de "Mi espacio" con sus tabs (`d18`). Falta la única pieza de personalización de fábrica: la Memoria de usuario. El contrato de producto está fijado por `design/VISTAS/06-mi-espacio.md` (vista 24) y `design/FUNCIONALIDADES.md` §4/§10: el agente solo propone, el usuario controla todo, límite ~1.000 tokens, snapshot por sesión que no rompe el cache del prefijo estático.

## Goals / Non-Goals

**Goals:**

- Mecanismo propuesta→confirmación inline en el chat, con cero escritura autónoma del agente.
- Vista Mi memoria completa (editor, contador, confirmación, borrado, historial, concurrencia optimista) según la vista 24.
- Validador fail-closed de credenciales/PII sin excepción de "datos de prueba".
- Snapshot post-prefijo inmutable por sesión, cache-safe y append-only-safe.
- Indicador de memoria usada + auditoría de alta/edición/borrado/uso.

**Non-Goals:**

- Memoria de proyecto/cliente compartida (Etapa P), memoria automática/implícita, RAG, exportación, flag por Agent Manifest, cambios en `core/` o en el contrato de `LLMPort`.

## Decisions

1. **La memoria vive como versiones append-only en una tabla propia (`user_memory_versions`), no como fila mutable.** Cada guardado inserta una versión con `user_id`, `version` (monótona por usuario), `text`, `origin` (`user` | `agent_proposal_accepted`), `created_at`. "Borrar todo" = versión con texto vacío. Alternativa descartada: una fila `user_memory` con UPDATE — rompería el historial de cambios exigido por la vista 24 y la coherencia append-only del resto del sistema (`b04`); el historial saldría de una tabla de log paralela que puede divergir del estado real.
2. **El snapshot es una referencia inmutable `session.memory_version_id`, no una copia del texto.** Al crear la sesión se resuelve la versión vigente y se congela la FK; como las versiones son inmutables, referenciar equivale a copiar pero sin duplicar texto y con trazabilidad exacta ("esta sesión usó la versión 8"). El texto se materializa al construir el contexto de cada turno, siempre desde esa versión. Alternativa descartada: copiar el texto a la sesión — pierde el vínculo auditable con la versión; releer "la vigente" en cada turno — violaría el contrato "no cambia a mitad de sesión" y rompería el prefijo repetible entre turnos.
3. **Posición del snapshot: inmediatamente después del system prompt estático, antes del historial de turnos.** El prefijo cacheable queda en dos segmentos estables: el estático puro (idéntico para todos, máximo hit-rate entre usuarios) y el bloque de memoria (idéntico para todos los turnos y ramas de la sesión, cacheable dentro de la sesión). Nada del prefijo estático varía. Alternativa descartada: memoria dentro del system prompt — variaría el prefijo estático por usuario y destruiría el cache compartido (anti cache-first); memoria al final del contexto como los adjuntos — la degradaría a contenido de turno y complicaría el contrato "aplica a toda la sesión desde el inicio".
4. **Detección de la propuesta en `app/`, con delimitador estructural en la salida del modelo (`<<<MEMORY_PROPOSAL>>>…<<</MEMORY_PROPOSAL>>>` instruido por prompt), reutilizando el patrón del marcador de escalación de `b05` sin tocar el gateway.** El caso de uso post-procesa el texto ya resuelto por `LLMPort`: extrae la propuesta, la excluye del render del mensaje y la entrega a la UI como dato estructurado del turno junto a un `proposal_id` efímero. La exclusión anti-injection es la misma de `b05`: texto dentro de `<adjunto>` o `<memoria_usuario>` jamás se interpreta como propuesta. Alternativa descartada: extender el contrato de salida de `LLMPort`/gateway — obligaría a modificar `b05` (spec ya cerrada) para una necesidad puramente de aplicación; tool de "guardar memoria" — violaría la regla dura 3 elevada a mecanismo (las tools llegan vía skills y esto no es una skill) y daría al modelo un camino de escritura que este change existe para negar.
5. **Aceptar una propuesta pasa por el mismo caso de uso de guardado que la edición manual (validador + límite + versión + auditoría), sin atajos.** Un único punto de escritura garantiza que ninguna ruta evite el validador fail-closed. La propuesta aceptada se guarda como *texto resultante* (el propuesto aplicado sobre la versión base) con `origin = agent_proposal_accepted`. Rechazar no toca persistencia: el `proposal_id` simplemente expira con el turno renderizado, sin fila ni `AuditEvent` de alta.
6. **Validador de contenido prohibido: mismas familias de detectores que el escaneo N2/N3 de `d14` (Presidio + reconocedores propios ES/BO + patrones de credenciales), política más estricta: todo hallazgo bloquea.** Se reutiliza la infraestructura de detección para no duplicar reglas, pero la política es propia de memoria: sin checkbox "son datos de prueba", porque la memoria persiste indefinidamente y viaja en TODAS las sesiones futuras — el costo de un falso negativo es permanente, no puntual. Fail-closed explícito: si el detector no responde, el guardado se rechaza (decisión 3 del apéndice de la vista 24).
7. **Concurrencia optimista por `base_version` en el payload de guardado.** El servidor compara contra la versión vigente; divergencia → HTTP 409 con la versión nueva, la UI ofrece ver diferencia/recargar. Nunca merge automático. Alternativa descartada: last-write-wins — pisaría silenciosamente ediciones (anti-transparencia); locks pesimistas — innecesarios para un recurso de un solo dueño.
8. **El indicador de memoria usada se calcula server-side por sesión (snapshot no vacío) y viaja como dato del mensaje**, igual que la etiqueta "modelo alterno" de `d13` (decisión 8 de su design): la UI no reimplementa la lógica. Link fijo a `/espacio/memoria`.
9. **Estimación de tokens: ~4 caracteres/token, misma heurística en frontend (contador en vivo) y backend (límite duro), mostrada con `≈` honesto.** El backend es la autoridad: el límite se valida al guardar aunque el contador del cliente diga otra cosa. Alternativa descartada: tokenizer real por modelo — la memoria es multi-perfil (la sesión decide el modelo después), no hay un tokenizer canónico y la precisión extra no cambia el producto.

## Risks / Trade-offs

- [El modelo emite propuestas malformadas o a mitad de streaming] → Mitigación: la propuesta solo se extrae del texto final del turno (post-streaming); un delimitador incompleto o malformado se ignora y se marca en la traza — nunca se muestra una propuesta parcial ni se rompe el render del mensaje.
- [Prompt injection vía adjunto o memoria que fabrica una propuesta] → Mitigación: exclusión estructural (decisión 4) + el peor caso es inofensivo por diseño: una propuesta siempre exige clic humano y pasa el validador; no existe ruta de escritura sin confirmación.
- [Falsos positivos del validador frustran al usuario] → Trade-off aceptado: ante la duda se bloquea (la memoria es permanente y transversal a sesiones); el mensaje de error indica qué y dónde para que el usuario reformule, y su texto nunca se pierde.
- [Dos segmentos de prefijo reducen el hit-rate frente a un prefijo único] → Trade-off aceptado y medible con los contadores hit/miss de `b05`; la alternativa (memoria en el prefijo estático) destruye el cache compartido entre usuarios, que vale más.
- [El usuario espera que su edición aplique a la sesión abierta y no ve el cambio] → Mitigación: el aviso "se aplica desde tu próxima conversación" aparece en hint + modal + toast (una sola clave i18n, vista 24) y el indicador de memoria enlaza a la vista que lo explica.

## Migration Plan

Migración Alembic aditiva (`user_memory_versions` + columna `memory_version_id` nullable en sesiones): sesiones existentes quedan sin snapshot (comportamiento idéntico al actual). Rollback = revertir la migración; ninguna otra capability depende de estas tablas.

## Open Questions

*(ninguna — las decisiones quedan tomadas arriba; la palabra de confirmación por idioma ya está resuelta por glosario cerrado en la vista 24)*
