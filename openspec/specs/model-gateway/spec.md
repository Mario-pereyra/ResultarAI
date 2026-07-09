# model-gateway Specification

## Purpose
TBD - created by archiving change b05-gateway-modelos. Update Purpose after archive.
## Requirements
### Requirement: Todas las llamadas a modelo pasan exclusivamente por LiteLLM

El adapter `resultarai/adapters/llm_litellm/` SHALL ser la única implementación de `LLMPort` (`a03-core-gobernanza`) y SHALL ser el único punto del sistema que invoca un modelo de lenguaje. Ningún módulo fuera de este adapter SHALL importar un SDK de proveedor (OpenAI, Anthropic, etc.) directamente.

#### Scenario: Invocación exclusiva vía el port

- **WHEN** cualquier caso de uso de `app/` necesita una respuesta de un modelo de lenguaje
- **THEN** la única vía disponible es invocar `LLMPort`, cuya única implementación registrada es `resultarai.adapters.llm_litellm`, la cual delega en LiteLLM

#### Scenario: Ningún SDK de proveedor fuera del adapter

- **WHEN** se ejecuta `lint-imports` (import-linter) sobre el repo
- **THEN** ningún módulo de `resultarai/core/`, `resultarai/app/` u otro `resultarai/adapters/*` importa un SDK de proveedor de modelos; solo `resultarai/adapters/llm_litellm/` puede importar `litellm`

### Requirement: Cascada de fallback configurable ejecutada en orden

El gateway SHALL intentar los perfiles de modelo de la cascada de fallback del agente en el orden declarado en su configuración, pasando al siguiente perfil únicamente cuando el perfil actual falla (error del proveedor, timeout, respuesta inválida o proveedor sin credenciales disponibles).

#### Scenario: Fallback al segundo perfil de la cascada

- **WHEN** el primer perfil de la cascada del agente falla (por ejemplo, error 5xx del proveedor o timeout)
- **THEN** el gateway invoca el siguiente perfil de la cascada sin propagar el error intermedio al llamador, y la respuesta final queda marcada con el metadato de "modelo alterno"

#### Scenario: Primer perfil responde con éxito

- **WHEN** el primer perfil de la cascada del agente responde con éxito
- **THEN** el gateway no intenta ningún perfil adicional de la cascada

### Requirement: Error claro ante agotamiento de la cascada, nunca degradación silenciosa

Si ningún perfil de la cascada de un agente responde con éxito, el gateway SHALL retornar un error tipado y explícito al llamador identificando los perfiles intentados y la causa de cada falla. El gateway SHALL NUNCA generar ni retornar una respuesta parcial, simulada, de un modelo no configurado en la cascada, o degradada sin señalarlo explícitamente como error.

#### Scenario: Cascada completamente agotada

- **WHEN** todos los perfiles configurados en la cascada de fallback de un agente fallan en la misma invocación
- **THEN** `LLMPort` retorna un error tipado (por ejemplo, agotamiento de cascada) que identifica cada perfil intentado y su causa de falla, y no se produce ningún texto de respuesta de modelo

#### Scenario: Perfil sin proveedor disponible en la instancia

- **WHEN** un perfil de la cascada referencia un proveedor sin credenciales configuradas en la instancia
- **THEN** el gateway trata ese perfil como fallido para efectos de la cascada, sin reintentarlo indefinidamente, y lo reporta como causa si resulta ser el último intento

### Requirement: Contadores de cache hit/miss expuestos en el contrato de salida

El contrato de salida de `LLMPort` SHALL incluir los contadores de tokens de cache hit y de cache miss reportados por el proveedor subyacente en el `usage` de cada respuesta, identificados por el perfil de modelo que los originó.

#### Scenario: El proveedor reporta cache hit y miss

- **WHEN** el proveedor subyacente reporta tokens de cache hit y tokens de cache miss en el usage de su respuesta
- **THEN** el gateway propaga ambos contadores sin pérdida en el contrato de salida del port, asociados al perfil de modelo usado

#### Scenario: El proveedor no reporta contadores de cache

- **WHEN** el proveedor subyacente no reporta contadores de cache en su usage
- **THEN** el gateway expone esos contadores como ausentes (no como cero), para no falsear la telemetría (`b07`) ni el cálculo de cuotas (`d16`)

