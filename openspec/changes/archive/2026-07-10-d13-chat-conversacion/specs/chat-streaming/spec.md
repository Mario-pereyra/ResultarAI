## ADDED Requirements

### Requirement: Creación de sesión con agente del catálogo y stickiness de perfil

El endpoint de creación de sesión SHALL requerir el identificador de un agente del catálogo, crear la sesión asociada a ese agente y fijar su perfil de modelo (`model_profile`) inicial según la cascada de fallback del Agent Manifest (`model-profiles` de `b05-gateway-modelos`). Una sesión SHALL vivir en un único `model_profile` mientras no se cree explícitamente una sesión/rama nueva con otro perfil (stickiness, `conversation-persistence` de `b04-persistencia-postgres`).

#### Scenario: Crear sesión fija el perfil inicial

- **WHEN** un usuario autenticado solicita crear una sesión indicando un agente del catálogo
- **THEN** el sistema crea la sesión, la asocia a ese agente y registra el primer perfil de la cascada del agente como `model_profile` de la sesión

#### Scenario: Turnos posteriores no cambian el perfil de la sesión

- **WHEN** se envían turnos sucesivos dentro de la misma sesión sin pasar por escalación manual
- **THEN** el `model_profile` de la sesión permanece el mismo declarado al crearla, incluso si el gateway usó un perfil de fallback para responder un turno puntual

### Requirement: Envío de turno crea mensaje encadenado por `parent_id`

El endpoint de envío de turno SHALL crear un mensaje de usuario cuyo `parent_id` apunta al último mensaje de la rama activa de la sesión, y SHALL invocar el runtime (`agent-runtime` de `b06-runtime-grafos`) para generar la respuesta sobre ese mensaje.

#### Scenario: Turno normal se encadena al final de la rama activa

- **WHEN** el usuario envía el texto de un turno nuevo en una sesión con historia previa
- **THEN** el sistema crea el mensaje de usuario con `parent_id` igual al último mensaje de la rama activa y dispara la generación de la respuesta correspondiente

### Requirement: El marcador de escalación nunca se expone crudo en el stream

El endpoint de streaming SHALL nunca transmitir el texto literal `<<<NEEDS_PRO>>>` al cliente. Cuando el gateway (`escalation-marker` de `b05-gateway-modelos`) emite un evento de escalación para la respuesta en curso, el endpoint SHALL traducirlo a un evento de dominio de escalación separado del texto de la respuesta.

#### Scenario: Evento de escalación reemplaza al marcador crudo

- **WHEN** la respuesta generada por el modelo contiene el marcador de escalación según el contrato de `b05-gateway-modelos`
- **THEN** el stream entregado al cliente omite el marcador del texto de respuesta y en su lugar incluye un evento de escalación con la razón y el perfil de destino

### Requirement: Streaming SSE incremental con evento de cierre

El endpoint de turno SHALL transmitir la respuesta del agente por Server-Sent Events en fragmentos incrementales de texto a medida que el runtime los produce, y SHALL cerrar el stream con un evento final que incluya los metadatos completos del turno (perfil de modelo efectivamente usado, si hubo modelo alterno, indicador de compaction si aplicó, evento de escalación si lo hubo).

#### Scenario: Fragmentos llegan en orden antes del cierre

- **WHEN** el runtime produce el texto de la respuesta en partes sucesivas
- **THEN** el cliente recibe cada parte como un evento SSE en el mismo orden en que se generó, seguido de un evento de cierre con los metadatos del turno completo

### Requirement: Reconexión con heartbeat del stream SSE

El endpoint de streaming SHALL enviar un evento de heartbeat periódico mientras no haya contenido nuevo que transmitir, y SHALL permitir que un cliente reconecte a un turno en curso usando su identificador para continuar recibiendo eventos desde el punto de corte, sin duplicar contenido ya entregado ni reiniciar la generación de la respuesta.

#### Scenario: Heartbeat mantiene la conexión viva

- **WHEN** el runtime tarda en producir el siguiente fragmento de texto
- **THEN** el servidor envía un evento heartbeat antes de que el cliente o un proxy intermedio considere la conexión caída

#### Scenario: Reconexión tras un corte no duplica contenido

- **WHEN** la conexión SSE se corta antes de que el turno termine y el cliente reconecta con el identificador del turno en curso
- **THEN** el servidor retoma el envío de eventos desde el último fragmento no confirmado por el cliente, sin repetir fragmentos ya entregados ni volver a invocar al modelo

### Requirement: Cancelación de un stream en curso

El sistema SHALL exponer una operación de cancelación que, mientras un turno está generando su respuesta, detiene la generación, persiste el texto generado hasta ese punto marcado explícitamente como "detenida por el usuario", y deja el turno disponible para regenerar.

#### Scenario: Cancelar detiene la generación y conserva lo parcial

- **WHEN** el usuario cancela un turno mientras la respuesta se está transmitiendo
- **THEN** el servidor detiene la invocación al runtime, persiste el texto generado hasta ese momento como respuesta parcial marcada "detenida", y cierra el stream sin error

### Requirement: Edición de un mensaje propio crea una rama nueva

Cuando el usuario envía la edición de un mensaje propio ya persistido, el sistema SHALL crear un mensaje nuevo con el mismo `parent_id` que el mensaje original (rama hermana), sin modificar ni eliminar el mensaje original ni ningún mensaje posterior de la rama original, y SHALL generar la respuesta del agente sobre la rama nueva.

#### Scenario: Editar un mensaje no reescribe la historia

- **WHEN** el usuario edita el texto de un mensaje propio y lo envía
- **THEN** el sistema conserva el mensaje original intacto, crea un mensaje nuevo como hermano bajo el mismo `parent_id`, y ambas versiones quedan navegables

#### Scenario: Solo el autor puede editar su mensaje

- **WHEN** un usuario intenta editar un mensaje que no es propio
- **THEN** el sistema rechaza la operación sin crear ninguna rama

### Requirement: Regenerar una respuesta crea una rama nueva

Cuando el usuario solicita regenerar la respuesta de un turno, el sistema SHALL crear un mensaje de agente nuevo como hermano de la respuesta existente bajo el mismo mensaje de usuario, sin modificar ni eliminar la respuesta anterior.

#### Scenario: Regenerar agrega una versión sin borrar la anterior

- **WHEN** el usuario pulsa "regenerar" sobre una respuesta ya recibida
- **THEN** el sistema invoca de nuevo al runtime para ese mensaje de usuario y persiste la nueva respuesta como versión hermana de la anterior, ambas navegables

### Requirement: Escalación manual crea una sesión/rama nueva con el perfil configurado

Cuando el usuario confirma la escalación tras recibir un evento de escalación en un agente con la escalación habilitada (Agent Manifest de `a02-core-manifiestos`), el sistema SHALL crear una sesión o rama nueva con el perfil de modelo de escalación configurado para ese agente, re-planteando la consulta con el contexto necesario, y la sesión/rama original SHALL permanecer intacta y accesible. El sistema SHALL NUNCA crear la sesión/rama escalada sin esa confirmación explícita del usuario.

#### Scenario: Confirmar escalación abre sesión/rama nueva con el perfil Pro

- **WHEN** el usuario confirma "Continuar con Pro" tras un evento de escalación
- **THEN** el sistema crea una sesión/rama nueva con el `model_profile` de escalación del agente, la sesión original queda intacta, y la nueva sesión/rama queda enlazada a la original para navegación en ambos sentidos

#### Scenario: Escalación deshabilitada por agente rechaza la operación

- **WHEN** se solicita escalar en un agente cuyo Agent Manifest tiene la escalación deshabilitada
- **THEN** el sistema rechaza la operación de escalación sin crear ninguna sesión/rama nueva
