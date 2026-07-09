---
name: asignar-modelo
description: Asigna el escalón de modelo (haiku/sonnet/opus) a cada tarea delegada según su dificultad. Usar antes de lanzar un subagente con Agent y antes de escribir llamadas agent() en un Workflow.
---

# Escalera de modelos

Cada tarea delegada se coloca en un escalón de la escalera y la llamada declara ese `model` explícito. Fable 5 pertenece al bucle principal: un subagente o workflow lo lleva solo cuando el usuario lo nombra.

## Escalones

| Escalón | `model` | La tarea… |
|---|---|---|
| 1 | `haiku` | tiene regla clara y resultado verificable: buscar/localizar, extraer, clasificar, formatear, resumen básico, fan-out mecánico |
| 2 | `sonnet` | exige escribir o juzgar código/texto dentro de un patrón conocido: features acotadas, tests, refactors, debugging de rutina, review, verificación a escala. Escalón por defecto ante la duda |
| 3 | `opus` | tiene espacio de soluciones abierto o un error pasaría inadvertido: arquitectura, causa raíz difícil, síntesis final, jueces adversariales |
| 4 | `fable` | la nombra el usuario explícitamente |

Subir de escalón sin motivo cuesta tokens sin ganancia; la señal legítima para subir es un fallo observado en esa misma etapa. Caso real: una etapa de Workflow que agotó los reintentos de StructuredOutput con `sonnet` se resolvió relanzándola con `opus`.

## Al delegar

1. Coloca la tarea en su escalón con la tabla.
2. Declara el modelo: en Agent, el parámetro `model`; en Workflow, `opts.model` en cada `agent()` y `model` en su entrada de `meta.phases`.
3. En workflows, empareja `opts.effort` con el escalón: `'low'` en el 1, omitido en el 2, `'high'` en el 3.

Hecho cuando cada llamada Agent/agent() del turno lleva `model` explícito.
