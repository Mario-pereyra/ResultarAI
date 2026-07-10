## ADDED Requirements

### Requirement: Renderizado de streaming con markdown, tablas y código

La UI del chat SHALL renderizar el texto en streaming como markdown con soporte de negritas, listas, tablas y bloques de código con highlighting por lenguaje (`design/VISTAS/02-chat.md` vista 05, assistant-ui), mostrando un cursor de bloque parpadeante al final del texto mientras el turno sigue generándose.

#### Scenario: Tabla y bloque de código se renderizan durante el streaming

- **WHEN** la respuesta en curso contiene una tabla markdown y un bloque de código con lenguaje declarado
- **THEN** la UI los renderiza como tabla y bloque de código con highlighting a medida que llegan, sin esperar a que el turno termine

#### Scenario: Cursor de streaming visible mientras el turno no cerró

- **WHEN** el turno del agente sigue en streaming
- **THEN** la UI muestra el cursor de bloque parpadeante al final del texto y el botón "Detener" en lugar del botón de enviar

### Requirement: Sanitización anti-XSS del markdown renderizado

La UI del chat SHALL sanitizar el HTML resultante del renderizado de markdown antes de insertarlo en el DOM, eliminando o neutralizando cualquier script, atributo de evento o URL ejecutable, tanto en el texto del agente como en el texto del usuario mostrado en su propio mensaje.

#### Scenario: Contenido con script embebido no se ejecuta

- **WHEN** el texto de una respuesta o de un mensaje de usuario contiene una secuencia que parece HTML/script ejecutable
- **THEN** la UI la renderiza como texto o markdown inerte, sin ejecutar ningún script ni disparar navegación no solicitada

### Requirement: Indicador de actividad durante el streaming

Mientras el turno está en curso, la UI SHALL mostrar una línea de actividad plegada indicando qué está haciendo el agente (por ejemplo, "consultando…") sin exponer detalle técnico a la capa Funcional, y SHALL habilitar el auto-scroll solo si el usuario está al final de la conversación, ofreciendo un botón flotante "Nuevos mensajes" si el usuario se desplazó hacia arriba.

#### Scenario: Línea de actividad visible antes de la respuesta

- **WHEN** el agente está ejecutando una tool de lectura antes de responder
- **THEN** la UI muestra una línea de actividad plegada con un spinner, sin parámetros técnicos para el rol Funcional

#### Scenario: Botón de nuevos mensajes cuando el usuario scrolleó hacia arriba

- **WHEN** llegan fragmentos nuevos de streaming mientras el usuario no está al final de la columna de mensajes
- **THEN** la UI no fuerza el scroll automático y muestra un botón flotante para saltar a los mensajes nuevos

### Requirement: Tool calls colapsadas y expandibles por capa de rol

La UI SHALL mostrar cada tool call de lectura como una línea de actividad plegada y expandible conforme al contrato `tool-call-visibility` de `c09-mcp-tools`, mostrando para el rol Funcional una descripción en lenguaje simple de qué se consultó y qué se obtuvo (truncado), y para Técnico/Admin además los parámetros completos de la invocación y la latencia.

#### Scenario: Funcional ve la tool call en lenguaje simple

- **WHEN** un usuario con rol Funcional expande una tool call de lectura ya ejecutada
- **THEN** la UI muestra una descripción sin jerga técnica de qué se consultó y el resultado truncado, sin parámetros técnicos

#### Scenario: Técnico/Admin ven los parámetros completos

- **WHEN** un usuario con rol Técnico o Admin expande la misma tool call
- **THEN** la UI muestra además los parámetros completos de la invocación y su latencia

### Requirement: Capa de telemetría por turno para Técnico/Admin

Para los roles Técnico y Admin, la UI SHALL agregar a cada turno del agente su costo (`turn.cost_usd`), perfil de modelo usado, latencia y chips de cache hit/miss/write, además de un taxímetro acumulado de la sesión en el header (`design/VISTAS/02-chat.md` vista 06); esta capa SHALL no renderizarse en absoluto para el rol Funcional. Para el rol Admin, cada turno SHALL incluir además un enlace "ver traza" hacia la traza de observabilidad del turno.

#### Scenario: Técnico ve costo y chips de cache sin enlace de traza

- **WHEN** un usuario con rol Técnico visualiza un turno completado
- **THEN** la UI muestra costo, perfil, latencia y chips de cache de ese turno, y no muestra ningún enlace "ver traza"

#### Scenario: Admin ve además el enlace a la traza

- **WHEN** un usuario con rol Admin visualiza el mismo turno
- **THEN** la UI muestra todo lo anterior más el enlace "ver traza" que abre la traza del turno en la consola

#### Scenario: Funcional no ve ningún dato de telemetría

- **WHEN** un usuario con rol Funcional visualiza el mismo turno
- **THEN** la UI no renderiza costo, perfil, latencia, chips de cache ni taxímetro para ese turno

### Requirement: Etiqueta "modelo alterno" visible para todos los roles

Cuando un turno se generó con un perfil de modelo distinto al primario de la cascada del agente (metadato de `model-profiles` de `b05-gateway-modelos`), la UI SHALL mostrar una etiqueta discreta "modelo alterno" junto al turno para todos los roles. La capa Funcional SHALL mostrar la etiqueta con una explicación en lenguaje simple sin el nombre del perfil; Técnico/Admin SHALL ver además el nombre del perfil efectivamente usado.

#### Scenario: Todos los roles ven la etiqueta cuando hubo fallback

- **WHEN** un turno fue respondido por un perfil de fallback distinto al primario
- **THEN** la UI muestra la etiqueta "modelo alterno" en ese turno para Funcional, Técnico y Admin

#### Scenario: Solo Técnico/Admin ven el nombre del perfil

- **WHEN** un usuario Técnico o Admin pasa el cursor o expande la etiqueta "modelo alterno"
- **THEN** la UI muestra el nombre del perfil de modelo efectivamente usado, dato que la capa Funcional nunca muestra

### Requirement: Tarjeta de escalación manual a Pro

Al recibir un evento de escalación para el turno en curso, la UI SHALL mostrar una tarjeta embebida en el flujo de mensajes (no modal) con la razón de la escalación, el perfil de destino, y exactamente dos acciones: "Continuar con Pro" y "Seguir con Flash". La tarjeta SHALL NUNCA disparar la escalación sin que el usuario pulse "Continuar con Pro", y SHALL no renderizarse en absoluto si el agente tiene la escalación deshabilitada.

#### Scenario: Confirmar escalación navega a la sesión/rama nueva

- **WHEN** el usuario pulsa "Continuar con Pro" en la tarjeta de escalación
- **THEN** la UI invoca la creación de la sesión/rama de escalación y navega a ella, dejando en la sesión original una nota-enlace de vuelta

#### Scenario: Descartar la escalación no interrumpe la conversación

- **WHEN** el usuario pulsa "Seguir con Flash"
- **THEN** la tarjeta colapsa a una línea atenuada y la conversación continúa en el perfil original sin crear ninguna sesión/rama nueva

#### Scenario: Escalación deshabilitada no muestra tarjeta

- **WHEN** el agente activo tiene la escalación deshabilitada en su Agent Manifest
- **THEN** la UI nunca renderiza la tarjeta de escalación aunque el modelo hubiera intentado emitir el marcador

### Requirement: Selector de versiones para mensajes editados y respuestas regeneradas

Cuando un mensaje de usuario o una respuesta del agente tiene más de una versión, la UI SHALL mostrar un selector "versión N/M" junto al mensaje ramificado que permite alternar entre versiones, y al cambiar de versión SHALL re-renderizar todos los mensajes posteriores de la rama seleccionada conservando intactos los de la rama no seleccionada.

#### Scenario: Alternar versión conserva ambas ramas intactas

- **WHEN** el usuario alterna del selector "1/2" al "2/2" en un mensaje con dos versiones
- **THEN** la UI muestra los mensajes posteriores correspondientes a la versión 2 sin alterar ni perder los mensajes de la versión 1

#### Scenario: Editar un mensaje muestra el selector por primera vez

- **WHEN** el usuario edita un mensaje que hasta entonces no tenía versiones alternativas
- **THEN** tras crearse la rama, la UI muestra el selector "1/2" en ese mensaje

### Requirement: Aviso suave de regeneración costosa al editar lejos

Cuando el usuario edita un mensaje que tiene tres o más mensajes posteriores en su rama, la UI SHALL mostrar un aviso no bloqueante indicando cuántos mensajes se reprocesarán antes de confirmar la creación de la rama; el aviso SHALL solo informar, sin impedir la operación.

#### Scenario: Aviso aparece al editar con reproceso relevante

- **WHEN** el usuario edita un mensaje que tiene seis mensajes posteriores en su rama
- **THEN** la UI muestra el aviso "reprocesa 6 mensajes" antes de confirmar la edición, sin bloquear el botón de confirmar

#### Scenario: Sin aviso al editar el último mensaje

- **WHEN** el usuario edita el último mensaje de la conversación (sin mensajes posteriores)
- **THEN** la UI no muestra el aviso de regeneración costosa

### Requirement: Tarjeta de error accionable para GATEWAY_OFFLINE

Cuando el servicio de modelo no está disponible, la UI SHALL mostrar dentro del flujo de mensajes una tarjeta de error con el código `GATEWAY_OFFLINE`, una redacción del "qué pasó/por qué" adaptada al rol (código visible para Técnico/Admin, en segundo plano para Funcional), un countdown de reintento automático y un botón "Reintentar ahora"; el mensaje original del usuario SHALL permanecer visible en el hilo y ser reenviable sin duplicarse.

#### Scenario: Reintento automático con countdown

- **WHEN** ocurre un error `GATEWAY_OFFLINE` al procesar un turno
- **THEN** la UI muestra la tarjeta con countdown decreciente y reintenta automáticamente al llegar a cero, sin perder el mensaje original del usuario

#### Scenario: Redacción distinta por rol

- **WHEN** el mismo error `GATEWAY_OFFLINE` se muestra a un usuario Funcional y a uno Técnico
- **THEN** el Funcional ve una redacción sin jerga con el código en segundo plano ("código para soporte: …"), y el Técnico ve el código mono visible arriba de la tarjeta

### Requirement: Tarjeta de error accionable para QUOTA (estado UI)

Cuando el backend indica que la sesión alcanzó su límite de cuota, la UI SHALL mostrar dentro del flujo de mensajes una tarjeta de error con el código `QUOTA`, deshabilitar el composer con el motivo inline, y ofrecer un botón "Solicitar liberación". Este requirement cubre únicamente el estado visual y la deshabilitación del composer; la evaluación de presupuestos y el flujo de solicitud/aprobación de la liberación los implementa `d16-cuotas-liberaciones`.

#### Scenario: Composer deshabilitado con motivo visible

- **WHEN** el backend señala que la sesión alcanzó el límite de cuota
- **THEN** la UI muestra la tarjeta `QUOTA` dentro del flujo de mensajes y deshabilita el composer indicando el motivo

#### Scenario: Botón de solicitar liberación presente sin enforcement propio

- **WHEN** la tarjeta `QUOTA` está visible
- **THEN** la UI ofrece el botón "Solicitar liberación", cuyo flujo de creación y resolución de la solicitud no forma parte de este change

### Requirement: Feedback 👍/👎 por respuesta con comentario opcional

Cada respuesta del agente ya completada SHALL mostrar acciones de feedback 👍/👎; al seleccionar una, la UI SHALL registrar el voto ligado al turno y ofrecer un comentario opcional antes de confirmarlo, sin bloquear la conversación si el usuario omite el comentario.

#### Scenario: Votar sin comentario registra el feedback igual

- **WHEN** el usuario pulsa 👍 y elige "Omitir" en el popover de comentario
- **THEN** el sistema registra el voto ligado al turno sin comentario

#### Scenario: Cambiar el voto reemplaza el anterior

- **WHEN** el usuario había votado 👍 en una respuesta y pulsa 👎 en la misma respuesta
- **THEN** el sistema reemplaza el voto anterior por el nuevo y vuelve a ofrecer el popover de comentario

### Requirement: Ejemplos clicables precargan el composer

En una sesión nueva sin mensajes, la UI SHALL mostrar los prompts de ejemplo configurados para el agente (`agent.starter_prompts`) como sugerencias clicables; al hacer click, SHALL insertar el texto en el composer y darle foco sin enviarlo automáticamente.

#### Scenario: Click en un ejemplo precarga sin enviar

- **WHEN** el usuario hace click en una sugerencia de inicio
- **THEN** la UI inserta el texto de esa sugerencia en el composer y le da foco, sin enviar el turno

### Requirement: Indicador discreto de compaction

Cuando el runtime informa que la sesión fue compactada (`context-compaction` de `b06-runtime-grafos`), la UI SHALL mostrar un indicador discreto en la conversación señalando que la sesión fue compactada, sin bloquear ni interrumpir el flujo, y SHALL permitir que el usuario reenvíe contenido compactado como un mensaje nuevo si lo necesita.

#### Scenario: Indicador aparece tras la compaction

- **WHEN** el runtime compacta el contexto de la sesión en la frontera de un turno
- **THEN** la UI muestra un indicador discreto de compaction en ese punto de la conversación

### Requirement: Chat funcional en dispositivos móviles

La UI del chat (columna de mensajes, composer, selector de ramas, tarjetas de error, tarjeta de escalación e historial) SHALL ser completamente operable en viewport móvil: composer fijo con área segura, acciones de turno con objetivo táctil de al menos 44 px, y el menú de sesión con la información que en desktop vive en el header.

#### Scenario: Selector de ramas operable en móvil

- **WHEN** un usuario en viewport móvil interactúa con el selector "versión N/M" de un mensaje ramificado
- **THEN** las flechas del selector son operables con un objetivo táctil de al menos 44 px
