# model-profiles Specification

## Purpose
TBD - created by archiving change b05-gateway-modelos. Update Purpose after archive.
## Requirements
### Requirement: Perfil de modelo como configuración versionada, no hardcode

Un perfil de modelo SHALL definirse como configuración versionada en Git (no hardcodeada en `resultarai/adapters/llm_litellm/`), especificando como mínimo: identificador de perfil, proveedor, modelo, parámetros de invocación y tarifas de cache hit/miss.

#### Scenario: Nuevo perfil sin cambio de código

- **WHEN** se agrega o modifica un perfil de modelo en la configuración versionada
- **THEN** el perfil queda disponible para el gateway sin requerir ningún cambio en el código de `resultarai/adapters/llm_litellm/`

### Requirement: Cascada de fallback declarada por agente

La cascada de fallback de un agente SHALL declararse como una lista ordenada de perfiles de modelo en su Agent Manifest (`a02-core-manifiestos`), no en código ni compartida implícitamente entre agentes.

#### Scenario: Dos agentes con cascadas distintas

- **WHEN** dos Agent Manifest declaran cascadas de fallback distintas
- **THEN** el gateway respeta la cascada propia de cada agente al resolver sus invocaciones, sin aplicar una cascada global compartida

### Requirement: Tarifas de cache hit/miss separadas por perfil

Cada perfil de modelo SHALL declarar una tarifa de cache hit y una tarifa de cache miss por separado, permitiendo calcular el costo real de cada respuesta para telemetría (`b07-observabilidad`) y cuotas (`d16-cuotas-liberaciones`).

#### Scenario: El costo usa la tarifa correcta según hit o miss

- **WHEN** una respuesta reporta tokens de cache hit y tokens de cache miss para un perfil de modelo
- **THEN** el costo expuesto en el contrato de salida aplica la tarifa hit del perfil a los tokens hit y la tarifa miss del mismo perfil a los tokens miss

### Requirement: Etiqueta "modelo alterno" cuando responde un perfil de fallback

Cuando la respuesta final de una invocación proviene de un perfil distinto al primero de la cascada del agente, el contrato de salida de `LLMPort` SHALL incluir el metadato de "modelo alterno": el perfil efectivamente usado, el perfil primario original de la cascada, y el motivo del fallback. Este metadato SHALL viajar con la respuesta y estar disponible para todos los roles en las capas superiores.

#### Scenario: Respuesta con modelo alterno lleva el metadato

- **WHEN** el gateway responde usando el segundo perfil de la cascada porque el primero falló
- **THEN** el contrato de salida marca la respuesta como generada por modelo alterno e incluye el perfil usado, el perfil primario y el motivo del fallback

#### Scenario: Respuesta con el perfil primario no lleva la etiqueta

- **WHEN** el gateway responde usando el primer perfil de la cascada sin que ocurra ningún fallback
- **THEN** el contrato de salida indica explícitamente que la respuesta NO es de modelo alterno

### Requirement: Stickiness de perfil como invariante verificable del contrato

El port SHALL exponer, en cada respuesta, el perfil efectivamente usado, de forma que las capas superiores (`b04-persistencia-postgres`) puedan hacer cumplir que una sesión viva en un único perfil de modelo (stickiness). El gateway SHALL NUNCA sustituir por sí mismo el perfil primario de una cascada a mitad de una sesión sin que el llamador envíe explícitamente una cascada distinta en esa invocación.

#### Scenario: El gateway no retiene estado de sesión

- **WHEN** un caso de uso invoca el gateway dos veces dentro de la misma sesión con la misma cascada de fallback
- **THEN** el perfil primario considerado en cada invocación depende únicamente de la cascada recibida en esa llamada; el gateway no mantiene ni fuerza estado de sesión propio, dejando la persistencia de stickiness a `b04-persistencia-postgres`

