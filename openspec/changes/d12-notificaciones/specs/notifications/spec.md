# notifications — Delta Spec (d12-notificaciones)

## ADDED Requirements

### Requirement: Modelo de notificación

El sistema SHALL persistir cada notificación con: identificador único, `type` (uno de los tipos del registro), `recipient` (usuario destinatario único), `payload` estructurado propio del tipo, estado `read`/`unread`, `deep_link` al origen (sesión, tarjeta HITL o solicitud) y `created_at`.

#### Scenario: Notificación creada con los campos mínimos

- **WHEN** un caso de uso emite una notificación con `type`, `recipient`, `payload` y `deep_link` válidos
- **THEN** el sistema la persiste con estado inicial `unread` y `created_at` asignado por el sistema, y queda disponible para el destinatario

### Requirement: Contrato genérico de emisión

El sistema SHALL exponer un contrato único de emisión (`type`, `recipient`, `payload`, `deep_link`) que cualquier caso de uso de `app/` puede invocar para crear una notificación, sin conocer cómo se lista, se renderiza ni se entrega.

#### Scenario: Emisión desde un caso de uso externo al de notificaciones

- **WHEN** un caso de uso de otro bounded context (por ejemplo, liberación de cuota) invoca el contrato de emisión con datos válidos de un tipo registrado
- **THEN** la notificación se crea sin que ese caso de uso dependa de la implementación interna del listado o del panel

#### Scenario: Emisión rechazada para un tipo no registrado

- **WHEN** se invoca el contrato de emisión con un `type` que no existe en el registro de tipos
- **THEN** el sistema rechaza la emisión con un error explícito y no crea la notificación

### Requirement: Registro de tipos de notificación

El sistema SHALL mantener un registro de tipos de notificación donde cada tipo declara su `payload` esperado y su regla de resolución de destinatario, y está marcado como **implementado** (este change lo emite de punta a punta) o **registrado** (el tipo y su contrato existen; el change que lo emite llega después). El registro SHALL incluir, como mínimo: `quota_release_requested` (implementado, destinatario = Admin del tenant), `quota_release_resolved` (implementado, destinatario = solicitante), `hitl_approval_pending` (registrado, lo emite `d17-hitl-aprobaciones`), `hitl_card_expired` (registrado, lo emite `d17-hitl-aprobaciones`), `workflow_finished` (registrado, lo emite `e22-workflows-deterministas`) y `catalog_news` (registrado, lo emite `d15-catalogo-agentes`).

#### Scenario: Consulta del registro incluye tipos registrados sin emisor propio

- **WHEN** se consulta el registro de tipos de notificación
- **THEN** los cuatro tipos registrados (`hitl_approval_pending`, `hitl_card_expired`, `workflow_finished`, `catalog_news`) aparecen con su `payload` y regla de destinatario documentados, aunque ningún caso de uso de este change los emita todavía

#### Scenario: Tipo implementado disponible para emisión inmediata

- **WHEN** se consulta el registro de tipos de notificación
- **THEN** `quota_release_requested` y `quota_release_resolved` aparecen marcados como implementados y pueden emitirse a través del contrato genérico

### Requirement: Emisión de extremo a extremo — solicitud de liberación de cuota

Cuando un usuario dispara una solicitud de liberación de cuota bloqueada, el sistema SHALL emitir una notificación `quota_release_requested` para cada Admin del tenant, con `payload` que incluye el usuario solicitante, la cuota afectada y el consumo actual, y `deep_link` a la pantalla de Cuotas de administración.

#### Scenario: Solicitud de liberación notifica a todos los Admin del tenant

- **WHEN** se dispara una solicitud de liberación de cuota para un usuario del tenant T
- **THEN** cada usuario con rol Admin de T recibe una notificación `quota_release_requested` propia, con el solicitante, la cuota afectada y el consumo actual en el `payload`

### Requirement: Emisión de extremo a extremo — resultado de liberación de cuota

Cuando la solicitud de liberación de cuota es resuelta (concedida o denegada), el sistema SHALL emitir una notificación `quota_release_resolved` para el usuario solicitante original, con la decisión en el `payload` y `deep_link` a su consumo (Mi espacio).

#### Scenario: El solicitante es notificado de la decisión

- **WHEN** un Admin resuelve una solicitud de liberación de cuota (concede o deniega)
- **THEN** el solicitante original recibe una notificación `quota_release_resolved` con la decisión tomada; el registro de la decisión en el audit log es responsabilidad del caso de uso emisor, no de este change

### Requirement: Filtrado por ownership

El sistema SHALL devolver, en cualquier operación de lectura o conteo, únicamente las notificaciones cuyo `recipient` sea el usuario autenticado que realiza la petición. Ningún endpoint SHALL exponer notificaciones de otro usuario, incluida la resolución por identificador directo.

#### Scenario: Un usuario no ve las notificaciones de otro

- **WHEN** el usuario A tiene notificaciones propias y el usuario B (con al menos una notificación pendiente) lista sus notificaciones
- **THEN** la respuesta contiene únicamente notificaciones con `recipient = B`; ninguna notificación de A aparece, y el contador de no-leídas de B tampoco las incluye

#### Scenario: Acceso directo a una notificación ajena es rechazado

- **WHEN** el usuario B solicita por identificador una notificación cuyo `recipient` es el usuario A
- **THEN** el sistema responde como si no existiera (sin filtrar su existencia ni su contenido) en lugar de devolver el recurso

### Requirement: Filtrado por rol

El sistema SHALL restringir la creación y, en consecuencia, la visibilidad de notificaciones cuyo tipo esté reservado a un rol (por ejemplo, los tipos con destinatario Admin) a los usuarios que tengan ese rol al momento de la emisión.

#### Scenario: Un usuario sin rol Admin nunca recibe una notificación reservada a Admin

- **WHEN** se emite una notificación `quota_release_requested` (destinatario = Admin) sobre un tenant
- **THEN** solo los usuarios con rol Admin de ese tenant reciben la notificación; ningún usuario Técnico o Funcional la recibe

### Requirement: Listado paginado y filtrado por estado de lectura

El sistema SHALL exponer un endpoint de listado de notificaciones propias con paginación clásica y filtro opcional por estado (`unread`, `read`, todas), ordenado por fecha de creación descendente.

#### Scenario: Listar solo no leídas

- **WHEN** el usuario solicita su listado con filtro `unread`
- **THEN** el sistema devuelve solo sus notificaciones con estado `unread`, ordenadas de más reciente a más antigua

#### Scenario: Paginación no devuelve todo el historial de una vez

- **WHEN** el usuario tiene más notificaciones que el tamaño de página configurado y solicita la página 2
- **THEN** el sistema devuelve el segundo bloque sin repetir ni omitir elementos respecto de la página 1, con metadatos de paginación (total, página actual, hay-siguiente)

### Requirement: Conteo de no leídas

El sistema SHALL exponer un endpoint que devuelve la cantidad de notificaciones `unread` del usuario autenticado, para alimentar el indicador de la campana.

#### Scenario: El contador refleja el estado real de no-leídas

- **WHEN** el usuario tiene 3 notificaciones `unread` y marca una como leída
- **THEN** una consulta posterior al endpoint de conteo devuelve 2

### Requirement: Marcar como leída, individual y masiva

El sistema SHALL permitir marcar una notificación propia como leída de forma individual, y marcar todas las notificaciones visibles del usuario como leídas en una sola operación.

#### Scenario: Marcar una notificación como leída

- **WHEN** el usuario marca como leída una notificación propia en estado `unread`
- **THEN** su estado pasa a `read` y deja de contar en el indicador de no-leídas

#### Scenario: Marcar todas las notificaciones como leídas

- **WHEN** el usuario invoca "marcar todas leídas" teniendo varias notificaciones `unread`
- **THEN** todas sus notificaciones visibles pasan a `read` y el contador de no-leídas queda en cero

### Requirement: Ir al origen marca la notificación como leída

Al navegar desde una notificación hacia su `deep_link`, el sistema SHALL marcarla como leída como efecto de esa navegación. Si el objeto referenciado por el `deep_link` ya no existe o cambió de estado, el sistema SHALL mostrar el estado final del origen en lugar de un error genérico.

#### Scenario: Click en una notificación navega y marca leído

- **WHEN** el usuario hace click en una notificación `unread` (o en su acción "Ver")
- **THEN** el sistema navega al recurso indicado por `deep_link` y la notificación pasa a `read`

#### Scenario: El origen ya no existe en su estado original

- **WHEN** el usuario navega desde una notificación cuyo origen (por ejemplo, una solicitud de liberación) ya fue resuelto o expiró
- **THEN** el sistema muestra el estado final del origen, nunca un error de "no encontrado"

### Requirement: Campana con indicador de no-leídas en el shell

La UI SHALL mostrar una campana (`.notif-bell`) en la topbar del shell (`d10-design-system-shell`) con un indicador del conteo de no-leídas; el indicador SHALL ocultarse cuando el conteo es cero sin desplazar el layout.

#### Scenario: El indicador se oculta en cero

- **WHEN** el usuario no tiene notificaciones `unread`
- **THEN** la campana se muestra sin indicador numérico, reservando el espacio para evitar saltos de layout cuando el conteo cambie

#### Scenario: Llegada en vivo actualiza el contador sin robar foco

- **WHEN** llega una notificación nueva mientras el usuario tiene foco en otra parte de la UI
- **THEN** el indicador de la campana se actualiza y se anuncia mediante una región `aria-live` sin mover el foco del usuario

### Requirement: Panel de notificaciones agrupado

La UI SHALL renderizar, al abrir la campana, un panel (dropdown en escritorio, sheet a pantalla completa en móvil según `design/VISTAS/01-acceso-shell.md` Vista 4) con las notificaciones agrupadas por familia de tipo mediante encabezados de grupo (kicker); los grupos sin elementos no SHALL renderizarse, y un estado vacío SHALL mostrarse cuando el usuario no tiene notificaciones.

#### Scenario: Los grupos sin elementos no aparecen

- **WHEN** el usuario no tiene notificaciones de una familia de tipos (por ejemplo, ninguna de cuotas)
- **THEN** el encabezado de ese grupo no se renderiza en el panel

#### Scenario: Estado vacío cuando no hay notificaciones

- **WHEN** el usuario no tiene ninguna notificación
- **THEN** el panel muestra el estado vacío "Estás al día" con el texto de ayuda definido en la Vista 4, sin listar grupos

#### Scenario: En móvil el panel ocupa toda la pantalla

- **WHEN** el usuario abre la campana en un viewport menor a 768 px
- **THEN** el panel se presenta como sheet a pantalla completa con encabezado fijo y botón de cierre, en vez de dropdown anclado

### Requirement: Ver todas — listado completo paginado

La UI SHALL ofrecer, desde el panel, una acción "Ver todas" que navega a una vista de listado completo y paginado de las notificaciones propias del usuario, más allá del máximo de elementos mostrados en el dropdown.

#### Scenario: Ver todas abre el listado completo

- **WHEN** el usuario tiene más notificaciones que el máximo mostrado en el panel y hace click en "Ver todas"
- **THEN** el sistema navega a la vista de listado completo, paginada, con el resto de sus notificaciones

### Requirement: Retención de notificaciones

El sistema SHALL aplicar una ventana de retención sobre las notificaciones, configurable por instancia y sin valor embebido en el código de `core/`; las notificaciones fuera de la ventana de retención SHALL excluirse del listado y del conteo de no-leídas.

#### Scenario: Notificaciones fuera de la ventana de retención no se listan

- **WHEN** una notificación del usuario supera la ventana de retención configurada para la instancia
- **THEN** deja de aparecer en el listado y no cuenta para el indicador de no-leídas de la campana

### Requirement: Accesibilidad AA del panel de notificaciones

El panel de notificaciones SHALL cumplir WCAG 2.1 AA: contraste suficiente en ambos temas, navegación completa por teclado (flechas entre ítems, Enter para abrir, Esc para cerrar devolviendo el foco a la campana) y semántica ARIA apropiada para lector de pantalla.

#### Scenario: Navegación completa por teclado

- **WHEN** un usuario abre la campana con el teclado y navega el panel con flechas
- **THEN** puede recorrer cada notificación, activar "Ver" con Enter, y cerrar el panel con Esc devolviendo el foco a la campana, sin usar el mouse en ningún paso
