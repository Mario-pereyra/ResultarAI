# app-shell — Delta Spec (d10-design-system-shell)

## ADDED Requirements

### Requirement: Shell persistente en toda vista autenticada

El frontend SHALL renderizar un shell persistente compuesto por banner IA, sidebar, topbar y slot de contenido en toda vista autenticada, con la anatomía descrita en `design/DESIGN-SYSTEM.md` §6.1 y `design/VISTAS/01-acceso-shell.md` Vista 3 (`03-shell.html`).

#### Scenario: Layout de escritorio

- **WHEN** un usuario autenticado carga cualquier vista en viewport ≥1200 px
- **THEN** el shell muestra el banner IA (28 px, arriba), sidebar de 240 px, topbar de 56 px y el contenido en el slot central, según `design/mockups/03-shell.html`

#### Scenario: Sidebar colapsable persistente

- **WHEN** el usuario colapsa el sidebar a 64 px (solo íconos con tooltip)
- **THEN** el estado de colapso se persiste por usuario y se restaura en la siguiente carga, según `design/VISTAS/01-acceso-shell.md` Vista 3 (sección Interacciones)

### Requirement: Banner permanente de IA no ocultable

El shell SHALL mostrar en todas las vistas autenticadas, para todos los roles, un banner con el texto "Respuestas generadas por IA — verificá antes de aplicar en cliente" (o su forma acortada en móvil), sin ningún control de usuario que permita ocultarlo.

#### Scenario: Banner presente sin acción de cierre

- **WHEN** se inspecciona el DOM del shell en cualquier vista autenticada
- **THEN** el elemento `.ai-banner` está presente y no expone ningún botón, ícono o gesto de cierre, según `design/FUNCIONALIDADES.md` §2 ("Banner permanente de IA") y `design/mockups/tokens.css` clase `.ai-banner`

#### Scenario: Banner se acorta en móvil sin desaparecer

- **WHEN** el viewport es <768 px
- **THEN** el banner permanece visible con el texto acortado según `design/VISTAS/01-acceso-shell.md` Vista 3 (sección Móvil)

### Requirement: Sidebar filtrado por matriz de capacidades del rol

El sidebar SHALL renderizar únicamente las secciones que la matriz de capacidades habilita para el rol del usuario autenticado; una sección no habilitada SHALL no renderizarse (ocultar, no deshabilitar), según `design/DESIGN-SYSTEM.md` §9.7 y `design/FUNCIONALIDADES.md` §2 ("Shell única por capacidades"). La matriz de capacidades como configuración editable por el Admin es alcance de `d20-gobernanza-plataforma`; este shell consume una matriz de ejemplo estática equivalente a la tabla de `design/VISTAS/01-acceso-shell.md` Vista 3 ("Diferencias por rol").

#### Scenario: Rol Funcional no ve secciones de Admin

- **WHEN** un usuario con rol Funcional carga el shell
- **THEN** el sidebar muestra Catálogo, Chat, Workflows, Aprobaciones y Mi espacio, y no renderiza (ni en el DOM) las secciones Administración ni Construcción, según la tabla "Diferencias por rol" de `design/VISTAS/01-acceso-shell.md` Vista 3

#### Scenario: Rol Admin ve todas las secciones

- **WHEN** un usuario con rol Admin carga el shell
- **THEN** el sidebar agrega, tras un divisor con kicker "ADMIN", las secciones Administración y Construcción, según `design/mockups/03-shell.html`

### Requirement: Identidad visible en el header

El topbar SHALL mostrar la identidad del usuario autenticado (avatar/iniciales + nombre) junto con un badge de rol visible (`ADMIN`/`TÉCNICO`/`FUNCIONAL`), y un menú desplegable con acceso a Mi espacio, tema y cerrar sesión.

#### Scenario: Badge de rol visible en el menú de usuario

- **WHEN** se abre el menú de usuario del topbar
- **THEN** el badge de rol coincide con el rol de la sesión (`badge-rol--admin`/`--tecnico`/`--funcional`) según `design/mockups/tokens.css` §5.4 y `design/VISTAS/01-acceso-shell.md` Vista 3

### Requirement: Selector de tema personal

El topbar SHALL exponer un conmutador de tema (dark/light) que alterna `html[data-theme]` y persiste la preferencia por usuario; el brand (`data-brand`) SHALL permanecer fijo por configuración de instancia y no SHALL exponerse como control de usuario.

#### Scenario: Alternar tema persiste entre sesiones

- **WHEN** el usuario alterna el tema con el switcher del topbar y recarga la aplicación en una sesión posterior
- **THEN** el tema elegido se mantiene, y el brand de la instancia no cambia, según `design/DESIGN-SYSTEM.md` §2.1 y `design/FUNCIONALIDADES.md` §2 ("Selector de tema dark/light")

### Requirement: Estado global GATEWAY_OFFLINE accionable

Cuando la plataforma reporta el gateway caído, el shell SHALL mostrar un estado accionable siguiendo la plantilla de ErrorCard (qué pasó, por qué, qué hacer) sin bloquear la navegación del shell en sí, según `design/DESIGN-SYSTEM.md` §8.16 y §9.6, y `design/FUNCIONALIDADES.md` §2 ("Estados globales accionables").

#### Scenario: Gateway caído no bloquea el shell

- **WHEN** el estado del gateway es `GATEWAY_OFFLINE`
- **THEN** el shell (sidebar, topbar, banner) sigue renderizando con normalidad y el contenido afectado muestra el error-card `GATEWAY_OFFLINE` con acción "Reintentar", según `design/DESIGN-SYSTEM.md` §8.16

#### Scenario: Redacción del error se adapta al rol

- **WHEN** el error `GATEWAY_OFFLINE` se muestra a un usuario Funcional
- **THEN** el texto evita jerga técnica ("El asistente no está disponible") mientras que Técnico/Admin ven el código `GATEWAY_OFFLINE`, según `design/DESIGN-SYSTEM.md` §4.2 y §8.16

### Requirement: Navegación por teclado y skip-link

El shell SHALL ser completamente operable por teclado: orden de tabulación igual al orden visual, `Ctrl/⌘+K` enfoca el buscador global, y un skip-link "Saltar al contenido" es el primer elemento enfocable de cada carga.

#### Scenario: Skip-link es el primer foco

- **WHEN** un usuario presiona `Tab` por primera vez tras cargar el shell
- **THEN** el foco cae en el skip-link "Saltar al contenido", visible al enfocarse, según `design/DESIGN-SYSTEM.md` §10

### Requirement: Responsive del shell en móvil

En viewport <768 px, el sidebar SHALL convertirse en un drawer sobre scrim con trampa de foco, cierre por scrim/`Esc`/swipe, y el topbar SHALL conservar hamburguesa, campana y avatar.

#### Scenario: Drawer con trampa de foco en móvil

- **WHEN** un usuario abre el sidebar en viewport <768 px
- **THEN** el sidebar se muestra como drawer con `aria-modal`, trampa de foco, y se cierra con `Esc`, click en el scrim o swipe, según `design/VISTAS/01-acceso-shell.md` Vista 3 (sección Móvil)
