# response-feedback — Delta Spec (b07-observabilidad)

## ADDED Requirements

### Requirement: Captura de feedback por respuesta

El sistema SHALL exponer un servicio de captura de Feedback por cada respuesta del Default Chat: un valor 👍 (positivo) o 👎 (negativo), obligatorio, más un comentario de texto opcional. El servicio SHALL persistir el feedback como `score` en Langfuse, sin requerir que quien lo invoque conozca detalles del cliente Langfuse.

#### Scenario: Feedback positivo sin comentario

- **WHEN** un usuario envía 👍 sobre una respuesta sin agregar comentario
- **THEN** el servicio crea un score con valor positivo, comentario vacío, ligado a la respuesta evaluada

#### Scenario: Feedback negativo con comentario

- **WHEN** un usuario envía 👎 sobre una respuesta junto con un comentario de texto
- **THEN** el servicio crea un score con valor negativo y el comentario capturado tal cual lo escribió el usuario

### Requirement: Feedback ligado a traza y versión de prompt activa

Todo Feedback SHALL quedar ligado al `trace_id` del turno que produjo la respuesta evaluada y a la versión de prompt activa en el momento en que esa respuesta se generó (vínculo de Prompt Management de Langfuse), de forma que sea reconstruible qué versión exacta de qué prompt produjo la respuesta calificada.

#### Scenario: Feedback reconstruible junto a su traza

- **WHEN** se consulta el feedback capturado para una respuesta
- **THEN** el registro incluye el `trace_id` del turno y el identificador de versión del prompt activo en ese turno

#### Scenario: Dos respuestas del mismo turno con distinta versión de prompt

- **WHEN** una respuesta se regenera tras publicarse una nueva versión de prompt y ambas respuestas reciben feedback
- **THEN** cada feedback queda ligado a la versión de prompt que efectivamente generó esa respuesta, no a la versión activa al momento de la consulta

### Requirement: Retención permanente exenta de purgas

El Feedback SHALL conservarse indefinidamente y SHALL quedar excluido de cualquier proceso de purga automática de la plataforma, incluida la retención de 90 días configurada para adjuntos (`d14-attachments`). Ningún mecanismo de purga de la plataforma SHALL eliminar ni modificar un score de feedback ya creado; una corrección se expresa como un score nuevo, nunca como edición del existente.

#### Scenario: Purga de adjuntos no afecta el feedback asociado

- **WHEN** el adjunto vinculado a un turno se purga tras cumplir la retención de 90 días
- **THEN** el feedback capturado sobre la respuesta de ese turno permanece disponible sin cambios

#### Scenario: Corrección de un feedback existente

- **WHEN** un usuario cambia de opinión y quiere corregir un feedback ya enviado sobre la misma respuesta
- **THEN** el sistema crea un score nuevo que referencia al anterior, sin eliminar ni sobrescribir el original

### Requirement: Marca de candidato a caso de regresión

Un Feedback negativo (👎) que incluya comentario SHALL quedar marcado como candidato a caso de regresión (tag/metadata del score). Un 👎 sin comentario NO SHALL quedar marcado como candidato. Esta marca únicamente se almacena y se expone para consulta; el sistema NO SHALL procesar, convertir ni ejecutar la marca como caso de evaluación — esa transformación es responsabilidad exclusiva de `e25-evals-gates`.

#### Scenario: 👎 con comentario marcado como candidato

- **WHEN** un usuario envía 👎 con un comentario explicando el problema
- **THEN** el score creado queda marcado como candidato a caso de regresión, visible en su metadata

#### Scenario: 👎 sin comentario no se marca

- **WHEN** un usuario envía 👎 sin agregar ningún comentario
- **THEN** el score creado se persiste como feedback negativo pero sin la marca de candidato a caso de regresión

### Requirement: Candidatos a regresión consultables sin ejecutar evals

El sistema SHALL exponer una forma de consultar todos los Feedback marcados como candidato a caso de regresión (por ejemplo, filtrando por su tag en Langfuse) sin requerir que exista o se ejecute ningún runner de evals.

#### Scenario: Consulta de candidatos antes de que exista el runner de evals

- **WHEN** se consultan los candidatos a caso de regresión antes de que `e25-evals-gates` esté archivado
- **THEN** la consulta devuelve la lista de Feedback marcados, sin error y sin depender de ningún componente de evals
