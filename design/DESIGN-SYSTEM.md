# Sistema de Diseño — Resultar Agents Platform

> **Estado:** v1.0 — fundación. Fuente de verdad visual: [`mockups/tokens.css`](mockups/tokens.css). Validación visual: [`mockups/00-styleguide.html`](mockups/00-styleguide.html).
> **Alcance:** documentación de diseño para construir los mockups y, después, la UI real (`apps/web`, Next.js + assistant-ui). No es código de producción.
> **Relación:** UX-SPEC (flujos y estados), ADR-0006 (modelos/fallback), ADR-0007/0010 (cuotas), ADR-0011 (registro de prompts), ANEXO-ATTACHMENTS (adjuntos).

---

## 1. Principios de diseño

Cinco principios, cada uno anclado al dominio: consultores TOTVS Protheus trabajando contra ERPs de clientes reales, con presupuesto de tokens finito y escrituras que pueden romper una contabilidad.

### P1 — Precisión instrumental
La plataforma es un instrumento de trabajo, no un juguete conversacional. Todo dato operativo (costos, tokens, fechas, parámetros `MV_*`, códigos de tabla `SX*`) se muestra en **JetBrains Mono con `tabular-nums`**, alineado y sin ambigüedad. Radios pequeños, bordes visibles, jerarquía tipográfica nítida. **Por qué:** un consultor que valida parametrización contable necesita distinguir `MV_PAISLOC` de `MV_PAISLOC2` de un vistazo; la estética "sala de control" no es decorativa, comunica que aquí los detalles importan.

### P2 — Transparencia del costo y de la IA
Nada de magia: el costo se muestra en vivo (taxímetro), el cache se muestra (chips hit/miss para Técnico/Admin), el modelo usado se muestra (etiqueta "modelo alterno" **para todos los roles** cuando hay fallback), y el banner permanente recuerda que las respuestas son generadas por IA. **Por qué:** la economía del proyecto depende del cache-first (ADR-0001); hacer visible el costo crea la cultura que lo sostiene. Y un consultor que confía a ciegas en una respuesta de IA frente a un cliente es un riesgo de negocio: la transparencia es una función de seguridad.

### P3 — Jerarquía por capas de rol
**Una sola UI.** Las capacidades se agregan por capa: Funcional ve una experiencia limpia tipo ChatGPT (cero jerga, cero costos, cero cache); Técnico agrega la ficha técnica de agentes (tools, costo, versión de prompt, evals); Admin agrega telemetría, consola, builders y registro de prompts. Lo que un rol no tiene **no existe en su pantalla** (se oculta, no se deshabilita — ver §9.7). **Por qué:** interfaces separadas por rol divergen y duplican mantenimiento; una UI con capas mantiene un único modelo mental y permite que un usuario promovido de rol reconozca su entorno.

### P4 — Densidad controlada
Desktop-first para usuarios expertos: tablas densas, paneles compactos, atajos visibles. Pero densidad ≠ ruido: espaciado en escala de 4 px, máximo dos niveles de énfasis por vista, aire alrededor de las acciones destructivas. **Por qué:** un consultor compara 40 parámetros contra un checklist; obligarlo a paginar de a 5 filas es hostil. La densidad se controla con jerarquía, no eliminando información.

### P5 — Confianza y evidencia
Toda afirmación del sistema lleva su evidencia: las respuestas de DocAgent citan fuente (TDN/CST) o se abstienen; toda escritura a Protheus pasa por tarjeta HITL con payload visible, cliente/ambiente y riesgo; toda degradación (VPN caída, fallback de modelo) se declara. Los errores dicen **qué pasó, por qué y qué hacer**. **Por qué:** el producto se usa contra ERPs de clientes finales; un dato inventado o una escritura silenciosa destruyen la confianza que vende el servicio. La UI debe hacer estructuralmente visible la diferencia entre "el sistema sabe" y "el sistema cree".

---

## 2. Arquitectura de theming por instancia

El producto se vende **instancia por cliente** (cada consultora despliega la suya). El theming es configuración de instancia, no preferencia individual — con una excepción: el tema claro/oscuro.

### 2.1 Qué configura una instancia

| Configurable | Mecanismo | Quién |
|---|---|---|
| **Brand** (`default` \| `totvs` \| futuros) | `html[data-brand]` — selecciona el set de tokens | Configuración de instancia (deploy) |
| **Logo y nombre** | Asset + string de instancia | Configuración de instancia |
| **Tema por defecto** (`dark` \| `light`) | `html[data-theme]` inicial | Configuración de instancia |
| **Tema efectivo** | El usuario puede alternarlo; se persiste por usuario | Usuario (cualquier rol) |
| Catálogo de agentes, usuarios, cuotas | Datos de instancia (no theming) | Admin |

### 2.2 Qué NO es personalizable

- **Tokens semánticos y su significado:** `--money` siempre es verde-dinero/éxito, `--danger` siempre rojo. Un brand puede mover el matiz, jamás el rol semántico.
- **Tipografías:** Chakra Petch / Saira / JetBrains Mono en todos los brands (la fuente corporativa TOTVS no está disponible públicamente; el brand `totvs` se expresa por color).
- **Espaciado, radios, motion, breakpoints, z-index:** globales, fuera de los bloques de tema.
- **Componentes y layout:** un brand no puede mover el sidebar ni cambiar la anatomía de la tarjeta HITL.
- **Reglas de accesibilidad:** todo brand nuevo entra con sus 2 temas completos y matriz de contraste AA verificada — es requisito de alta, no opción.

### 2.3 Mecánica

Los 4 sets de tokens viven en `tokens.css` bajo selectores `html[data-theme="…"][data-brand="…"]`. Los componentes consumen **solo tokens semánticos** (`var(--accent)`, nunca `#ffb000`). Agregar un brand = agregar 2 bloques de tokens (dark + light) + verificación AA; cero cambios en componentes.

---

## 3. Referencia de tokens

### 3.1 Tokens semánticos de color (por combinación tema × brand)

| Token | Rol | dark·default | light·default | dark·totvs | light·totvs |
|---|---|---|---|---|---|
| `--bg` | Fondo de aplicación | `#0a0d13` | `#f2efe8` | `#0b1020` | `#f2f5f8` |
| `--bg-raised` | Sidebar, inputs, zonas elevadas | `#10151f` | `#f8f6f0` | `#101a2e` | `#f8fafc` |
| `--panel` | Cards, paneles, modals | `#121826` | `#fffdf8` | `#0e2030` | `#ffffff` |
| `--line` | Bordes/divisores sutiles | `#222b3c` | `#ddd6c6` | `#1f3346` | `#d7dee5` |
| `--line-strong` | Bordes de controles | `#35415a` | `#b9b09a` | `#2f4a61` | `#b3c0cb` |
| `--ink` | Texto principal | `#e8edf5` | `#1b2130` | `#eef3f8` | `#002233` |
| `--ink-dim` | Texto secundario | `#9aa7bd` | `#4f5868` | `#9fb2c4` | `#3c5666` |
| `--ink-faint` | Metadatos, placeholders | `#7c89a0` | `#6e7787` | `#74879b` | `#5d7382` |
| `--accent` | Acento/atención (texto, íconos, foco activo) | `#ffb000` | `#8a5c00` | `#00dbff` | `#0a46ea` |
| `--accent-fill` | Relleno de acción primaria | `#ffb000` | `#ffb000` | `#00dbff` | `#0a46ea` |
| `--accent-ink` | Tinta sobre `--accent-fill` | `#181102` | `#181102` | `#002233` | `#ffffff` |
| `--accent-soft` | Tinte de selección/realce | `rgba(255,176,0,.14)` | `rgba(255,176,0,.22)` | `rgba(0,219,255,.12)` | `rgba(0,219,255,.22)` |
| `--accent-alt` | Acento cálido (escalación Pro, riesgo alto) | `#ffb000` | `#8a5c00` | `#ff8900` | `#a85600` |
| `--money` | Dinero, éxito, OK | `#3ddc97` | `#0e7a50` | `#3ddc97` | `#0e7a50` |
| `--info` | Enlaces, datos informativos | `#58aeff` | `#1d5fc2` | `#58aeff` | `#0a46ea` |
| `--warn` | Advertencia (cuota 80%, degradado) | `#ffb000` | `#8a5c00` | `#ffb800` | `#8a5c00` |
| `--danger` | Peligro, destructivo, bloqueo | `#ff5c5c` | `#b42b2b` | `#ff5c5c` | `#b42b2b` |
| `--danger-ink` | Tinta sobre relleno danger | `#1f0a0a` | `#ffffff` | `#1f0a0a` | `#ffffff` |
| `--focus-ring` | Anillo de foco | `#ffb000` | `#8a5c00` | `#00dbff` | `#0a46ea` |
| `--scrim` | Fondo de overlay | `rgba(4,6,10,.66)` | `rgba(27,33,48,.45)` | `rgba(0,10,20,.66)` | `rgba(0,34,51,.45)` |

Notas de diseño:
- En brand **default**, `--warn` y `--accent` comparten el ámbar deliberadamente: *el ámbar ES la atención* en la sala de control. En brand **totvs** se separan (cian = marca/acción, `#FFB800` = advertencia, `#FF8900` = acento cálido), siguiendo la paleta oficial del rebrand dic-2025 (Guia da Marca TOTVS).
- En **light·totvs**, `#00DBFF` falla como texto sobre blanco (1.67:1): solo se usa como superficie/realce (`--accent-soft`) con tinta `#002233` encima; el interactivo es el azul funcional oficial `#0A46EA`.
- `--money` y `--danger` son **transversales a brands**: el significado de "esto cuesta dinero" y "esto es peligroso" no cambia con el logo.

### 3.2 Tipografía

| Token | Valor | Uso |
|---|---|---|
| `--font-display` | Chakra Petch | h1/h2, kickers, títulos de modal, labels instrumentales |
| `--font-body` | Saira | todo el texto de UI, botones, formularios |
| `--font-mono` | JetBrains Mono | números, dinero, tokens, código, payloads, tags, headers de tabla |

Escala (12→32 px, ratio ≈1.2): `--fs-caption` 12 · `--fs-small` 13 · `--fs-body` 14 · `--fs-lead` 16 · `--fs-h4` 18 · `--fs-h3` 20 · `--fs-h2` 24 · `--fs-h1` 28 · `--fs-display` 32. Alturas de línea: `--lh-tight` 1.2 · `--lh-base` 1.5 · `--lh-loose` 1.65.

### 3.3 Espaciado, radios, sombras, motion, z-index, breakpoints

- **Espaciado** (escala 4 px): `--sp-1` 4 · `--sp-2` 8 · `--sp-3` 12 · `--sp-4` 16 · `--sp-5` 20 · `--sp-6` 24 · `--sp-7` 32 · `--sp-8` 40 · `--sp-9` 48 · `--sp-10` 64.
- **Radios:** `--r-xs` 2 · `--r-sm` 4 (controles) · `--r-md` 6 (cards menores) · `--r-lg` 10 (paneles/modals) · `--r-xl` 14 · `--r-pill` 999. Contenidos a propósito: la estética instrumental no usa esquinas blandas.
- **Sombras:** `--shadow-1/2/3` definidas por tema (en dark casi todo el relieve lo dan los bordes; en light las sombras son tenues y cálidas/frías según brand).
- **Motion:** `--dur-1` 120 ms (hover/focus) · `--dur-2` 180 ms (transiciones) · `--dur-3` 280 ms (toasts/modals); easings `--ease-out`, `--ease-in-out`. Con `prefers-reduced-motion`: se apagan pulsos y shimmer; el spinner se conserva (feedback funcional).
- **Z-index:** nav 10 · dropdown 40 · overlay 80 · modal 90 · toast 100 · tooltip 110.
- **Breakpoints:** móvil 380 · tablet 768 · desktop 1200 (desktop-first; ver §11).

---

## 4. Tipografía y voz

### 4.1 Uso tipográfico

- **Chakra Petch** solo en display: h1/h2, kickers, título de modal, labels del taxímetro. Nunca en párrafos.
- **Saira** para todo lo demás. Pesos: 400 texto, 500 énfasis suave, 600 botones/títulos h3-h4, 700 excepcional.
- **JetBrains Mono** obligatorio para: montos, tokens, contadores, IDs, fechas-hora en tablas, parámetros (`MV_PAISLOC`), tablas Protheus (`SX3`), payloads, versiones de prompt (`docagent@12`), códigos de error. Siempre con `font-variant-numeric: tabular-nums` cuando hay columnas de números.
- Jerarquía máxima por vista: 1 × h1, kickers para seccionar, h3/h4 dentro de paneles. No saltar niveles.

### 4.2 Voz y redacción UI (español)

- **Voseo** (estándar del producto, coherente con el banner obligatorio "verificá antes de aplicar"): «Revisá la parametrización», «Solicitá liberación». Evitar el "usted" (distante) y el "tú" (inconsistente).
- **Sentence case** en todo: títulos, botones, tabs («Solicitar liberación», no «Solicitar Liberación»). MAYÚSCULAS solo en kickers, tags y códigos de error (`QUOTA`, `VPN_OFFLINE`).
- Botones = verbo + objeto, máx. 3 palabras: «Aprobar escritura», «Ver evidencia», «Crear rama».
- Errores accionables, sin culpa y sin jerga interna en rol Funcional: nada de "LLM", "tokens" o "prefix cache" fuera de Técnico/Admin. Funcional ve «El asistente no está disponible», Técnico ve «GATEWAY_OFFLINE».
- Sin signos de exclamación en UI operativa. Sin humor en errores ni en HITL.
- Números en mono (ver §9.8 para formatos es-BO).
- Terminología fija: «agente» (no "bot"), «sesión» / «rama», «escalación a Pro», «aprobación» (HITL), «cuota», «modelo alterno», «evidencia» (citas).

---

## 5. Color

### 5.1 Roles semánticos (regla dura)

| Color | Rol | Úsalo para | Nunca para |
|---|---|---|---|
| **Ámbar / acento** (`--accent`) | Atención + identidad | Acción primaria, foco activo, tab activa, kickers, selección, escalación | Éxito, dinero, decoración masiva (≤10% de la vista) |
| **Verde** (`--money`) | Dinero + éxito | Costos USD, taxímetro, cache hit, estados OK, pasos completados, cuota sana | Botones primarios, enlaces |
| **Rojo** (`--danger`) | Peligro | Acciones destructivas, errores bloqueantes, cuota 100%, riesgo crítico, validación fallida | Énfasis genérico, advertencias recuperables |
| **Info** (`--info`) | Enlaces + datos | Enlaces, citas/evidencia, cache write, tags informativos, notificaciones neutras | Estados de éxito o peligro |
| **Warn** (`--warn`) | Advertencia | Cuota ≥80%, degradado (modelo alterno, VPN inestable), HITL pendiente | Errores bloqueantes (eso es danger) |
| **Acento cálido** (`--accent-alt`) | Escalación / riesgo alto | Tarjeta NEEDS_PRO, riesgo alto en HITL | Texto largo |

Regla de proporción en dark·default: el fondo domina (~80%), paneles/líneas (~15%), color semántico (~5%). El ámbar pierde su poder si está en todas partes.

### 5.2 Reglas de aplicación

- El color **nunca es el único canal**: todo estado lleva ícono o texto además del color (daltonismo, WCAG 1.4.1).
- Texto sobre tintes suaves (`color-mix … 12%`): usar el color pleno del rol como tinta — los pares están verificados.
- Enlaces siempre `--info` subrayados al hover; la acción primaria siempre `--accent-fill`+`--accent-ink`.
- En light, los colores "brillantes" de marca (`#ffb000`, `#00dbff`, `#ff8900`) **no se usan como texto**: existen variantes oscurecidas por token (`--accent`, `--accent-alt`, `--warn`).

### 5.3 Matriz de contraste (WCAG 2.1, ratios calculados)

Pares de texto principales — todos ≥4.5:1 (AA texto normal):

| Par | dark·default | light·default | dark·totvs | light·totvs |
|---|---|---|---|---|
| `--ink` / `--bg` | 16.6 | 14.0 | 17.0 | 15.6 |
| `--ink-dim` / `--panel` | 7.4 | 7.2 | 7.6 | 7.7 |
| `--ink-faint` / `--panel` | 5.0 | 4.5 | 4.8 | 5.0 |
| `--accent` / `--bg` | 10.6 | 5.1 | 11.3 | 6.2 |
| `--accent-ink` / `--accent-fill` | 10.2 | 10.2 | 9.85 | 6.8 |
| `--money` / `--bg` | 11.0 | 4.7 | 10.8 | 4.9 |
| `--info` / `--bg` | 8.2 | 5.3 | 8.0 | 6.2 |
| `--warn` / `--bg` | 10.6 | 5.1 | 10.9 | 5.2 |
| `--danger` / `--bg` | 6.4 | 5.5 | 6.3 | 5.7 |
| `--danger-ink` / `--danger` | 6.0 | 6.3 | 6.0 | 6.3 |

Sobre `--panel` (ligeramente distinto de `--bg`) los ratios varían <8% y ningún par baja de 4.5:1. Todo brand nuevo debe entregar esta tabla completa antes de habilitarse en una instancia.

---

## 6. Espaciado, grid y layout

### 6.1 Shell de aplicación

```
┌──────────────────────────────────────────────────────────┐
│ ai-banner (permanente, 28px)                             │
├───────────┬──────────────────────────────────────────────┤
│ sidebar   │ topbar: contexto + taxímetro* + campana      │
│ 240px     ├──────────────────────────────────────────────┤
│ (64px     │ contenido                                    │
│ colapsado)│   chat: columna máx. 760px centrada          │
│           │   tablas/admin: máx. 1200px                  │
│           │   formularios: máx. 560px                    │
└───────────┴──────────────────────────────────────────────┘
                                  * solo Técnico/Admin
```

- Sidebar: navegación por secciones (Chat, Catálogo, Workflows, Aprobaciones, + capas de rol: Ficha técnica / Consola admin). Colapsable a 64 px (solo íconos con tooltip).
- Gutter estándar: `--sp-6` (24 px) desktop, `--sp-4` (16 px) móvil. Separación entre paneles: `--sp-5`.
- Densidad de tablas: estándar 10 px de padding vertical; `.table--dense` 6 px para vistas de comparación (ValidationAgent). Mínimo 44 px de alto táctil en móvil.

### 6.2 Reglas de composición

- Una vista = un h1 (o kicker+h1). Acciones primarias arriba a la derecha del encabezado de página.
- Máximo un botón primario visible por zona de pantalla.
- Las acciones destructivas se separan del resto (espacio `--sp-6` o alineación opuesta).

---

## 7. Iconografía

- **Set único: [lucide](https://lucide.dev).** Trazo 2 px (por defecto de lucide; en tamaños 13-14 px usar 2.2 para legibilidad). En mockups: SVG inline copiado de lucide.
- Tamaños: **14** (dentro de chips/tags), **16** (botones, inline con texto), **18** (toasts, error cards), **20** (navegación), **24** (encabezados), **32** (empty states).
- El ícono hereda `currentColor`; jamás colores propios.
- Ícono solo (sin texto) únicamente con `aria-label` + tooltip. Prohibido en acciones destructivas: «Eliminar» siempre lleva palabra.
- Asociaciones fijas del dominio: aprobación HITL = `shield-check` · escalación Pro = `zap` · cache = `database` · costo = `circle-dollar-sign` · evidencia/cita = `quote` · VPN = `cable` · rama = `git-branch` · workflow = `list-checks` · agente = `bot`.

---

## 8. Inventario de componentes

Formato: **Anatomía · Variantes · Estados · Responsive · A11y.** Clases en `tokens.css`; los compuestos marcados ◆ tienen demo en `00-styleguide.html`.

### 8.1 Botones (`.btn`)

- **Anatomía:** contenedor inline-flex 36 px de alto, ícono 16 opcional + label. Radio `--r-sm`.
- **Variantes:** `--primary` (relleno `--accent-fill`; máx. 1 por zona) · `--secondary` (borde `--line-strong`) · `--danger` (relleno `--danger`; solo acciones destructivas/bloqueos) · `--ghost` (acciones terciarias, toolbars). Tamaños `--sm` 28 px, `--lg` 44 px, `--block`.
- **Estados:** default · hover (brightness/tinte + borde acento en secondary) · focus-visible (anillo 2 px `--focus-ring` offset 2) · active (oscurece) · disabled (`opacity .45`, `cursor: not-allowed`; ver §9.7 para cuándo deshabilitar) · loading (`.btn--loading`: spinner, texto transparente para no mover el layout, `pointer-events: none`).
- **Responsive:** en móvil las acciones de pie de tarjeta pasan a columna, primario abajo (zona del pulgar).
- **A11y:** elemento `<button>` real; loading añade `aria-busy="true"`; disabled por atributo, no solo clase; el label nunca desaparece en loading para lectores (mantener `aria-label`).

### 8.2 Inputs y formularios (`.field`, `.input`, `.textarea`)

- **Anatomía:** `.field` = label (+ `.req` si obligatorio) → control → `.field-hint` o `.field-error`. Alto 36 px.
- **Variantes:** texto, `--mono` (IDs, parámetros), textarea (min 88 px, redimensionable vertical).
- **Estados:** default · hover (borde sube medio tono) · focus (borde `--accent` + halo 3 px al 25%) · disabled (op. .5 + fondo tintado) · invalid (`.is-invalid`: borde `--danger`; halo rojo en focus) · readonly (sin borde de foco acentuado).
- **Responsive:** ancho 100% del contenedor; formularios máx. 560 px.
- **A11y:** `<label for>` siempre; error con `aria-describedby` + `aria-invalid="true"`; el hint no desaparece cuando aparece el error (se apilan); placeholder jamás sustituye al label.

### 8.3 Selects (`.select`)

- **Anatomía:** como input + chevron embebido (data-URI). Nativo (`<select>`) en v1.
- **Variantes:** estándar; con grupos (`<optgroup>`) para selector cliente-final/ambiente de ValidationAgent.
- **Estados:** los mismos del input. Valor sin elegir = placeholder `--ink-faint` («Seleccioná un ambiente…»).
- **A11y:** nativo = teclado y lector gratis. El par cliente/ambiente son dos selects encadenados: al cambiar cliente, el de ambiente se resetea y lo anuncia (`aria-live="polite"`).

### 8.4 Tablas de datos (`.table-wrap` + `.table`)

- **Anatomía:** wrapper con borde/scroll-x; thead mono uppercase 11 px `--ink-faint`; celdas 13 px; números a la derecha con `.num`.
- **Variantes:** estándar · `--dense` · con fila seleccionada (`.is-selected`, fondo `--accent-soft`) · primera columna fija (vistas de comparación).
- **Estados:** carga (3-5 filas skeleton con anchos variados) · vacío (empty-state dentro del wrapper) · error (error-card en lugar del cuerpo) · hover de fila (tinte 4%) · ordenamiento (flecha + `aria-sort`).
- **Responsive:** <768 px scroll horizontal con sombra de borde como affordance; vistas clave (aprobaciones) reformatean a cards apiladas.
- **A11y:** `<caption>` (visible u oculta); `scope="col"`; hover no es el único indicador de interactividad de fila (si la fila navega, lleva enlace explícito).

### 8.5 Cards / fichas (`.panel`)

- **Anatomía:** superficie `--panel`, borde `--line`, radio `--r-lg`, padding `--sp-5`. Ficha de agente: kicker (tipo de agente) + nombre + descripción + tags de capacidades + acción.
- **Variantes:** `--flush` (tablas embebidas), `--raised` (destacadas). Ficha técnica (capa Técnico): agrega versión de prompt (`docagent@12`), toolset, costo medio/sesión, score de evals.
- **Estados:** default · hover si toda la card es clickable (borde `--line-strong` + sombra; entonces TODA la card es un solo enlace) · seleccionada (borde `--accent`) · deshabilitada (agente sin acceso para el rol: no se muestra — §9.7).
- **Responsive:** grid de fichas `repeat(auto-fill, minmax(280px, 1fr))`.
- **A11y:** card clickable = un único `<a>` envolvente o título-enlace con pseudo-elemento; nunca handlers en divs.

### 8.6 Tags y badges (`.tag`, `.badge-rol`)

- **Anatomía:** tag 22 px, mono 11 uppercase, borde + tinte 12%. Badge de rol con punto cuadrado identitario.
- **Variantes tag:** neutral · `--accent` · `--money` · `--info` · `--warn` · `--danger` · `--alt` · `--outline`. Badge de rol: `--admin` (acento) · `--tecnico` (info) · `--funcional` (neutral).
- **Estados:** estáticos (no interactivos en v1; un tag-filtro será botón con `aria-pressed`).
- **Mapa de riesgo HITL:** bajo = `tag--money` · medio = `tag--warn` · alto = `tag--alt` · crítico = `tag--danger`. Siempre con la palabra («RIESGO ALTO»), nunca solo color.
- **A11y:** uppercase visual por CSS pero texto fuente en sentence case (los lectores deletrean siglas).

### 8.7 Tabs (`.tabs`, `.tab`)

- **Anatomía:** fila con borde inferior; tab activa con subrayado 2 px `--accent`. Contador opcional como tag.
- **Variantes:** navegación de vista (Ficha técnica: «Resumen / Tools / Prompt / Evals») · filtros de lista (Aprobaciones: «Pendientes 3 / Resueltas»).
- **Estados:** default · hover · activa · focus (anillo interior) · deshabilitada (evitar: si una tab no aplica al rol, no se renderiza).
- **Responsive:** scroll-x sin wrap.
- **A11y:** patrón WAI-ARIA tabs (`role="tablist"`, flechas ←→, `aria-selected`); si son enlaces de ruta, son nav-links, no tabs ARIA.

### 8.8 Modals / sheets (`.overlay` + `.modal`)

- **Anatomía:** scrim + caja ≤540 px (head con título display y cierre / body scrollable / foot con acciones alineadas a la derecha).
- **Variantes:** confirmación (texto + 2 botones) · formulario · destructiva (título con ícono `--danger`, primario danger, patrón escribir-para-confirmar §9.3) · sheet lateral derecha 420 px para detalle sin perder contexto (telemetría, detalle de aprobación).
- **Estados:** abierto/cerrando (fade+slide `--dur-3`) · loading interno (skeleton en body) · error de submit (error-card arriba del foot, foco al error).
- **Responsive:** <768 px el modal toma todo el ancho menos 16 px y el sheet se vuelve bottom-sheet a pantalla completa.
- **A11y:** `role="dialog"` `aria-modal="true"` + `aria-labelledby`; trampa de foco; Esc cierra (salvo destructivas a mitad de confirmación); al cerrar, el foco vuelve al disparador; scroll de fondo bloqueado.

### 8.9 Toasts (`.toast-stack` + `.toast`)

- **Anatomía:** apilados abajo-derecha, ≤360 px; borde izquierdo 3 px semántico + ícono + título + mensaje; cierre opcional.
- **Variantes:** info · `--ok` · `--warn` · `--danger`.
- **Estados:** entrada slide-up `--dur-3`; auto-cierre 6 s (info/ok) — warn/danger persisten hasta cierre manual; hover pausa el temporizador.
- **Responsive:** móvil: ancho completo menos 16 px, siguen abajo.
- **A11y:** contenedor `aria-live="polite"` (`assertive` solo danger); nunca poner la única vía a una acción dentro de un toast (la acción debe existir también en la vista).

### 8.10 Tooltips (`[data-tip]`)

- **Anatomía:** burbuja `--ink` sobre fondo invertido, 12 px, arriba del disparador.
- **Variantes:** una sola. Contenido máximo ~8 palabras; más que eso es un popover/sheet.
- **Estados:** hover y focus-visible (no solo hover — teclado).
- **A11y:** complementa, no sustituye: el dato esencial debe estar accesible sin hover (p. ej. el desglose del taxímetro vive también en el sheet de detalle). No usar en móvil como única vía.

### 8.11 Barras de cuota (`.quota-row` + `.quota-bar`) ◆

- **Anatomía:** fila de label + números mono (`usado / límite`) sobre barra 8 px con fill animado.
- **Variantes:** por alcance: global / grupo / usuario / sesión (ADR-0007). Compacta (sidebar) y detallada (consola admin, con desglose).
- **Estados:** sana (<80%, `--money`) · advertencia (≥80%, `--warn` + aviso «te queda ~20% de tu cuota mensual») · bloqueada (100%, `--danger` + ErrorCard `QUOTA` con botón «Solicitar liberación») · carga (skeleton).
- **Responsive:** idéntica; en móvil la versión compacta.
- **A11y:** `role="progressbar"` con `aria-valuenow/min/max` y `aria-label` («Cuota mensual: 82% utilizada»); el cambio a ≥80% se anuncia por `aria-live`.

### 8.12 Taxímetro (`.taximeter`) ◆ — solo Técnico/Admin

- **Anatomía:** cápsula en topbar: label «SESIÓN» + monto USD acumulado en mono verde + detalle de tokens (`12.4k tok`). Tooltip/sheet con desglose: input cacheado/no cacheado/output y % de ahorro por cache.
- **Variantes:** compacto (topbar) · expandido (panel en telemetría de Admin).
- **Estados:** en vivo (incrementa con cada turno; transición suave del número, sin parpadeo) · sesión cerrada (congelado) · sin datos (—) · degradado (si Langfuse no responde: `~` antes del monto + tooltip «costo estimado, telemetría diferida»).
- **Responsive:** móvil: oculto del topbar, disponible en el menú de sesión.
- **A11y:** región con `aria-label`; las actualizaciones NO se anuncian a cada turno (ruido); el desglose es alcanzable por teclado.
- **Regla de rol:** Funcional jamás lo ve. No se renderiza (ni oculto por CSS).

### 8.13 Chips de cache (`.chip-cache`) ◆ — solo Técnico/Admin

- **Anatomía:** mini-cápsula mono 10 px con punto: `HIT` / `MISS` / `WRITE` + tokens opcionales (`HIT · 8.2k`).
- **Estados:** hit (`--money`) · miss (`--warn`) · write (`--info`). Tooltip explica («prefijo servido desde cache: ahorro ~90% en esos tokens»).
- **Ubicación:** junto al metadato de cada turno del agente, al lado del tiempo de respuesta.
- **A11y:** texto siempre presente (no solo punto de color); `aria-label` expandido («cache hit, 8.200 tokens cacheados»).

### 8.14 Tarjeta HITL (`.hitl-card`) ◆ — el componente más crítico del producto

- **Anatomía:** head ámbar («Aprobación requerida» + `shield-check`) → body: descripción de la acción en lenguaje claro · meta en grid (**cliente final · ambiente · agente · solicitante · riesgo**) · payload exacto (mono, scrollable, SIEMPRE visible — no colapsado por defecto) · campo comentario (obligatorio si riesgo crítico) · expiración (`expira en 23 h 12 min`) → foot: «Rechazar» (secondary) + «Aprobar escritura» (primary).
- **Variantes:** pendiente · crítica (riesgo crítico: comentario obligatorio + confirmación reforzada) · irreversible (banda «requiere segunda aprobación»: muestra primera firma y espera la segunda — el mismo usuario no puede dar ambas) · resuelta (aprobada/rechazada: solo lectura con quién/cuándo/comentario) · expirada (atenuada, «Reabrir solicitud»).
- **Estados:** carga (skeleton) · error de envío (error-card inline, decisión no se pierde) · concurrencia (otro aprobador resolvió primero: la tarjeta se actualiza a resuelta y lo anuncia).
- **Responsive:** móvil de primera clase (aprobar desde el celular es caso de uso real): meta en una columna, payload con scroll, botones full-width con primario abajo.
- **A11y:** `<section>` con `aria-labelledby`; riesgo como texto+color; expiración en texto absoluto y relativo; foco inicial en el cuerpo, jamás en «Aprobar» (anti-aprobación accidental).

### 8.15 Tarjeta de escalación (`.escalate-card`) ◆ — marcador `<<<NEEDS_PRO>>>`

- **Anatomía:** ícono `zap` `--accent-alt` + título «Este caso amerita el modelo Pro» + explicación de costo y de que abrirá **una conversación nueva (rama)** + acciones: «Escalar a Pro» (primary) y «Seguir con Flash» (ghost) + tag mono `deepseek-v4-pro`.
- **Variantes:** habilitada · no disponible para el agente (no se renderiza: la escalación es configurable por agente) · bloqueada por cuota (botón disabled + motivo inline + «Solicitar liberación»).
- **Estados:** reposo · loading al escalar (crea la rama) · escalada (reemplazada por nota-enlace «Continuaste en Pro — abrir rama»).
- **Responsive:** botones apilados en móvil.
- **A11y:** no roba el foco al aparecer (es contenido del stream); anuncio `aria-live="polite"`; la decisión es 100% manual — un clic, nunca automática.

### 8.16 ErrorCards (`.error-card`) ◆ — errores accionables

- **Anatomía:** ícono + código mono (`QUOTA` / `VPN_OFFLINE` / `BRIDGE_OFFLINE` / `GATEWAY_OFFLINE`) + **qué pasó** (título) + **por qué** (1 línea, `--ink-dim`) + **qué hacer** (botones).
- **Variantes:** `danger` (bloqueante) · `--warn` (degradado: el sistema sigue con limitaciones — p. ej. modelo alterno activo).
- **Catálogo base:** `QUOTA` («Alcanzaste tu cuota mensual» → Solicitar liberación / Ver consumo) · `VPN_OFFLINE` («Sin conexión al ambiente del cliente» → Reintentar / Guía de VPN) · `BRIDGE_OFFLINE` («El conector local no responde» → Reintentar / Estado del bridge) · `GATEWAY_OFFLINE` («El servicio de IA no está disponible» → Reintentar; el texto del *por qué* se adapta al rol: Funcional sin jerga).
- **Estados:** estática · reintentando (botón loading) · resuelta (se retira con fade).
- **A11y:** `role="alert"` al aparecer; el código de error es seleccionable/copiable (para reportar a soporte).

### 8.17 Chips de archivo adjunto (`.chip`) ◆

- **Anatomía:** ícono por tipo + nombre (ellipsis al medio idealmente) + meta (tamaño o tokens estimados) + cierre. Ver ANEXO-ATTACHMENTS para el pipeline.
- **Estados:** subiendo/extrayendo (`.is-loading`, ícono acento + spinner) · listo (meta = `≈3.1k tok` — transparencia de presupuesto) · error (`.is-error`: tipo rechazado, demasiado grande, N3 detectado — con tooltip del motivo) · truncado (tag `--warn` «truncado» + acceso a vista previa de extracción).
- **Responsive:** los chips envuelven en filas; máx. 2 líneas y «+N más».
- **A11y:** botón de cierre con `aria-label="Quitar adjunto manual-fact.pdf"`; el estado de extracción se anuncia al completarse.

### 8.18 Citas / evidencia (`.cite`) ◆ — DocAgent

- **Anatomía:** bloque con borde izquierdo `--info`: fragmento citado (cursiva, `--ink-dim`) + fuente mono con ícono (`TDN · MATA010 — Parámetros de localización BOL`) como enlace.
- **Variantes:** cita única · grupo numerado `[1] [2]` referenciado desde el texto de la respuesta · **abstención** (variante especial sin fuente: «No encontré evidencia suficiente en TDN/CST para responder esto con confianza» — usa empty-state + sugerencias, jamás texto inventado).
- **Estados:** default · enlace visitado · fuente inaccesible (tag `--warn` «fuente no disponible», la cita se conserva).
- **A11y:** `<blockquote cite="…">`; el número de cita es enlace con `aria-label` («ver fuente 2: TDN MATA010»).

### 8.19 Timeline de workflow (`.wf`) ◆ — sección Workflows (separada del catálogo)

- **Anatomía:** pasos verticales: dot numerado + título + meta mono (duración, costo si el rol lo ve) + conector.
- **Estados por paso:** pendiente (gris) · activo (acento + halo, label «en curso») · completado (check verde, conector verde) · error (rojo + error-card anidada + «Reintentar paso» si el workflow lo permite) · esperando aprobación (dot `shield` ámbar + HITL embebida).
- **Variantes:** vista de ejecución (en vivo) · vista de definición (formulario inicial + pasos previstos).
- **Responsive:** igual en móvil (vertical por naturaleza).
- **A11y:** `<ol>` real; estado de cada paso en texto (`aria-label`: «paso 2 de 5, completado»); progreso global anunciado al cambiar de paso.

### 8.20 Selector de rama (`.branch-sel`) ◆ — «versión 1/2»

- **Anatomía:** cápsula mono `‹ 2/3 ›` junto al mensaje editado. Editar mensaje = rama nueva; la historia jamás se reescribe.
- **Estados:** default · en extremo (flecha disabled) · cambiando (los mensajes posteriores se re-renderizan con fade) · rama con modelo distinto (acompañada del tag «modelo alterno» — stickiness por sesión, ADR-0006).
- **Responsive:** objetivo táctil ≥44 px en móvil (padding invisible).
- **A11y:** `aria-label`(«versión 2 de 3 de este mensaje»); flechas operables por teclado; cambio anunciado con `aria-live="polite"`.

### 8.21 Campana / notificaciones (`.notif-bell`) ◆

- **Anatomía:** botón-ícono con contador rojo; dropdown-panel con lista (ícono semántico + título + tiempo relativo) y «Ver todas».
- **Fuentes de notificación:** aprobación HITL pendiente/resuelta · cuota 80%/100% · liberación concedida · workflow terminado/fallido · (Admin) evals fallando, caída de proveedor.
- **Estados:** sin novedades (sin contador; dropdown con empty-state «Estás al día») · con novedades · crítica (HITL crítica: punto pulsante `live-dot--warn`) · carga (skeletons).
- **Responsive:** dropdown → sheet a pantalla completa en móvil.
- **A11y:** `aria-label`(«Notificaciones, 3 sin leer»); dropdown con `role="menu"` navegable por flechas; nuevas notificaciones NO roban foco.

### 8.22 Empty states (`.empty-state`) ◆

- **Anatomía:** ícono 32 + título + hint (≤42ch) + CTA opcional.
- **Regla de redacción:** decir qué es el lugar Y cómo empezar: «Todavía no hay aprobaciones pendientes. Cuando un agente necesite escribir en Protheus, la solicitud va a aparecer acá.»
- **Variantes:** primera vez (con CTA) · sin resultados de filtro («Sin resultados para “MV_XYZ”» + «Limpiar filtros») · sin permiso suficiente: NO existe — lo que el rol no tiene, no se muestra (§9.7).
- **A11y:** el CTA es foco lógico siguiente tras cargar la vista vacía.

### 8.23 Skeletons (`.skeleton`) ◆

- **Anatomía:** bloques shimmer en la silueta real del contenido (título 50%, líneas 100/80/90%, tabla = filas).
- **Regla:** solo para cargas estimadas >300 ms; nunca mezclar skeleton + spinner en la misma zona; ≤1.5 s esperado — si puede tardar más, mensaje de progreso real.
- **Estados:** shimmer · estático con `prefers-reduced-motion`.
- **A11y:** contenedor `aria-busy="true"`; el contenido real anuncia su llegada si el usuario esperaba (foco no se mueve).

---

## 9. Patrones de interacción

### 9.1 Formularios

- Validación inline al `blur` del campo (no al teclear); revalidación inmediata al corregir.
- Submit con error de servidor: error-card arriba del formulario + foco a ella + campos afectados marcados; **el input del usuario jamás se pierde**.
- Botón de submit con loading durante el round-trip; doble submit bloqueado.
- Campos obligatorios con `*` (`.req`) y nota al pie «* obligatorio»; lo opcional no se marca.

### 9.2 Confirmación destructiva
Dos niveles: (a) destructivo normal (borrar borrador, revocar token) → modal con consecuencia explícita y botón danger; (b) **crítico/irreversible** (eliminar usuario, desactivar agente con sesiones activas, aprobar HITL crítica) → escribir-para-confirmar: el modal exige tipear el identificador exacto (`nombre del usuario`, `APROBAR`); el botón danger permanece deshabilitado hasta coincidencia; Esc no confirma jamás.

### 9.3 Aprobación HITL anti-fatiga
- Cada tarjeta es autosuficiente (payload + contexto completos) — el aprobador nunca navega para entender.
- **Batch con diff resumido:** N escrituras del mismo tipo/cliente/ambiente se agrupan («3 actualizaciones de parámetros MV_* en Comercial Andina S.A. / TEST») con diff por ítem expandible y aprobación por lote, PERO los ítems de riesgo crítico se extraen del lote y se aprueban uno a uno.
- Nunca «aprobar todo» global. Expiración visible siempre. Segunda aprobación para irreversibles: usuarios distintos, ambas firmas quedan en el audit.
- El comentario es obligatorio en críticos: el botón aprueba se habilita recién con texto.

### 9.4 Streaming de respuesta
- El texto del agente entra en stream con cursor de bloque parpadeante al final; auto-scroll solo si el usuario está abajo (si scrolleó arriba: botón «↓ Nuevos mensajes»).
- «Detener» visible durante todo el stream. Tool-calls como líneas de actividad plegadas («consultando TDN…») — el detalle técnico (args/latencia) solo Técnico/Admin.
- Al finalizar: metadatos del turno (hora; + chips de cache, latencia, modelo para Técnico/Admin). Si hubo fallback: tag «modelo alterno» **para todos los roles**.

### 9.5 Carga progresiva
Orden de llegada: shell → datos primarios (lista/chat) → datos secundarios (costos, contadores). Skeletons por zona, no pantalla completa en blanco. Paginación: tablas admin con paginación clásica (auditabilidad); historiales de chat con scroll inverso por ventanas.

### 9.6 Errores accionables
Plantilla obligatoria: **qué pasó** (título humano) + **por qué** (1 línea honesta) + **qué hacer** (1-2 acciones). El código técnico (`VPN_OFFLINE`) visible y copiable para Técnico/Admin; para Funcional va en segundo plano («código para soporte: VPN_OFFLINE»). Degradados ≠ errores: si el sistema sigue funcionando (modelo alterno, telemetría diferida) es `--warn` informativo, no bloqueo rojo.

### 9.7 Permisos: ocultar vs deshabilitar
- **Ocultar** lo que el rol no tiene: Funcional no ve taxímetro, chips de cache ni consola — ni siquiera deshabilitados (deshabilitado = promesa de que existe para vos).
- **Deshabilitar** lo temporalmente imposible para tu rol: aprobar sin comentario en crítica, escalar sin cuota, submit incompleto — siempre con el motivo al lado o en tooltip accesible.
- Nunca un error de permisos como respuesta a un clic en algo visible: si podía clickearlo, era suyo.

### 9.8 Fechas, moneda y números (es-BO)

| Dato | Formato | Ejemplo |
|---|---|---|
| Costo LLM | `USD` + 4 decimales, coma decimal, mono | `USD 0,0042` |
| Montos agregados | 2 decimales, separador de miles `.` | `USD 1.284,50` |
| Tokens | abreviado k/M, 1 decimal | `12,4k tok` |
| Fecha | `dd/mm/aaaa` | `11/06/2026` |
| Fecha-hora | `dd/mm/aaaa HH:mm` (24 h) | `11/06/2026 14:32` |
| Relativo | < 24 h relativo + absoluto en tooltip | `hace 2 h` |
| Porcentaje | sin espacio antes de `%` | `82%` |
| Duración | unidades cortas | `1 min 12 s` |

Implementación: `Intl.NumberFormat('es-BO')` / `Intl.DateTimeFormat('es-BO')`. Números siempre en mono con `tabular-nums` cuando se comparan verticalmente.

---

## 10. Accesibilidad (WCAG 2.1 AA)

- **Contraste:** matriz §5.3; ningún par de texto bajo 4.5:1 (3:1 para ≥24 px o gráficos). Verificación obligatoria al alta de cada brand.
- **Foco:** `:focus-visible` con anillo 2 px `--focus-ring` + offset 2 en TODO interactivo; jamás `outline: none` sin reemplazo. Orden de tabulación = orden visual. Skip-link al contenido en el shell.
- **Teclado:** todo operable sin mouse. Modal: trampa de foco + Esc + retorno al disparador. Tabs con flechas. Dropdown campana con flechas + Esc. Tooltips también en focus.
- **ARIA en componentes clave:** quota `role="progressbar"` · ErrorCard `role="alert"` · toasts `aria-live="polite"` (danger `assertive`) · escalación/branch-sel `aria-live="polite"` · HITL como `section` etiquetada con foco inicial fuera del botón aprobar · streaming: región `aria-live` con anuncio al completar el turno (no token por token).
- **No solo color:** todo estado lleva texto o ícono (chips de cache dicen HIT/MISS, riesgo dice la palabra).
- **Motion:** `prefers-reduced-motion` apaga pulso/shimmer/slide; los spinners de carga permanecen.
- **Táctil:** objetivos ≥44×44 px en móvil (filas, flechas de rama, cierre de chips con padding extendido).
- **Idioma:** `lang="es"`; términos técnicos en otros idiomas marcados cuando aplique.

---

## 11. Responsive

Desktop-first (1200+). Grados de soporte:

| Vista | Móvil 380 | Notas de degradación |
|---|---|---|
| Chat | ✅ completo | sidebar → drawer; taxímetro al menú de sesión; chips de adjunto envuelven |
| Catálogo de agentes | ✅ completo | grid → 1 columna |
| Aprobaciones HITL | ✅ completo (primera clase) | tabla → cards; botones full-width, primario abajo |
| Workflows (ejecución) | ✅ funcional | timeline vertical intacta; formularios 1 columna |
| Ficha técnica (Técnico) | ⚠️ lectura | tabs scrolleables; tablas con scroll-x |
| Consola admin / telemetría | ⚠️ lectura básica | gráficos simplificados; edición se recomienda en desktop |
| Builders (Agent/Skills) | ❌ desktop-only | en móvil: mensaje + enlace «abrir en escritorio» |

Reglas: tablet 768 = desktop con sidebar colapsado; nada de funcionalidad exclusiva de móvil; el ancho de columna de chat (760 px) es constante en desktop aunque la ventana crezca.

---

## 12. i18n (ES → PT-BR)

- **Todos los textos externalizados** desde el primer mockup→código: claves de mensaje, jamás strings hardcodeados. Los mockups muestran ES; el HTML de producción saldrá de catálogos.
- **Reservar +25% de ancho** para PT-BR (y alemán futuro si se diera): botones con `padding` flexible y `white-space: nowrap` consciente; nada de anchos fijos al píxel sobre texto traducible.
- No concatenar fragmentos de oración con variables intercaladas (las traducciones reordenan): usar plantillas con placeholders nombrados («{usuario} aprobó la escritura»).
- Plurales por ICU (`{n, plural, one {...} other {...}}`).
- Lo que NO se traduce: códigos de error (`VPN_OFFLINE`), nombres de modelo (`deepseek-v4-flash`), parámetros Protheus (`MV_PAISLOC`), nombres de tabla (`SX6`).
- Formatos de fecha/número por `Intl` con locale de instancia (es-BO hoy; pt-BR preparado).
- El glosario de terminología (§4.2) se traduce como glosario cerrado (1 término → 1 traducción), no palabra por palabra.

---

## Apéndice A — Checklist de alta de un brand nuevo

1. Dos bloques de tokens (`dark`+`light`) con TODOS los tokens semánticos de §3.1.
2. Matriz de contraste §5.3 completa, todos los pares ≥4.5:1.
3. Verificación visual en `00-styleguide.html` (las 4 combinaciones con el switcher).
4. Logo en claro y oscuro; favicon.
5. Revisión de `--accent-soft` con tinta `--ink` encima (selecciones legibles).
6. Nada de cambios en componentes: si un brand "necesita" tocar un componente, la discusión es de sistema, no de brand.
