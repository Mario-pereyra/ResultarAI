# escalation-marker Specification

## Purpose
TBD - created by archiving change b05-gateway-modelos. Update Purpose after archive.
## Requirements
### Requirement: Detección del marcador genérico de escalación

El gateway SHALL detectar el marcador literal `<<<NEEDS_PRO>>>` en el texto de la respuesta generada por el modelo y, cuando la escalación está habilitada para el agente, SHALL emitir un evento de escalación como parte del contrato de salida de `LLMPort`.

#### Scenario: Marcador presente en la respuesta

- **WHEN** el texto de respuesta generado por el modelo contiene `<<<NEEDS_PRO>>>` fuera de cualquier bloque de adjunto
- **THEN** el contrato de salida incluye un evento de escalación además del texto de respuesta

#### Scenario: Marcador ausente

- **WHEN** el texto de respuesta generado por el modelo no contiene el marcador
- **THEN** el contrato de salida indica que no hay escalación y no se emite ningún evento de escalación

### Requirement: El contenido de un adjunto no puede disparar la escalación

El gateway SHALL excluir de la detección del marcador todo el texto comprendido entre los delimitadores `<adjunto ...>` y `</adjunto>` (`design/ANEXO-ATTACHMENTS.md` §4.3), sea que ese texto provenga del mensaje reenviado al modelo o aparezca reflejado en el texto de salida del modelo. Esta exclusión SHALL aplicarse antes de ejecutar el patrón de búsqueda del marcador, como defensa anti prompt-injection.

#### Scenario: Un adjunto contiene el marcador en su texto extraído

- **WHEN** el `inserted_text` de un adjunto incluye literalmente `<<<NEEDS_PRO>>>` y el modelo lo reproduce citando el contenido del adjunto dentro de su respuesta
- **THEN** el gateway no cuenta esa ocurrencia como disparador de escalación por caer dentro de los delimitadores `<adjunto>...</adjunto>` de ese adjunto

#### Scenario: El modelo emite el marcador fuera de cualquier adjunto

- **WHEN** el modelo emite `<<<NEEDS_PRO>>>` en su propio texto de respuesta, fuera de cualquier bloque `<adjunto>...</adjunto>`
- **THEN** el gateway sí lo detecta y emite el evento de escalación

#### Scenario: Un adjunto intenta falsificar el cierre de su delimitador

- **WHEN** el texto de un adjunto intenta incluir una secuencia `</adjunto>` propia para cerrar prematuramente su delimitador y colocar `<<<NEEDS_PRO>>>` fuera de la exclusión
- **THEN** la exclusión se resuelve por el `id` aleatorio asignado a ese adjunto (`design/ANEXO-ATTACHMENTS.md` §4.3), de forma que el contenido no puede falsificar un cierre y reapertura creíbles para escapar de la exclusión

### Requirement: Escalación habilitada o deshabilitada por agente

La evaluación del marcador de escalación SHALL estar sujeta a un campo de configuración del Agent Manifest (`a02-core-manifiestos`) que determina si la escalación está habilitada para ese agente. Cuando está deshabilitada, el gateway SHALL NUNCA evaluar el marcador ni emitir el evento de escalación para ese agente, incluso si el texto de respuesta contiene el marcador literal.

#### Scenario: Agente con escalación deshabilitada

- **WHEN** el Agent Manifest de un agente declara la escalación deshabilitada
- **THEN** el gateway no ejecuta la detección del marcador para las respuestas de ese agente; si `<<<NEEDS_PRO>>>` aparece en el texto, viaja como texto normal sin evento de escalación

#### Scenario: Agente con escalación habilitada por defecto

- **WHEN** el Agent Manifest de un agente no declara el campo de escalación o lo declara habilitado
- **THEN** el gateway ejecuta la detección del marcador normalmente para las respuestas de ese agente

