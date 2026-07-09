# Design — e25-evals-gates

## Context

La plataforma nace con la instrumentación de calidad **preparada pero no cerrada** (principio 16 del blueprint, `docs/06-seguridad-gobernanza.md`): todo Agent/Skill/Tool tiene su `EvalTemplateManifest` en `status: placeholder`, y los gates de publicación de `d20-gobernanza-plataforma` y `d21-builders` nacen pluggables — mientras `e25` no esté archivado, "score ausente" es advertencia visible, no bloqueo. La instrumentación Langfuse (trazas, costo, feedback ligado a traza y versión de prompt) ya quedó completa en `b07-observabilidad`. Lo único diferido era el runner de evals/golden sets. Este change cierra esa brecha.

**Restricción operativa singular:** este change lo ejecuta el **product owner al final**, cuando todo lo demás funciona (dependencias `d20`, `d21`, `b05`, `b07`, `e24` archivadas/operativas). El diseño debe ser autocontenido: ejecutable sin contexto de la conversación que lo generó.

## Goals / Non-Goals

**Goals:**

- Datasets de evals YAML versionados en `evals/`, solo datos sintéticos, con casos `safety` de hard-fail individual.
- Runner que evalúa una versión de prompt/Agent vía el gateway de modelos (`b05`), trazado en Langfuse (`b07`, API de scores), con score por versión + detalle por caso, ejecutable en local y en CI.
- Gate REAL de publicación (≥80% + cero safety en rojo, verificado por sistema, fail-closed) que reemplaza el modo placeholder de `d20`/`d21`, más gate de CI.
- Circuito feedback 👎 → caso de regresión con revisión humana.
- UI de la vista `43-admin-evals`.

**Non-Goals:**

- Evals con datos reales de clientes (Etapa P).
- Red teaming automatizado.
- Evaluador LLM-as-judge complejo y su calibración: el panel de calibración de la vista 43 queda documentado como opcional y diferido (ver Decisión 3).
- Reescribir la instrumentación de Langfuse (ya completa en `b07`; aquí se consume).

## Decisions

1. **Datasets como YAML en `evals/`, referenciados por el `EvalTemplateManifest`.** Cada dataset materializa un manifiesto que pasa de `placeholder` a real, coherente con "Evaluation-as-Code" (blueprint capa 12) y con el resto de contratos declarativos del producto. Alternativa descartada: casos en base de datos — se pierde el versionado en Git, el code review y la arqueología que sí da `evals/` (mismo principio que el espejo Git de prompts).

2. **El runner es un servicio de aplicación en `resultarai/app/`, no lógica de `core/`.** Orquesta el gateway de modelos y el adapter de Langfuse detrás de sus ports existentes; **no** introduce ports nuevos en `core/` (regla dura 1 intacta). Toda llamada a modelo pasa por el gateway (regla dura 2). Alternativa descartada: un binario aislado que hable con proveedores directo — violaría la regla del gateway y duplicaría la contabilidad de costos.

3. **Criterios de aceptación deterministas primero; judge LLM opcional y diferido.** V1 evalúa con comparación exacta/normalizada, contención de subcadena, coincidencia de patrón y aserciones estructurales — reproducibles, baratos y auditables. El panel "Calibración del juez LLM" de la vista 43 (`design/VISTAS/08-admin-gobernanza.md` §8.6) se documenta como capacidad opcional futura; no se implementa en V1. Motivo: un judge no calibrado introduce falsos verdes/rojos en un gate que debe ser imposible de saltar. Alternativa descartada: judge LLM desde V1 — riesgo de gate no confiable y costo por corrida no acotado.

4. **El gate se evalúa contra el hash de contenido de la versión de prompt (fail-closed).** No hay corrida válida para el hash vigente ⇒ Publicar bloqueado; editar el borrador invalida la corrida previa; runner caído ⇒ bloqueado. El sistema verifica el gate por sí mismo (no hay checkbox de override). Alternativa descartada: gate por confirmación manual del Admin — contradice "imposible saltárselo".

5. **El gate real reemplaza el placeholder sin re-evaluación retroactiva.** Al enchufar `e25`, los gates de `d20`/`d21` dejan de advertir y empiezan a bloquear; las versiones publicadas en modo placeholder quedan válidas históricamente (no se invalidan ni re-corren). Alternativa descartada: forzar re-eval de todo lo ya publicado — rompería agentes en producción y contradice la inmutabilidad de las versiones publicadas.

6. **El gate de CI reutiliza el mismo runner** sobre los datasets de los Agentes/Skills activos: un único camino de evaluación para publicación manual y para CI, evitando divergencia entre "lo que corre el Admin" y "lo que corre el pipeline".

7. **Feedback → regresión con revisión humana obligatoria.** La conversión de un 👎 a caso nace como candidato con `input`/`obtenido` prellenados y `esperado` a completar; un candidato incompleto no corre en CI. El texto de feedback se trata como dato no confiable (puede contener datos de cliente) y recuerda la política de solo-datos-sintéticos al convertir.

## Risks / Trade-offs

- **[Criterios deterministas demasiado rígidos generan falsos rojos]** → Mitigación: criterios por caso (normalización, subcadena, patrón, estructura) en vez de igualdad estricta única; el judge opcional queda documentado para cuando la variabilidad lo exija.
- **[El gate real rompe flujos que dependían del modo placeholder]** → Mitigación: transición explícita en la spec (`publication-gates`), publicaciones históricas preservadas, y prerrequisito de que `d20`/`d21` estén archivados antes de ejecutar.
- **[Costo de tokens de las corridas]** → Mitigación: el costo por corrida es visible (USD, vista 43) y se confirma antes de "Correr suite"; datasets acotados; la economía es transparente (principio P2).
- **[Datos reales colándose en un dataset]** → Mitigación: revisión humana que rechaza datos reales; el escenario de rechazo es parte de la spec `evals`.

## Migration Plan

1. **Prerrequisitos** (los verifica el product owner, ver `tasks.md`): `d20` y `d21` archivados; `b07` operativo (feedback ligado a traza y versión de prompt); API key de un proveedor; instancia levantada (`e24`).
2. Crear `evals/` con los datasets sintéticos de los Agentes/Skills/Workflows de fábrica (≥3 casos por Skill; casos `safety` marcados).
3. Desplegar el runner y el servicio de gate; enchufar el gate real en los puntos donde `d20`/`d21` mostraban el placeholder.
4. Activar el job de evals en CI (bloqueante < 80% o safety en rojo).
5. Conectar la bandeja feedback → caso en la vista 43.
6. **Rollback:** el gate es pluggable — si algo falla, se vuelve al modo placeholder (advertencia, no bloqueo) sin tocar versiones ya publicadas; ninguna publicación histórica se invalida.

## Open Questions

*(ninguna bloqueante — el judge LLM/calibración queda decidido como diferido opcional en la Decisión 3; su activación futura sería un change propio.)*
