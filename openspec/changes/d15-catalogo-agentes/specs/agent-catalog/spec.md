# agent-catalog — Delta Spec (d15-catalogo-agentes)

## ADDED Requirements

### Requirement: Grilla de agentes filtrada por visibilidad

El sistema SHALL listar en la grilla del catálogo (`design/VISTAS/03-catalogo.md`, vista 13) únicamente los agentes cuyo `AgentManifest` tiene `status: active` en el Agent Registry (`a02-core-manifiestos`) y que el contrato de lectura de `agent-visibility` marca como visibles para el rol del usuario autenticado.

#### Scenario: Un agente deprecado en el manifiesto nunca aparece en la grilla

- **WHEN** un `AgentManifest` tiene `status: deprecated`
- **THEN** ningún rol lo ve en la grilla del catálogo, aunque exista en el Agent Registry

#### Scenario: Un Funcional ve exactamente los agentes que su rol permite

- **WHEN** un Funcional abre el catálogo
- **THEN** la grilla contiene solo los agentes `active` marcados visibles para Funcional por `agent-visibility`, y ningún otro

### Requirement: Anatomía de la card por capa de rol

Cada card de la grilla SHALL mostrar, para todos los roles, el tipo de agente, el nombre, la descripción truncada a dos líneas y hasta 3 casos de uso. La **capa técnica** de la card (versión activa del `AgentManifest`, costo estimado por sesión y score de evals) SHALL renderizarse únicamente para Técnico y Admin; para Funcional esa capa no SHALL existir en el DOM, no solo estar oculta visualmente.

#### Scenario: Card de Funcional sin capa técnica

- **WHEN** un Funcional visualiza la grilla
- **THEN** ninguna card incluye versión activa, costo estimado ni score de evals, ni siquiera en markup oculto

#### Scenario: Card de Técnico con capa técnica

- **WHEN** un Técnico visualiza la grilla
- **THEN** cada card incluye la versión activa del `AgentManifest`, el costo estimado por sesión y el score de evals (o su placeholder, ver Requirement "Score de evals en modo placeholder")

### Requirement: Búsqueda por texto en el catálogo

El sistema SHALL permitir filtrar la grilla por una búsqueda de texto que compare contra el nombre, la descripción y los casos de uso del agente, aplicada en cliente con un debounce y sin recargar la página; el contador de resultados SHALL actualizarse junto con la grilla y anunciarse por `aria-live="polite"`.

#### Scenario: Búsqueda sin resultados

- **WHEN** una búsqueda no coincide con ningún agente visible para el rol
- **THEN** la grilla muestra el estado vacío de búsqueda con la opción de limpiar filtros

#### Scenario: Búsqueda vacía restaura la grilla completa

- **WHEN** el usuario borra el texto de búsqueda
- **THEN** la grilla vuelve a mostrar todos los agentes visibles para su rol

### Requirement: Orden fijo del catálogo

El sistema SHALL ordenar la grilla de forma fija por instancia: agentes disponibles primero, agentes no disponibles por kill-switch al final (cuando la configuración de instancia elige mostrarlos en vez de ocultarlos); dentro de cada grupo, orden alfabético por nombre. El catálogo no SHALL ofrecer un ordenamiento personalizado por usuario en este change.

#### Scenario: Un agente no disponible aparece al final

- **WHEN** un agente está apagado por kill-switch y la instancia está configurada para mostrar agentes no disponibles
- **THEN** ese agente aparece después de todos los agentes disponibles, en su posición alfabética dentro del grupo de no disponibles

### Requirement: Estados de carga, vacío y error de la grilla

La grilla SHALL mostrar un estado de carga con cards skeleton cuando la respuesta tarda más de 300 ms, un estado vacío distinto para "el rol no tiene agentes asignados" (sin CTA, remite a hablar con el Admin) y para "búsqueda sin resultados" (con botón limpiar filtros), y un `error-card` accionable con código `CATALOG_OFFLINE` y botón "Reintentar" ante un fallo de carga, conforme a `design/VISTAS/03-catalogo.md` §Estados.

#### Scenario: Rol sin agentes asignados

- **WHEN** un usuario cuyo rol no tiene ningún agente visible abre el catálogo
- **THEN** el sistema muestra el estado vacío "Tu rol todavía no tiene agentes asignados" sin ningún botón de acción

#### Scenario: Error de carga es accionable

- **WHEN** la carga del catálogo falla
- **THEN** el sistema muestra un `error-card` con el código `CATALOG_OFFLINE`, una explicación en lenguaje simple y un botón "Reintentar"

#### Scenario: Telemetría degradada no bloquea el catálogo

- **WHEN** la fuente de costo estimado (`b07-observabilidad`) no responde
- **THEN** la capa técnica de las cards muestra el costo con el marcador `~` y un tooltip de "costo estimado, telemetría diferida", sin impedir el resto de la carga del catálogo

### Requirement: Selector "Ver como rol" (solo Admin)

El sistema SHALL ofrecer, únicamente a Admin, un selector que previsualiza la grilla exactamente como la vería otro rol, incluida la ausencia de la capa técnica si se elige Funcional. Esta previsualización SHALL ser de solo lectura: no SHALL cambiar permisos reales ni registrar ninguna acción en el audit log.

#### Scenario: Admin previsualiza como Funcional

- **WHEN** un Admin selecciona "Ver como Funcional"
- **THEN** la grilla se re-renderiza como la vería un Funcional (agentes visibles y capas), sin alterar la sesión real del Admin ni la matriz de visibilidad

### Requirement: Estado de kill-switch por agente

El sistema SHALL consultar, por agente, una bandera de habilitación en tiempo de ejecución (el kill-switch). La administración de esa bandera —apagar o encender en menos de 1 minuto sin despliegue, con registro auditado— es responsabilidad de `d20-gobernanza-plataforma`; este change solo consume su estado. Mientras `d20` no exista, el sistema SHALL tratar a todo agente como habilitado por default. Según una configuración de instancia, un agente con la bandera apagada SHALL, alternativamente: (a) aparecer en la grilla y en la ficha con el CTA "Abrir chat" deshabilitado y el mensaje "No disponible temporalmente"; o (b) quedar excluido de la grilla y responder el estado "no disponible" (idéntico al de la Requirement "No revelar existencia a un rol sin acceso" de `agent-visibility`) ante un deep link a su ficha.

#### Scenario: Agente apagado con configuración "mostrar deshabilitado"

- **WHEN** el kill-switch de un agente está apagado y la instancia está configurada para mostrar agentes no disponibles
- **THEN** el agente aparece en la grilla con el CTA "Abrir chat" deshabilitado y el texto "No disponible temporalmente"

#### Scenario: Agente apagado con configuración "ocultar"

- **WHEN** el kill-switch de un agente está apagado y la instancia está configurada para ocultar agentes no disponibles
- **THEN** el agente no aparece en la grilla y un deep link a su ficha devuelve el mismo estado "no disponible" que un agente inexistente

#### Scenario: Sin bandera de kill-switch configurada, el agente está habilitado

- **WHEN** `d20-gobernanza-plataforma` todavía no existe y no hay ninguna bandera de kill-switch registrada para un agente
- **THEN** el sistema lo trata como habilitado y el CTA "Abrir chat" está activo

### Requirement: Ficha de agente — capa común

La ficha de agente (`design/VISTAS/03-catalogo.md`, vista 14) SHALL mostrar, para los tres roles, la cabecera (tipo, nombre, estado, roles objetivo), la descripción completa, los límites ("qué NO hace"), los casos de uso ideales completos, el owner y 3 ejemplos de prompt clicables. Este contenido SHALL provenir de un read-model de catálogo propio de este change (no de un campo nuevo en el `AgentManifest` de `a02-core-manifiestos`), sembrado como dato de fábrica para `default_chat` y el agente de ejemplo.

#### Scenario: Capa común idéntica para los tres roles

- **WHEN** Admin, Técnico y Funcional abren la misma ficha de agente
- **THEN** los tres ven la misma cabecera, descripción, límites, casos de uso y ejemplos, en lenguaje sin jerga técnica

#### Scenario: Ficha de fábrica completa

- **WHEN** se consulta la ficha de `default_chat` o del agente de ejemplo en una instancia recién desplegada
- **THEN** la capa común está completa (descripción, límites, casos de uso, owner y 3 ejemplos), sin campos vacíos

### Requirement: Ejemplos clicables prellenan el composer sin enviar

Cada uno de los 3 ejemplos de prompt de la ficha SHALL, al hacer click, abrir una sesión nueva con ese agente (delegando en `d13-chat-conversacion`) y dejar el texto del ejemplo prellenado en el composer sin enviarlo; el usuario SHALL revisar y enviar explícitamente.

#### Scenario: Click en un ejemplo abre sesión con el texto prellenado

- **WHEN** un usuario hace click en uno de los 3 ejemplos de la ficha de un agente disponible
- **THEN** se abre una sesión nueva con ese agente y el composer muestra el texto del ejemplo sin haberlo enviado

#### Scenario: Ejemplos deshabilitados si el agente no está disponible

- **WHEN** el agente de la ficha está apagado por kill-switch y configurado para mostrarse deshabilitado
- **THEN** los 3 botones de ejemplo se muestran deshabilitados mostrando igual su texto, sin poder abrir sesión

### Requirement: Ficha técnica — solo Técnico y Admin

La ficha técnica SHALL renderizarse únicamente para Técnico y Admin (para Funcional no SHALL existir en el DOM) y SHALL mostrar, como mínimo: el perfil de modelo asignado al agente (`b05-gateway-modelos`), si la escalación manual a Pro está habilitada para ese agente y a qué perfil escala, la política HITL del agente (si aplica), la política de datos del agente, el costo estimado por sesión con desglose (input cacheado, input nuevo, output, porcentaje de ahorro por cache) agregado desde las trazas del agente (`b07-observabilidad`) sobre una ventana configurable por instancia, y la tabla de Tools que usa (nombre, clasificación lectura/escritura, scope) derivada de sus Skills habilitadas (`a02-core-manifiestos`/`c09-mcp-tools`).

#### Scenario: Ficha técnica invisible para Funcional

- **WHEN** un Funcional abre la ficha de un agente
- **THEN** el bloque de ficha técnica no existe en el DOM, ni siquiera colapsado

#### Scenario: Costo estimado sin datos históricos

- **WHEN** un agente no tiene trazas históricas todavía (agente nuevo)
- **THEN** el costo estimado se muestra como "sin datos todavía" en vez de un valor o de un error

#### Scenario: Tabla de tools marca las de escritura

- **WHEN** un agente declara al menos una Tool clasificada `escritura`
- **THEN** la fila correspondiente en la tabla de Tools la marca visualmente distinta de las de lectura, con una nota que remite a la política HITL

### Requirement: Versión activa mostrada como equivalente disponible hoy

Mientras no exista `d20-gobernanza-plataforma` (Registro de Prompts inmutable con versiones publicadas), la ficha técnica SHALL mostrar la `version` semver del `AgentManifest` activo como versión equivalente, con una etiqueta que indique que este campo se reemplaza por el Registro de Prompts cuando ese change esté disponible.

#### Scenario: Versión mostrada antes de que exista el Registro de Prompts

- **WHEN** se consulta la ficha técnica de un agente y `d20-gobernanza-plataforma` no está archivado
- **THEN** la tab Prompt muestra la `version` del `AgentManifest` activo con la etiqueta que aclara que es un valor transitorio

### Requirement: Score de evals en modo placeholder

Mientras `e25-evals-gates` no esté archivado, la ficha técnica SHALL mostrar "sin evals aún" en el lugar del score de evals, sin bloquear ninguna otra parte de la ficha. Cuando `e25-evals-gates` exponga un score real para el agente, la ficha técnica SHALL mostrarlo en su lugar.

#### Scenario: Ficha técnica sin evals antes de e25

- **WHEN** se consulta la ficha técnica de cualquier agente y `e25-evals-gates` no está archivado
- **THEN** la tab Evals muestra "sin evals aún" en vez de un score o de un error, y el resto de la ficha técnica se muestra con normalidad

### Requirement: Iniciar conversación desde el catálogo

El botón "Abrir chat" de la card o de la ficha SHALL crear una sesión nueva con el agente elegido invocando el endpoint de creación de sesión de `d13-chat-conversacion`, y navegar al chat de esa sesión. Este change no SHALL reimplementar la lógica de creación de sesión.

#### Scenario: Abrir chat crea una sesión nueva

- **WHEN** un usuario hace click en "Abrir chat" sobre un agente disponible y visible para su rol
- **THEN** se crea una sesión nueva con ese agente vía el endpoint de `d13-chat-conversacion` y el usuario es navegado al chat de esa sesión

#### Scenario: Abrir chat con cuota al 100% no se intercepta en el catálogo

- **WHEN** un usuario con la cuota al 100% hace click en "Abrir chat"
- **THEN** la sesión se crea igual y el estado de cuota se muestra dentro del chat (`d13-chat-conversacion`), nunca como un bloqueo en el catálogo

### Requirement: Ficha — estados de no disponible y error

Ante un deep link a un agente que no existe, que no es visible para el rol, o que está apagado por kill-switch con la instancia configurada para ocultar, la ficha SHALL mostrar el mismo estado "Este agente no está disponible" con un botón para volver al catálogo, sin distinguir la causa. Ante un fallo de carga, la ficha SHALL mostrar el mismo patrón de `error-card` con "Reintentar" que la grilla.

#### Scenario: Ficha de agente inexistente o sin acceso

- **WHEN** un usuario navega a la ficha de un agente inexistente o fuera de la visibilidad de su rol
- **THEN** ve el estado "Este agente no está disponible" con un botón "Volver al catálogo", sin ningún detalle que revele la causa

### Requirement: Accesibilidad AA y soporte móvil

La grilla y la ficha SHALL cumplir WCAG 2.1 AA: contraste suficiente en ambos temas, foco visible, navegación completa por teclado (incluida la navegación por pestañas de la ficha técnica con flechas y `aria-selected`) y semántica ARIA en los componentes interactivos. En viewport móvil, la grilla SHALL colapsar a una columna con CTA a ancho completo y objetivo táctil de al menos 44 px, y la ficha SHALL ofrecer lectura completa en columna única con las tablas de la ficha técnica desplazables horizontalmente.

#### Scenario: Navegación de la ficha técnica por teclado

- **WHEN** un usuario Técnico navega las pestañas de la ficha técnica (Resumen/Tools/Prompt/Evals) usando el teclado
- **THEN** puede moverse entre pestañas con las flechas, y el panel activo se anuncia mediante los atributos ARIA correspondientes

#### Scenario: Grilla utilizable en móvil

- **WHEN** el catálogo se abre en un viewport de 380 px
- **THEN** la grilla se muestra en una sola columna con cada CTA a ancho completo y con al menos 44 px de alto táctil
