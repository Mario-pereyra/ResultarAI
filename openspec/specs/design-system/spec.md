# design-system Specification

## Purpose
TBD - created by archiving change d10-design-system-shell. Update Purpose after archive.
## Requirements
### Requirement: Los 4 sets de tokens de tema×brand como CSS custom properties

El frontend SHALL portar a CSS custom properties reales, sin pérdida de valores, los 4 sets de tokens semánticos de color definidos en `design/mockups/tokens.css` (fuente de verdad de valores) y documentados en `design/DESIGN-SYSTEM.md` §3.1, bajo selectores `html[data-theme="dark"|"light"][data-brand="default"|"totvs"]`.

#### Scenario: Los 4 sets están completos

- **WHEN** se inspeccionan los selectores `html[data-theme][data-brand]` del CSS del frontend para las 4 combinaciones (dark·default, light·default, dark·totvs, light·totvs)
- **THEN** cada uno define los 19 tokens semánticos de `design/DESIGN-SYSTEM.md` §3.1 (`--bg`, `--bg-raised`, `--panel`, `--line`, `--line-strong`, `--ink`, `--ink-dim`, `--ink-faint`, `--accent`, `--accent-fill`, `--accent-ink`, `--accent-soft`, `--accent-alt`, `--money`, `--info`, `--warn`, `--danger`, `--danger-ink`, `--focus-ring`, `--scrim`) con los valores exactos de `design/mockups/tokens.css`

#### Scenario: dark·default es el tema por defecto de la instancia

- **WHEN** una instancia no configura explícitamente `data-theme`/`data-brand`
- **THEN** el documento aplica `dark`/`default` (según `design/mockups/tokens.css` §3.1 y `design/DESIGN-SYSTEM.md` §2.1)

### Requirement: Tokens globales fuera de los bloques de tema

El frontend SHALL definir como custom properties globales (no condicionadas a tema ni brand) la tipografía, la escala de espaciado, los radios, las sombras por variable, el motion, el z-index y los breakpoints de `design/DESIGN-SYSTEM.md` §3.2 y §3.3.

#### Scenario: Escala de espaciado completa

- **WHEN** se inspecciona `:root` del CSS del frontend
- **THEN** existen `--sp-1` a `--sp-10` con los valores en múltiplos de 4 px de `design/DESIGN-SYSTEM.md` §3.3, y `--r-xs`/`--r-sm`/`--r-md`/`--r-lg`/`--r-xl`/`--r-pill`, `--dur-1`/`--dur-2`/`--dur-3`, `--z-nav`/`--z-dropdown`/`--z-overlay`/`--z-modal`/`--z-toast`/`--z-tooltip`

#### Scenario: Breakpoints documentados y aplicados

- **WHEN** se revisan los media queries del frontend
- **THEN** usan los valores literales 380 px (móvil), 768 px (tablet) y 1200 px (desktop) de `design/DESIGN-SYSTEM.md` §3.3, desktop-first según §11

### Requirement: Tipografías del sistema con tabular-nums en datos operativos

El frontend SHALL cargar Chakra Petch (display), Saira (body) y JetBrains Mono (mono) como los únicos `--font-display`/`--font-body`/`--font-mono`, y todo dato operativo (montos, tokens, IDs, fechas-hora en tablas) SHALL renderizarse en `--font-mono` con `font-variant-numeric: tabular-nums`.

#### Scenario: Columna numérica alineada

- **WHEN** un componente de tabla del styleguide muestra una columna de números (p. ej. montos de ejemplo)
- **THEN** la celda usa la clase `.num`/`.mono` con `font-family: var(--font-mono)` y `font-variant-numeric: tabular-nums`, según `design/DESIGN-SYSTEM.md` §4.1 y `design/mockups/tokens.css` clase `.mono`

### Requirement: Componentes base consumen solo tokens semánticos

Todo componente base del frontend SHALL referenciar exclusivamente variables CSS semánticas (`var(--accent)`, `var(--danger)`, etc.); ningún componente SHALL contener un valor de color hexadecimal, `rgb()`/`rgba()` u otro literal de color hardcodeado fuera de la capa de tokens.

#### Scenario: Auditoría estática sin hex hardcodeado

- **WHEN** se ejecuta un lint/grep de colores literales (`#[0-9a-fA-F]{3,8}`, `rgb(`, `rgba(`) sobre los archivos de componentes del frontend (excluyendo el archivo de definición de tokens)
- **THEN** no se encuentra ninguna coincidencia

#### Scenario: Agregar un brand no toca componentes

- **WHEN** se agrega un quinto set de tokens de tema×brand siguiendo el checklist de `design/DESIGN-SYSTEM.md` Apéndice A
- **THEN** ningún archivo de componente requiere modificación (solo el archivo de tokens)

### Requirement: Inventario de componentes base del shell

El frontend SHALL implementar, con la anatomía, variantes y estados descritos en `design/DESIGN-SYSTEM.md` §8, los siguientes componentes base: botón (`.btn`, variantes primary/secondary/danger/ghost, tamaños sm/lg/block, estados default/hover/focus-visible/active/disabled/loading), input/textarea/select (`.field`/`.input`/`.textarea`/`.select`), tabla de datos densa (`.table-wrap`/`.table`/`.table--dense`), card/panel (`.panel`, variantes flush/raised), tag/badge-rol (`.tag`, `.badge-rol`), toast (`.toast-stack`/`.toast`), modal (`.overlay`/`.modal`), dropdown (patrón usado por el menú de usuario y la campana), tooltip (`[data-tip]`) y skeleton/empty-state.

#### Scenario: Botón primario con estado de carga

- **WHEN** un formulario del styleguide dispara el estado loading de un `.btn--primary`
- **THEN** el botón muestra `aria-busy="true"`, el spinner descrito en `design/DESIGN-SYSTEM.md` §8.1 y el texto permanece disponible para lectores de pantalla (no se elimina el `aria-label`)

#### Scenario: Modal con trampa de foco

- **WHEN** se abre un `.modal` desde el styleguide
- **THEN** el foco queda atrapado dentro del modal, `Esc` lo cierra (salvo variante destructiva a mitad de confirmación), y al cerrarse el foco vuelve al elemento disparador, según `design/DESIGN-SYSTEM.md` §8.8

#### Scenario: Tabla densa con datos monoespaciados

- **WHEN** se renderiza `.table--dense` con una columna de datos operativos
- **THEN** el padding vertical de celda es 6 px y las celdas numéricas usan `.num` (mono + tabular-nums), según `design/DESIGN-SYSTEM.md` §6.1 y §8.4

### Requirement: Contraste WCAG 2.1 AA verificado en los 4 sets

Todo par de texto/fondo usado por los componentes base SHALL cumplir la matriz de contraste de `design/DESIGN-SYSTEM.md` §5.3 (≥4.5:1 para texto normal, ≥3:1 para texto ≥24 px o gráficos) en las 4 combinaciones de tema×brand.

#### Scenario: Verificación automatizada de contraste

- **WHEN** se ejecuta la verificación de contraste (script o test) sobre los pares documentados en `design/DESIGN-SYSTEM.md` §5.3 para las 4 combinaciones
- **THEN** ningún par reporta un ratio menor al mínimo AA correspondiente

#### Scenario: Foco visible en todo interactivo

- **WHEN** se navega el styleguide completo por teclado (`Tab`)
- **THEN** todo elemento interactivo muestra `:focus-visible` con anillo de 2 px `var(--focus-ring)` y offset 2 px, y ningún elemento tiene `outline: none` sin un reemplazo visible, según `design/DESIGN-SYSTEM.md` §10

### Requirement: Página styleguide interna de verificación visual

El frontend SHALL exponer una página interna (no pública en producción) que renderice los 4 sets de tokens con un selector tema/brand y una demostración de cada componente base del inventario, equivalente en cobertura a `design/mockups/00-styleguide.html`.

#### Scenario: Styleguide renderiza los 4 sets

- **WHEN** se abre la página styleguide y se alternan `data-theme` y `data-brand` con el selector
- **THEN** los componentes base cambian de apariencia reflejando cada uno de los 4 sets sin errores visuales ni de contraste

