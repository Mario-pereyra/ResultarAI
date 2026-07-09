# Proposal — b05-gateway-modelos

## Why

Regla dura del proyecto: toda llamada a modelo pasa por LiteLLM, nunca SDKs de proveedor directos (CLAUDE.md, regla 2). Sin este adapter no existe ningún camino legal para que `core/` invoque un LLM, y `b06-runtime-grafos` (graph templates que responden vía Default Chat) no tiene con qué ejecutar. Además, dos comportamientos genéricos del producto —transparencia de "modelo alterno" ante fallback y el marcador de escalación `<<<NEEDS_PRO>>>`— deben nacer en el gateway porque son propiedades de la respuesta del modelo, no de la UI que las consume después (`d13`).

## What Changes

- Se implementa el adapter `resultarai/adapters/llm_litellm/` que satisface `LLMPort` (definido en `a03-core-gobernanza`) invocando LiteLLM exclusivamente.
- Se define **perfil de modelo** como configuración versionada (no hardcode): modelo/proveedor + parámetros de invocación, con una **cascada de fallback** configurable por agente (orden de perfiles a intentar). Si ningún proveedor de la cascada responde, el gateway retorna un error claro y tipado — nunca degrada de perfil en silencio.
- Toda respuesta que provino de un perfil distinto al primario de la cascada viaja con el metadato **"modelo alterno"** (perfil efectivamente usado + motivo), como parte del contrato de salida del port. El contrato lo expone para todos los roles; el consumo visual queda para `d13`.
- Se exponen **contadores de cache hit/miss** tomados del `usage` que reporta el proveedor vía LiteLLM, con tarifas hit/miss separadas por perfil, para telemetría (`b07`) y cuotas (`d16`).
- Se implementa la detección del **marcador genérico de escalación** `<<<NEEDS_PRO>>>` en el texto de respuesta del modelo: al detectarlo se emite un evento de escalación en el contrato de salida del port. El contenido dentro de los delimitadores `<adjunto ...>...</adjunto>` (ANEXO-ATTACHMENTS §4.3) se excluye de la búsqueda del marcador **antes** de invocar al modelo, de forma que un adjunto nunca puede disparar la escalación por eco/inyección.
- La escalación es habilitable/deshabilitable por agente vía un campo del Agent Manifest (`a02`); si está deshabilitada, el gateway no evalúa el marcador para ese agente.
- Stickiness de perfil (una sesión vive en un solo `model_profile`; cambiar de modelo implica una rama/sesión nueva) se declara aquí como invariante del contrato del port; su persistencia real es de `b04`.

## Capabilities

### New Capabilities

- `model-gateway`: adapter `LLMPort` → LiteLLM; ejecución de la cascada de fallback; errores claros y tipados ante agotamiento de la cascada; contadores de cache hit/miss expuestos en el contrato de salida.
- `model-profiles`: perfiles de modelo y sus cascadas de fallback como configuración versionada por agente (no hardcode), con tarifas hit/miss separadas por perfil.
- `escalation-marker`: detección del marcador `<<<NEEDS_PRO>>>` en la respuesta del modelo, exclusión del contenido de adjuntos de esa detección, emisión del evento de escalación, y habilitación/deshabilitación por agente.

### Modified Capabilities

*(ninguna — no existen specs previas para estas capacidades)*

## No-objetivos

- Ninguna UI de escalación ni botón "Continuar con Pro" (llega en `d13-chat-conversacion`).
- Ningún motor de cuotas ni bloqueo por consumo (llega en `d16-cuotas-liberaciones`); aquí solo se exponen los contadores que ese motor consumirá.
- Ningún prompt caching **medido** ni optimización de layout de prompt para maximizar hit rate (Etapa P); aquí solo se leen y exponen los contadores que el proveedor ya reporta.
- Ninguna persistencia de sesión/mensajes/stickiness (pertenece a `b04-persistencia-postgres`); aquí el port solo declara la invariante de contrato.
- Ningún graph template ni Skill Router (llega en `b06-runtime-grafos`); este change no decide cuándo se llama al modelo, solo cómo se lo llama.
- Ninguna política de datos por nivel N0–N3 ni scrubber de PII hacia el LLM (Etapa P, ADR-0014); la cascada filtra por perfil disponible, no por nivel de dato.

## Bounded context afectado

`gateway` (`docs/02-arquitectura.md`): binding LiteLLM, cache profiles, canonicalización de prompts. Implementación en `resultarai/adapters/llm_litellm/`. Consume el port `LLMPort` de `resultarai/core/ports/` (`a03-core-gobernanza`) y los campos de escalación del Agent Manifest (`a02-core-manifiestos`).

## Impact

- Nuevo paquete `resultarai/adapters/llm_litellm/` (implementación del port, cascada, detección de marcador).
- `manifests/agents/*.yaml`: nuevo campo de configuración de escalación por agente (habilitada/deshabilitada) y referencia a perfiles/cascada.
- Configuración de perfiles de modelo y cascadas (`manifests/` o config de instancia versionada — se decide en `design.md`).
- `tests/contracts/`: contract tests del adapter contra un proveedor simulado (sin red real).
- No afecta `app/`, `runtime_langgraph` (`b06`) ni ninguna vista de `design/` (solo su contrato de datos).
