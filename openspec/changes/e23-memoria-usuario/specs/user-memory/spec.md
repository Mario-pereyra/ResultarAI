# user-memory — Delta Spec (e23-memoria-usuario)

## ADDED Requirements

### Requirement: El agente solo propone, nunca guarda memoria por sí mismo

Cuando una respuesta del Default Chat incluye una propuesta de guardar contenido en la Memoria de usuario, el sistema SHALL presentarla al usuario de forma inline en el chat con las opciones "Guardar" y "Descartar" (`design/FUNCIONALIDADES.md` §4, `design/VISTAS/06-mi-espacio.md` vista 24). El sistema SHALL NUNCA persistir una entrada de memoria sin una confirmación explícita del usuario sobre esa propuesta puntual.

#### Scenario: Propuesta presentada de forma inline

- **WHEN** una respuesta del agente contiene una propuesta de memoria
- **THEN** el chat muestra la propuesta con el texto propuesto y los botones "Guardar" / "Descartar", sin haber escrito nada todavía en la Memoria de usuario

#### Scenario: Ninguna respuesta persiste memoria sin propuesta

- **WHEN** una respuesta del agente no contiene una propuesta de memoria
- **THEN** la Memoria de usuario permanece sin cambios y no se crea ninguna versión nueva

### Requirement: Aceptar o rechazar una propuesta de memoria

El usuario SHALL poder aceptar o rechazar cada propuesta de forma independiente. Al aceptar, el sistema SHALL ejecutar el mismo validador de contenido prohibido y el mismo control de límite de tokens que aplica a la edición manual antes de crear la versión nueva. Al rechazar, el sistema SHALL descartar la propuesta sin ningún efecto sobre la Memoria de usuario.

#### Scenario: Propuesta rechazada no se guarda nada

- **WHEN** el usuario hace clic en "Descartar" sobre una propuesta de memoria
- **THEN** no se crea ninguna versión nueva, el texto de la Memoria de usuario no cambia, y la propuesta desaparece del chat sin dejar rastro en el historial de cambios

#### Scenario: Propuesta aceptada y válida crea una versión nueva

- **WHEN** el usuario hace clic en "Guardar" sobre una propuesta de memoria y el texto propuesto pasa el validador de contenido prohibido y el límite de tokens
- **THEN** se crea una versión nueva de la Memoria de usuario con `origen = "propuesta del agente (aceptada por vos)"`, visible y editable de inmediato en Mi memoria

#### Scenario: Propuesta aceptada mostrada al usuario también si falla la validación

- **WHEN** el usuario hace clic en "Guardar" sobre una propuesta de memoria y el texto propuesto no pasa el validador de contenido prohibido o excede el límite de tokens
- **THEN** no se crea ninguna versión nueva, el chat muestra por qué no se pudo guardar con un link a Mi memoria, y el texto propuesto no se pierde (queda disponible para que el usuario lo ajuste manualmente en Mi memoria)

### Requirement: Memoria de usuario como texto único versionado con límite de ~1.000 tokens

La Memoria de usuario SHALL modelarse como un texto plano único por usuario (`memoria.texto`, perfil personal — NUNCA historial de conversaciones), con un límite duro de aproximadamente 1.000 tokens estimados (~4 caracteres/token). Cada guardado exitoso (edición manual o propuesta aceptada) SHALL crear una versión nueva; ninguna versión anterior SHALL sobrescribirse ni eliminarse del historial (append-only).

#### Scenario: Guardado dentro del límite crea versión nueva

- **WHEN** el usuario guarda un texto de memoria estimado en 850 tokens
- **THEN** se crea una versión nueva con ese texto y el contador se actualiza a "≈850 / 1.000 tokens"

#### Scenario: Guardado que excede el límite se bloquea con motivo

- **WHEN** el usuario intenta guardar un texto de memoria estimado en 1.120 tokens
- **THEN** el guardado se deshabilita con el motivo "te pasaste por ≈120 tokens — recortá antes de guardar" y no se crea ninguna versión nueva

#### Scenario: La memoria nunca contiene ni deriva del historial de conversaciones

- **WHEN** se construye o valida un texto de Memoria de usuario
- **THEN** el sistema no ofrece ningún mecanismo que copie o derive automáticamente contenido del historial de mensajes de una sesión hacia la memoria

### Requirement: Edición manual con confirmación obligatoria

Guardar una edición manual del texto de memoria SHALL requerir una confirmación explícita separada de la acción de escribir (modal con resumen del cambio: líneas agregadas/quitadas y variación de tokens estimados) y SHALL mostrar el aviso fijo de que el cambio se aplica desde la próxima conversación, no en las sesiones ya abiertas.

#### Scenario: Confirmación muestra el resumen del cambio

- **WHEN** el usuario hace clic en "Guardar memoria" tras editar el texto
- **THEN** aparece un modal con el resumen del diff y el aviso "se aplica desde tu próxima conversación"; solo tras confirmar se crea la versión nueva

#### Scenario: Cancelar la confirmación no persiste nada

- **WHEN** el usuario cierra el modal de confirmación con "Cancelar" o Esc
- **THEN** no se crea ninguna versión nueva y el texto editado permanece en el editor sin perderse

### Requirement: Borrado total como versión vacía, append-only

"Borrar todo" SHALL exigir escribir la palabra de confirmación exacta (glosario cerrado por idioma de instancia) antes de habilitar el botón destructivo. El borrado SHALL registrarse como una versión nueva con texto vacío — nunca como eliminación física del historial de versiones previas.

#### Scenario: Borrado exige escribir la palabra de confirmación

- **WHEN** el usuario abre el modal de "Borrar todo" y no ha escrito la palabra de confirmación exacta
- **THEN** el botón de borrado permanece deshabilitado

#### Scenario: Borrado confirmado crea versión vacía sin eliminar el historial

- **WHEN** el usuario escribe la palabra de confirmación exacta y confirma el borrado
- **THEN** se crea una versión nueva con `memoria.texto` vacío, y todas las versiones anteriores permanecen intactas y visibles en el historial de cambios

### Requirement: Validación fail-closed de contenido prohibido

Antes de crear cualquier versión nueva (edición manual o propuesta aceptada), el sistema SHALL validar el texto contra credenciales/secretos y datos personales estructurados de clientes reales (PII: CI, teléfono, correo personal, entre otros). A diferencia del escaneo N2 de adjuntos de `d14-attachments`, aquí NO SHALL existir una opción de confirmar y continuar: cualquier hallazgo de credencial o de PII real bloquea el guardado sin excepción. Si el validador no responde, el sistema SHALL bloquear el guardado (fail-closed: sin validación no hay escritura).

#### Scenario: Credencial detectada bloquea el guardado

- **WHEN** el texto a guardar contiene una cadena reconocible como credencial (por ejemplo `clave=Andina2026!`)
- **THEN** el guardado se rechaza, la ubicación del hallazgo se muestra al usuario, y no se crea ninguna versión nueva

#### Scenario: PII real detectada bloquea el guardado sin opción de continuar

- **WHEN** el texto a guardar contiene un dato personal estructurado de un cliente real (CI, teléfono o correo personal)
- **THEN** el guardado se rechaza con el motivo específico y no se ofrece ningún checkbox de "son datos de prueba" para continuar de todas formas

#### Scenario: Validador no disponible bloquea el guardado

- **WHEN** el servicio de validación de contenido no responde
- **THEN** el guardado se bloquea con un error accionable ("no pudimos validar tu memoria" + reintentar) y no se crea ninguna versión nueva

#### Scenario: El texto del usuario nunca se pierde ante un rechazo de validación

- **WHEN** el guardado se rechaza por cualquiera de los motivos anteriores
- **THEN** el texto que el usuario intentó guardar permanece visible y editable en el editor

### Requirement: Historial de cambios de solo lectura

La Memoria de usuario SHALL exponer un historial de sus propias versiones, de solo lectura, con al menos: número de versión, fecha, `origen` (∈ "vos" · "propuesta del agente (aceptada por vos)"), un resumen humano del cambio y el tamaño estimado en tokens.

#### Scenario: Cada guardado exitoso agrega una fila al historial

- **WHEN** se crea una versión nueva por edición manual o por propuesta aceptada
- **THEN** el historial de cambios muestra una fila nueva con versión, fecha, origen correspondiente, resumen del cambio y tamaño

#### Scenario: El historial no admite edición ni borrado de sus filas

- **WHEN** el usuario visualiza el historial de cambios
- **THEN** ninguna fila ofrece una acción de editar o eliminar esa versión específica

### Requirement: Concurrencia optimista en el guardado

Todo guardado (edición manual o aceptación de propuesta) SHALL enviar la versión base sobre la que se editó. Si la versión vigente en el servidor ya no coincide con la versión base al momento de guardar, el sistema SHALL rechazar el guardado con un error explícito y SHALL NUNCA fusionar los dos textos automáticamente.

#### Scenario: Edición concurrente detectada al guardar

- **WHEN** el usuario intenta guardar una edición basada en la versión 7, pero la versión vigente en el servidor ya es la versión 8 (guardada desde otra pestaña o sesión)
- **THEN** el guardado se rechaza con un error que indica la nueva versión vigente y ofrece ver la diferencia o recargar, sin aplicar ningún merge silencioso

### Requirement: Snapshot de memoria post-prefijo al crear la sesión

Al crear una sesión nueva, el sistema SHALL congelar la versión vigente de la Memoria de usuario del titular de la sesión en ese instante y SHALL adjuntarla a la sesión como snapshot inmutable. El snapshot SHALL insertarse en el contexto enviado al modelo inmediatamente después del system prompt estático y antes del historial de turnos, de forma que el prefijo 100% estático permanezca cacheable sin variación entre usuarios ni sesiones. Una vez creada la sesión, el snapshot SHALL NUNCA cambiar durante esa sesión, sin importar que la Memoria de usuario se edite o borre mientras la sesión permanece abierta.

#### Scenario: Sesión nueva toma la versión vigente al crearse

- **WHEN** se crea una sesión nueva y la Memoria de usuario del titular está en la versión 8
- **THEN** la sesión queda asociada al snapshot de la versión 8, insertado después del system prompt estático y antes del primer turno

#### Scenario: El snapshot no cambia a mitad de sesión

- **WHEN** el usuario edita o borra su Memoria de usuario mientras tiene una sesión abierta que ya capturó un snapshot anterior
- **THEN** los turnos siguientes de esa sesión ya abierta se siguen generando con el snapshot original, y solo una sesión creada después de la edición usa la versión nueva

#### Scenario: Memoria vacía no adjunta bloque de snapshot

- **WHEN** se crea una sesión nueva y la Memoria de usuario del titular está vacía
- **THEN** la sesión no adjunta ningún bloque de memoria al contexto del modelo

### Requirement: Memoria de usuario tratada como dato no confiable

El snapshot de memoria SHALL insertarse envuelto en un delimitador estructural (`<memoria_usuario id="…">…</memoria_usuario>`) declarado por el system prompt estático como dato provisto por el usuario, nunca como instrucción — mismo principio de *spotlighting* que `design/ANEXO-ATTACHMENTS.md` §4.3 aplica a los adjuntos. El contenido de memoria SHALL excluirse de la detección de cualquier marcador de control (por ejemplo el marcador de escalación de `b05-gateway-modelos`), de forma que un texto de memoria no pueda disparar por sí solo un efecto reservado a la salida genuina del modelo.

#### Scenario: El delimitador declara la memoria como dato, no instrucción

- **WHEN** se inserta el snapshot de memoria en el contexto de una sesión
- **THEN** queda envuelto en `<memoria_usuario id="…">…</memoria_usuario>` y el system prompt estático ya declara ese delimitador como dato-no-instrucción

#### Scenario: La memoria no puede disparar el marcador de escalación

- **WHEN** el texto de la Memoria de usuario contiene literalmente `<<<NEEDS_PRO>>>`
- **THEN** esa ocurrencia, por estar dentro de los delimitadores `<memoria_usuario>...</memoria_usuario>`, no se cuenta como disparador de escalación

### Requirement: Indicador de memoria usada en el chat

Cada respuesta generada dentro de una sesión cuyo snapshot de memoria no estaba vacío SHALL mostrar un indicador discreto de que la respuesta usó la Memoria de usuario, con un link a Mi memoria.

#### Scenario: Respuesta con snapshot no vacío muestra el indicador

- **WHEN** se genera una respuesta dentro de una sesión cuyo snapshot de memoria contiene texto
- **THEN** la respuesta muestra el indicador discreto de memoria usada con link a `/espacio/memoria`

#### Scenario: Sesión sin memoria no muestra el indicador

- **WHEN** se genera una respuesta dentro de una sesión cuyo snapshot de memoria está vacío (memoria vacía al momento de crear la sesión)
- **THEN** la respuesta no muestra ningún indicador de memoria usada

### Requirement: Ownership estricto sobre la Memoria de usuario

Ningún endpoint de Memoria de usuario SHALL aceptar un identificador de usuario ajeno provisto por el cliente: el usuario titular siempre SHALL derivarse de la sesión autenticada. Ningún rol —incluido Admin— SHALL poder leer ni editar la Memoria de usuario de otra persona desde este módulo.

#### Scenario: Intento de acceder a memoria ajena se deniega y se audita

- **WHEN** una petición autenticada intenta leer, editar o borrar la Memoria de usuario de un `user_id` distinto al de la sesión autenticada
- **THEN** la petición se deniega y queda registrada como intento denegado en el `AuditEvent` correspondiente

#### Scenario: Admin no ve memoria ajena desde este módulo

- **WHEN** un usuario con rol Admin abre Mi memoria
- **THEN** ve exclusivamente su propia Memoria de usuario, sin ninguna opción para consultar o editar la de otro usuario

### Requirement: Auditoría de alta, edición, borrado y uso

Toda alta (propuesta aceptada), edición manual y borrado de la Memoria de usuario SHALL registrarse como `AuditEvent` (contrato de `a03-core-gobernanza`). Todo uso —el hecho de que un snapshot no vacío se haya adjuntado a una sesión nueva— SHALL registrarse también como `AuditEvent` y SHALL quedar disponible como traza consumible por `b07-observabilidad`.

#### Scenario: Alta por propuesta aceptada genera AuditEvent

- **WHEN** el usuario acepta una propuesta de memoria y se crea la versión nueva
- **THEN** se emite un `AuditEvent` de tipo alta con el `user`, la versión creada y el origen "propuesta del agente"

#### Scenario: Edición manual y borrado generan AuditEvent

- **WHEN** el usuario guarda una edición manual o confirma "Borrar todo"
- **THEN** se emite un `AuditEvent` correspondiente (edición o borrado) con el `user` y la versión resultante

#### Scenario: El uso del snapshot en una sesión nueva genera AuditEvent y traza

- **WHEN** se crea una sesión nueva y se adjunta un snapshot de memoria no vacío
- **THEN** se emite un `AuditEvent` de tipo uso referenciando la sesión y la versión de memoria usada, disponible además como traza en `b07-observabilidad`

#### Scenario: El rechazo de una propuesta no genera alta

- **WHEN** el usuario rechaza una propuesta de memoria
- **THEN** no se emite ningún `AuditEvent` de alta (no hubo mutación de la Memoria de usuario)
