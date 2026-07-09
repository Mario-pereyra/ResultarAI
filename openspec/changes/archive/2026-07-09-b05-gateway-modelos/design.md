# Design — b05-gateway-modelos

## Context

`a03-core-gobernanza` define `LLMPort` como `Protocol` en `core/ports/`, junto con `ToolPort`, `TracePort`, `PolicyPort`, `StatePort` y `RetrievalPort`. Este change implementa la única implementación de `LLMPort`: `resultarai/adapters/llm_litellm/`. `core/` no puede importar `litellm` (regla de dependencia, `docs/02-arquitectura.md`), así que todo lo específico de LiteLLM —cliente, cascada de fallback, parseo de `usage`, detección de marcador— vive en el adapter; `core/` solo conoce el contrato del port (tipos de entrada/salida, errores) y los campos de configuración relevantes en el Agent Manifest.

`b04-persistencia-postgres` (sesiones, stickiness) y `b06-runtime-grafos` (Skill Router, graph templates) son consumidores futuros de este port; ambos están especificados por interfaz aunque no archivados todavía, conforme a la regla de ejecución del roadmap ("un change se implementa solo con sus dependencias archivadas o su interfaz ya especificada").

## Goals / Non-Goals

**Goals:**

- Contrato de `LLMPort` (entrada/salida) suficientemente completo para que `b04`, `b06` y `d13` lo consuman sin retrabajo: texto de respuesta, perfil usado, metadato de modelo alterno, contadores de cache hit/miss, costo, evento de escalación.
- Cascada de fallback y perfiles de modelo como datos de configuración, resueltos en runtime por el adapter.
- Detección del marcador de escalación con exclusión estructural de contenido de adjuntos, sin depender de heurísticas de contenido (regex sobre palabras) para la exclusión — depende de la delimitación estructural `<adjunto id="...">...</adjunto>`.
- Errores de dominio tipados (`core/ports/` o módulo de errores del port) para que `app/` pueda distinguir "cascada agotada" de otros fallos sin inspeccionar strings.

**Non-Goals:**

- Definir el schema completo del Agent Manifest (`a02`); este change solo agrega los campos que necesita (cascada, escalación habilitada) como incremento sobre ese contrato.
- Implementar el motor de cuotas que consume los contadores hit/miss (`d16`).
- Implementar la UI de escalación o la etiqueta visual de modelo alterno (`d13`).
- Optimizar el layout de prompt para maximizar cache hit rate (Etapa P); aquí solo se leen y exponen los contadores que LiteLLM/el proveedor ya reportan.

## Decisions

1. **La cascada de fallback es una lista ordenada de `model_profile_id`, resuelta a configuración en el momento de la invocación.** Alternativa descartada: cascada resuelta una sola vez al cargar el Agent Manifest y cacheada en memoria del adapter — se descarta porque impediría rotar credenciales o deshabilitar un proveedor sin reiniciar el proceso; la resolución por invocación es más simple de testear con proveedor simulado y el costo de resolución es despreciable frente a la latencia de red del LLM.

2. **Los perfiles de modelo viven en configuración de instancia versionada, no en `manifests/agents/*.yaml` directamente.** El Agent Manifest referencia perfiles por id (`fallback_cascade: [profile_a, profile_b]`); los perfiles mismos (proveedor, modelo, parámetros, tarifas) viven en un archivo de configuración propio del gateway (p. ej. `manifests/model_profiles.yaml` o equivalente resuelto por `a02`). Razón: los perfiles son compartidos por múltiples agentes y cambian con más frecuencia (nueva tarifa, nuevo proveedor) que la relación agente→cascada; separarlos evita duplicar tarifas en cada Agent Manifest. Alternativa descartada: embeber los perfiles completos dentro de cada Agent Manifest — duplica tarifas y complica auditar un cambio de precio de proveedor.

3. **La detección del marcador de escalación corre sobre el texto ya despojado de bloques `<adjunto>...</adjunto>`, no sobre un regex negativo aplicado al texto completo.** Se calcula un "texto elegible para escaneo" removiendo cada bloque delimitado por `<adjunto id="...">` / `</adjunto>` (usando el `id` aleatorio de cada adjunto para emparejar apertura/cierre, conforme a `design/ANEXO-ATTACHMENTS.md` §4.3) antes de buscar `<<<NEEDS_PRO>>>`. Alternativa descartada: un clasificador o heurística de "esto parece venir de un documento" — más frágil, no determinístico, y contradice el principio de defensa estructural que ya usa el mismo mecanismo de delimitación para prompt injection.

4. **Errores tipados como jerarquía de excepciones en el módulo de errores del port (`core/ports/llm_errors.py` o similar, definido por `a03`), no como parte del texto de respuesta.** El adapter traduce cualquier excepción de LiteLLM/proveedor a uno de estos tipos antes de propagarla. Alternativa descartada: devolver un objeto de resultado con campo `error: str | None` — se descarta porque Python/mypy estricto expresa mejor el caso de error con excepciones tipadas y evita que un caso de uso olvide chequear el campo.

5. **El contrato de salida es un objeto de datos (Pydantic o dataclass, según defina `a03`) con campos explícitos** — texto, perfil usado, `is_alternate_model`, motivo de fallback, contadores hit/miss, costo, evento de escalación — en vez de devolver el `usage` crudo de LiteLLM. Razón: aísla a los consumidores (`b04`, `b06`, `d13`, `d16`) de la forma específica de la respuesta de LiteLLM, que puede cambiar entre versiones.

6. **Contract tests contra un proveedor simulado (fake/stub), nunca contra un proveedor real en CI.** Sigue la misma lógica de `a01` (tests de humo sin red): la cascada, el fallback y el marcador de escalación son comportamiento del adapter, testeable inyectando un doble que simula éxito/fallo/latencia por perfil.

## Risks / Trade-offs

- [Un proveedor cambia el formato de su `usage` de cache hit/miss] → Mitigación: el adapter normaliza a los campos del contrato de salida en un único punto de traducción; un cambio de proveedor no debe propagarse a los consumidores del port.
- [La exclusión de `<adjunto>` por delimitador estructural falla si el texto de entrada llega mal formado (delimitador sin cerrar)] → Mitigación: el adapter trata un delimitador sin cierre como "todo lo que sigue pertenece al adjunto" (fail-closed: se excluye de más texto, nunca de menos), evitando que un adjunto malformado abra una ventana para disparar la escalación.
- [Definir perfiles en un archivo de configuración separado del Agent Manifest introduce una referencia cruzada adicional a validar] → Mitigación: la validación cruzada (perfiles referenciados existen y están activos) sigue el mismo patrón que ya usan Skill Manifest↔Tool Manifest (`docs/04-manifiestos.md`); se valida en CI y al arrancar (fail-fast), sin mecanismo nuevo.
- [Cascada larga añade latencia percibida en el peor caso] → Mitigación: fuera de alcance de este change (es una decisión de producto/operación sobre cuántos perfiles poner en cascada); el contrato solo garantiza que el error final es claro, no un límite de tiempo agregado.

## Open Questions

*(ninguna — las decisiones quedan tomadas arriba; el schema Pydantic exacto de perfiles y del contrato de salida lo fija la tarea de implementación de `core/ports` en `a03`, este change solo especifica el comportamiento observable)*
