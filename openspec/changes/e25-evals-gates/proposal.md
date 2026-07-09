# Proposal — e25-evals-gates

## Why

Los gates de publicación de `d20-gobernanza-plataforma` y `d21-builders` nacen **pluggables en modo placeholder** (Nota de desacople del roadmap, 2026-07-09): mientras no exista un runner de evals real, publicar una versión de prompt o un agente solo muestra la advertencia "score ausente", nunca bloquea. Eso deja abierta la regla dura del producto —"publicar con evals en rojo debe ser imposible por sistema" (`design/FUNCIONALIDADES.md` §12, Flujo F de `design/FLUJOS.md`)—. Este change cierra la brecha: aporta los datasets ejecutables, el runner trazado en Langfuse y el gate REAL que reemplaza el placeholder, además del circuito feedback 👎 → caso de regresión. La instrumentación Langfuse (trazas, costo, feedback ligado a traza y versión de prompt) ya quedó completa en `b07-observabilidad`; lo único diferido era el runner de evals/golden sets.

**Este change lo ejecuta el product owner AL FINAL**, cuando el resto de la plataforma está funcionando (todas sus dependencias archivadas). Se especifica ahora para dejar el plan completo y autocontenido.

## What Changes

- Se crean **datasets de evals** en YAML versionados por agente/skill/workflow bajo `evals/`, con casos que declaran input, salida esperada o criterios de aceptación deterministas, y categoría; los casos `safety` se marcan explícitamente y aplican **hard-fail individual** (uno solo en rojo bloquea, sin importar el score global). Los ≥3 casos de eval que `d21-builders` exige por skill se materializan aquí como datasets ejecutables. **Solo datos sintéticos** — jamás datos reales de clientes.
- Se crea el **runner de evals**: ejecuta un dataset contra una versión de prompt/agente a través del gateway de modelos (`b05-gateway-modelos`), traza cada caso en Langfuse (`b07-observabilidad`) con score por caso vía la API de scores de Langfuse, y produce un score por versión (% de casos OK) más el detalle por caso. Ejecutable en local y en CI.
- Se **reemplaza el modo placeholder** de los gates de publicación de `d20`/`d21` por el **gate REAL**: publicar exige score ≥ 80% **Y** cero casos `safety` en rojo, verificado por el sistema (imposible saltárselo); el botón Publicar se deshabilita con el detalle de los casos fallados (vista `43-admin-evals.html`); el score vigente aparece en la ficha técnica del agente (`d15-catalogo-agentes`).
- Se agrega el **gate de CI**: un score < 80% en los datasets de los agentes/skills activos bloquea el pipeline.
- Se agrega el circuito **feedback → regresión**: los 👎 con comentario marcados como "candidato a regresión" en `b07` se convierten en caso de eval mediante revisión humana (bandeja de la vista 43, conversión a un clic con caso prellenado); todo bug de producción se convierte en caso de regresión.
- Se agrega la **UI** de la vista 43 (`43-admin-evals.html`): lanzar runs del draft, ver score por versión, detalle de casos, historial de runs y la bandeja de conversión de feedback.

## Capabilities

### New Capabilities

- `evals`: datasets YAML por agente/skill/workflow (solo datos sintéticos), runner trazado en Langfuse, score por versión con detalle por caso, `safety` hard-fail individual, y el circuito feedback 👎 → caso de regresión (golden set).
- `publication-gates`: el gate REAL de publicación (score ≥ 80% + cero safety en rojo, verificado por sistema) y el gate de CI; documenta explícitamente que REEMPLAZA el modo placeholder con que nacen los gates de `d20`/`d21` y define la transición.

### Modified Capabilities

*(ninguna — los specs de `d20-gobernanza-plataforma` y `d21-builders` aún no están archivados en `openspec/specs/`; la transición desde el modo placeholder se documenta como requisitos ADDED dentro de `publication-gates`, no como MODIFIED).*

## No-objetivos

- **Evals con datos reales de clientes.** Quedan para la Etapa P (personalización). En V1 todos los datasets son sintéticos; un dataset con datos reales se rechaza en revisión.
- **Red teaming automatizado.** No se genera adversarialmente ningún caso; el golden set se nutre de casos escritos a mano, feedback convertido y bugs de producción.
- **Evaluadores LLM-as-judge complejos.** Decisión de diseño: en V1 los criterios de aceptación son **deterministas primero** (comparación exacta/normalizada, contención de subcadena, coincidencia de patrón, aserciones estructurales). Un evaluador tipo judge/calibración (panel de calibración de la vista 43) queda **documentado como opcional** y diferido, no implementado en V1.
- No se toca la instrumentación de Langfuse (ya completa en `b07`): este change la consume, no la reescribe.

## Bounded context afectado

`governance` (subdominio de evals) en `resultarai/app/` + carpeta `evals/` en la raíz del repo (datasets versionados, espejo del contrato de calidad) + frontend (`frontend/`, vista `43-admin-evals`). No toca `core/` (el runner es un servicio de aplicación que orquesta gateway y trazas vía adapters; no introduce lógica de dominio pura nueva). No pertenece a los bounded contexts funcionales de chat/attachments/HITL.

## Impact

- `evals/` (raíz): datasets YAML por agente/skill/workflow (empezando por los de contenido de ejemplo de fábrica), con casos `safety` marcados.
- `resultarai/app/`: servicio de runner de evals, servicio de gate de publicación, servicio de conversión feedback → caso.
- `resultarai/adapters/`: uso del gateway de modelos (`b05`) y del adapter Langfuse (`b07`, API de scores) — sin nuevos ports en `core/`.
- CI (`.github/workflows/`): job de gate de evals que bloquea con score < 80%.
- Frontend: vista `43-admin-evals` (suites, corridas, detalle por caso, historial, bandeja de feedback).
- Reemplazo del modo placeholder de los gates de `d20-gobernanza-plataforma` (Registro de Prompts, publicación) y `d21-builders` (Agent/Skills Builder).
- Referencia del blueprint: capa 12 "Evaluation-as-Code" y principio 16 "evaluaciones preparadas, no necesariamente definidas" (`docs/06-seguridad-gobernanza.md`, estrategia de evals placeholder-por-diseño).
