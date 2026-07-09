# Design — d15-catalogo-agentes

## Context

`design/VISTAS/03-catalogo.md` especifica un objeto `agent` compartido entre la grilla (vista 13) y la ficha (vista 14) con campos operativos (`status`, `model_profile`, `tools[]`) y campos de contenido comercial (`description`, `use_cases[]`, `examples[3]`, `owner`, `cost_estimate`, `prompt_version`, `evals`). Ese diseño se escribió en 2026-06, antes del pivote 2026-07-09, sobre un catálogo con 5 agentes reales (DocAgent, ValidationAgent, DevAgent + 2 de ejemplo para demostrar los estados `beta`/`deprecado`). El pivote reduce el catálogo real a `default_chat` + 1 agente de ejemplo (`a02-core-manifiestos`), ambos `status: active`. Este change debe entregar el contrato completo de catálogo y ficha sin inventar administración que todavía no existe (`d20-gobernanza-plataforma` para la matriz de visibilidad y el kill-switch; `e25-evals-gates` para el score de evals; `d21-builders` para crear agentes nuevos).

## Goals / Non-Goals

**Goals:**

- Grilla y ficha completas, por capas de rol, sobre los agentes `active` de `a02`.
- Contrato de lectura de visibilidad agente×rol con defaults sensatos mientras `d20` no existe, y un piso de seguridad no anulable que protege a Funcional de agentes con Tools de escritura.
- Contrato de lectura de kill-switch con default "habilitado" mientras `d20` no existe.
- read-model de contenido de ficha (descripción, límites, casos de uso, ejemplos, owner) desacoplado del `AgentManifest`, para no reabrir `a02`.

**Non-Goals:**

- Estados comerciales `beta`, `próximamente` y `deprecado` de la vista 13/14 original: la fábrica de este pivote solo tiene agentes `active` (`default_chat` + agente de ejemplo). El mapeo `status` del `AgentManifest` → estado comercial queda declarado (ver Decisión 2) para cuando `d21-builders` cree agentes en `draft`/`validated`/`deprecated`, pero ningún dato de fábrica ejercita esos estados todavía.
- Administración de la matriz de visibilidad, del kill-switch y del Registro de Prompts (`d20-gobernanza-plataforma`).
- Runner de evals (`e25-evals-gates`).
- Selector de contexto cliente/ambiente Protheus (Etapa P).

## Decisions

1. **El contenido de ficha vive en un read-model de aplicación propio (`agent_catalog_entry`), no en el `AgentManifest`.** Alternativa descartada: agregar `description`/`use_cases`/`examples`/`owner`/etc. al schema de `a02-core-manifiestos` — requeriría reabrir un change ya especificado y mezclaría gobernanza operativa (qué puede hacer el agente) con contenido comercial (cómo se presenta). El read-model referencia al agente por su `id` del Agent Registry, se persiste vía `b04-persistencia-postgres` y se siembra como fixture de fábrica en este change para `default_chat` y el agente de ejemplo. Su autoría futura (crear/editar desde una UI) es `d21-builders`; hasta entonces es contenido versionado en el repo, análogo a los manifiestos de fábrica de `a02`.
2. **Estado comercial derivado del `status` del `AgentManifest`, con un flag `beta` propio del read-model.** `active` → `activo`; `draft`/`validated` → `próximamente`; `deprecated` → `deprecado`; un agente `active` puede además marcarse `beta` en el read-model sin tocar su `status` real. Esto resuelve la ambigüedad entre el ciclo de vida técnico de `a02` (`draft → validado → active → deprecated`) y el estado comercial de `design/VISTAS/03-catalogo.md`, sin introducir un segundo campo `status` que colisione con el del manifiesto. La grilla de este change solo lista `active` (ver Non-Goals); el mapeo completo queda declarado para cuando existan agentes en otros estados.
3. **Kill-switch: contrato de lectura con default "habilitado", administración en `d20`.** Igual patrón que `agent-visibility`: mientras no exista una bandera explícita (porque `d20-gobernanza-plataforma` no está archivado), el agente se trata como habilitado. Evita que este change bloquee agentes por la sola ausencia de la infraestructura de flags. Config de instancia (mostrar-deshabilitado vs. ocultar) se modela como un valor booleano simple; su UI de configuración también es `d20`.
4. **Piso de seguridad de Funcional como regla no configurable, no como default de la matriz.** Alternativa descartada: tratarlo como "default recomendado" que el Admin puede sobrescribir vía matriz — se descarta porque el propio `design/FUNCIONALIDADES.md` §6 lo describe como comportamiento del sistema ("un Funcional no ve agentes cuyo toolset excede sus permisos"), no como configuración, y porque una matriz mal configurada no debe poder exponer tools de escritura a un rol sin tarjeta HITL. Se implementa como una intersección obligatoria en el caso de uso de visibilidad: `visible_final = visible_matriz AND NOT (rol == funcional AND agente.tiene_tool_escritura)`.
5. **Versión de prompt: se muestra la `version` semver del `AgentManifest` como sustituto transitorio.** Alternativa descartada: no mostrar nada hasta `d20` — se descarta porque la ficha técnica pierde valor de transparencia (uno de los principios adoptados sin cambio del roadmap). Se etiqueta explícitamente como valor transitorio para que Técnico/Admin no lo confundan con el Registro de Prompts inmutable futuro.
6. **Costo estimado agregado desde trazas de `b07-observabilidad`, no cacheado en el read-model.** Se calcula on-demand (o con cache corto de aplicación) sobre una ventana configurable por instancia; evita que el catálogo mantenga su propia copia de datos de costo que puedan desincronizarse de Langfuse.
7. **"Ver como rol" es una previsualización pura de lectura**, sin mutar sesión ni registrar auditoría — coherente con que este change no toca `core/` ni el Policy Gate.

## Risks / Trade-offs

- [El read-model de catálogo duplica conceptualmente al futuro `d21-builders`] → Mitigación: se documenta explícitamente como contenido de fábrica versionado en este change, con el mismo patrón que los manifiestos de ejemplo de `a02`; `d21` reemplaza la fuente de autoría, no el contrato de lectura que consume `d15`.
- [El piso de seguridad de Funcional depende de que `c09-mcp-tools` clasifique correctamente lectura/escritura] → Mitigación: la clasificación es fija por versión del `ToolManifest` (regla de `a02`/`c09`), no mutable en runtime; si `c09` aún no está archivado, el toolset del agente de fábrica (solo lectura) no activa el piso, y el comportamiento sigue siendo seguro por default (deny-by-default de la matriz).
- [Divergencia entre el estado comercial documentado en `design/` (4 estados) y el alcance real de este change (solo `activo`)] → Mitigación: declarado explícitamente en Non-Goals y en la Decisión 2; el mapeo evita tener que reabrir `agent-catalog` cuando aparezcan agentes en otros estados.
- [Costo estimado con `~` cuando Langfuse está caído puede leerse como dato real] → Mitigación: mismo patrón ya usado en `d13-chat-conversacion` para la etiqueta "modelo alterno" y en `design/FUNCIONALIDADES.md` §8.12 (convención `~` + tooltip), consistente en toda la plataforma.

## Open Questions

*(ninguna — las decisiones quedan tomadas arriba; los puntos que dependen de `d20`/`d21`/`e25` quedan como contratos de consumo documentados, no como preguntas abiertas de este change)*
