# i18n-foundation — Delta Spec (d10-design-system-shell)

## ADDED Requirements

### Requirement: Todos los textos de UI externalizados en catálogos de mensajes

Ningún texto de interfaz visible al usuario introducido por este change SHALL estar hardcodeado en componentes o markup; todo texto SHALL originarse en un catálogo de mensajes (claves de mensaje), según `design/DESIGN-SYSTEM.md` §12 y `design/FUNCIONALIDADES.md` §14 ("i18n preparado").

#### Scenario: Auditoría de strings hardcodeados

- **WHEN** se audita el código del frontend introducido por este change en busca de texto literal en español dentro de JSX/TSX (fuera de archivos de catálogo de mensajes)
- **THEN** no se encuentra ningún string de UI hardcodeado; todo texto se resuelve vía clave de catálogo

### Requirement: Voseo consistente en todos los textos del producto

Todo texto de UI en español SHALL usar voseo («Revisá», «Solicitá», «Verificá»), evitando tanto el "usted" como el "tú", según `design/DESIGN-SYSTEM.md` §4.2.

#### Scenario: Textos del shell en voseo

- **WHEN** se revisan los textos del banner IA, del wizard de estados y de los componentes base en español
- **THEN** todos los verbos dirigidos al usuario están conjugados en voseo (p. ej. "verificá", no "verifica" ni "verifique")

### Requirement: Layouts reservan espacio para expansión de texto (+25%)

Ningún layout de componente base o del shell introducido por este change SHALL fijar anchos en píxeles sobre contenedores de texto traducible; los contenedores de texto SHALL soportar al menos un 25% más de longitud de texto sin romper el layout, según `design/DESIGN-SYSTEM.md` §12.

#### Scenario: Botón con texto 25% más largo no rompe el layout

- **WHEN** se reemplaza el texto de un botón o label del shell por una cadena un 25% más larga
- **THEN** el componente ajusta su ancho (padding flexible, `white-space` consciente) sin recortar el texto ni desbordar su contenedor

### Requirement: Plantillas con placeholders nombrados

Ningún texto SHALL concatenar fragmentos de oración con variables intercaladas; toda interpolación SHALL usar plantillas con placeholders nombrados (p. ej. `{usuario} aprobó la escritura`), según `design/DESIGN-SYSTEM.md` §12.

#### Scenario: Mensaje con variable usa placeholder nombrado

- **WHEN** se revisa un mensaje de catálogo que incluye una variable dinámica
- **THEN** la variable aparece como placeholder nombrado dentro de una única clave de mensaje, no como concatenación de fragmentos de string

### Requirement: Plurales por regla ICU

Todo mensaje con conteo variable introducido por este change SHALL usar la sintaxis de plurales ICU (`{n, plural, one {...} other {...}}`), según `design/DESIGN-SYSTEM.md` §12.

#### Scenario: Contador de notificaciones no leídas

- **WHEN** el catálogo define el mensaje del contador de notificaciones no leídas del shell
- **THEN** el mensaje usa sintaxis de plural ICU y no una concatenación manual del número con un string singular/plural fijo

### Requirement: Formatos de fecha/número por locale de instancia

Todo dato de fecha, hora, moneda o número mostrado por el shell o los componentes base SHALL formatearse vía `Intl.NumberFormat`/`Intl.DateTimeFormat` con el locale de instancia (es-BO por defecto), según `design/DESIGN-SYSTEM.md` §9.8.

#### Scenario: Formato de fecha en es-BO

- **WHEN** un componente del styleguide muestra una fecha-hora de ejemplo
- **THEN** se formatea como `dd/mm/aaaa HH:mm` (24 h) vía `Intl.DateTimeFormat` con locale `es-BO`, según `design/DESIGN-SYSTEM.md` §9.8
