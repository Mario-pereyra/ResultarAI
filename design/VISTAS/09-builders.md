# 09 — Construcción (builders)

> **Módulo solo-Admin.** Vistas: **41 — Builder de agentes** ([`mockups/41-builder-agentes.html`](../mockups/41-builder-agentes.html)) y **42 — Builder de skills** ([`mockups/42-builder-skills.html`](../mockups/42-builder-skills.html)).
> Sistema visual: [`DESIGN-SYSTEM.md`](../DESIGN-SYSTEM.md) + [`mockups/tokens.css`](../mockups/tokens.css).
> Decisiones de fondo: ADR-0001/0006 (cache-first: prompts estáticos, toolset fijo por versión, skills horneadas), ADR-0011 (Registro de Prompts: versiones inmutables, publicar exige evals verdes, activar/rollback sin deploy), ADR-0004 (formato de evals), CLAUDE.md §Reglas duras.

---

## Contexto común del módulo

- **Ubicación:** sidebar → capa Admin → «Consola admin» → sección **Construcción**, con dos entradas: **Agentes** (vista 41) y **Skills** (vista 42). Para Técnico y Funcional la sección **no existe** (se oculta, no se deshabilita — DESIGN-SYSTEM §9.7).
- **Modelo mental que la UI debe enseñar:** un agente vive en **versiones inmutables** (`docagent@12`). Editar algo de una versión activa crea un **borrador** (`docagent@13 · borrador`). El borrador se edita libremente; **activarlo** exige pasar el gate de evals (score ≥ 80%, casos `safety` hard-fail individual). Activar archiva la versión anterior; el **rollback** es instantáneo y sin deploy (vive en el Registro de Prompts / ficha del agente, no en el builder).
- **La economía de cache es visible en la UI**, no un detalle de backend: el marco cache-safe del prompt está bloqueado con candado, el toolset es fijo por versión, y las skills se hornean — el builder repite estas reglas donde el Admin podría querer violarlas.
- **Datos siempre ficticios** en mockups: agente DocAgent, admins «mgarcia»/«lucia», skills `bol-localizacion`, cliente de ejemplo «Comercial Andina S.A.».

---

## Vista 41 — Builder de agentes (`41-builder-agentes.html`)

### Propósito

Crear o editar un agente mediante un wizard de 4 pasos (Identidad → Prompt → Tools y políticas → Evals y publicación), garantizando por construcción las reglas duras del producto: prefijo de prompt 100% estático, toolset completo y fijo por versión, HITL heredada e inviolable, y publicación bloqueada sin evals verdes. El resultado de un ciclo completo es una **versión nueva del agente** lista para activarse.

### Quién la ve (roles y capacidades)

| Rol | Acceso |
|---|---|
| **Admin** | Único rol con acceso. Crea/edita borradores, corre evals, activa versiones. TOTP ya exigido en login de Admin. |
| Técnico | No ve la entrada de navegación ni la ruta (server-side guard → redirige a su home). La **ficha técnica** del agente (solo lectura) es su vista, no esta. |
| Funcional | Ídem: no existe para él. |

Jamás se muestra un estado «sin permiso»: lo que el rol no tiene, no se renderiza (§9.7).

### Layout

Desktop-first, contenido máx. **1200 px**. Shell estándar (ai-banner + topbar con breadcrumb y campana). Encabezado de página con identidad del borrador y acciones globales; debajo, la **barra de pasos** (4 ítems con estado de validación); debajo, el panel del paso activo. En el mockup los 4 pasos se muestran **apilados** para documentar todos los estados; en producto se ve un paso a la vez.

```
┌──────────────────────────────────────────────────────────────────┐
│ ai-banner (respuestas generadas por IA…)                         │
├──────────────────────────────────────────────────────────────────┤
│ Consola admin › Construcción › Agentes      [ADMIN mgarcia] [🔔] │
├──────────────────────────────────────────────────────────────────┤
│ CONSOLA ADMIN · CONSTRUCCIÓN                                     │
│ Editar agente — DocAgent          [Descartar] [Guardar borrador] │
│ docagent@13 · BORRADOR   base: docagent@12 (activa)   guardado ⏱ │
├──────────────────────────────────────────────────────────────────┤
│ [✓ 1 Identidad] [● 2 Prompt] [! 3 Tools/políticas] [○ 4 Evals]   │
├──────────────────────────────────────────────────────────────────┤
│ ┌─ Paso activo ────────────────────────────────────────────────┐ │
│ │  campos / candado / tablas según paso                        │ │
│ │  ‹ Anterior            [Guardar borrador] [Siguiente ›]      │ │
│ └──────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

**Barra de pasos:** 4 tarjetas-enlace en grilla. Estados por paso: `pendiente` (número gris) · `activo` (borde + halo `--accent`) · `válido` (check `--money`) · `con errores` (signo `--danger` + subtítulo «N errores»). La navegación entre pasos es **libre** (es un formulario largo, no un túnel); solo «Activar versión» exige los 4 pasos válidos.

### Componentes usados

`tokens.css`: `.ai-banner` · `.badge-rol--admin` · `.notif-bell` · `.kicker` · `.panel` · `.btn` (primary/secondary/ghost/danger, `--loading`, disabled) · `.field`/`.input`/`.select`/`.textarea`/`.checkbox`/`.check-row`/`.field-error`/`.field-hint` · `.table` (matriz de visibilidad, allowlist de tools, suite de evals) · `.tag` (riesgo: bajo=`--money`, medio=`--warn`, alto=`--alt`, crítico=`--danger`; estado de versión: borrador=`--warn`, activa=`--money`) · `.chip` (casos de uso) · `.error-card` (+`--warn`) · `.empty-state` · `.skeleton` · `.toast--ok` · `.overlay`/`.modal` (activación) · `.quota-bar` (progreso de corrida de evals) · `.divider` · utilidades `.mono .muted .faint`.

Andamiaje local del mockup (solo tokens, prefijo `bx-`): topbar/breadcrumb, `bx-steps` (stepper), `bx-lock` (marco cache-safe con candado), pie de paso `bx-stepfoot`, marcos de demo de modal.

### Datos que muestra (campos exactos)

**Encabezado:** nombre del agente · versión borrador (`docagent@13` + tag `BORRADOR`) · versión base (`docagent@12 (activa)`) · marca de autosave («Guardado automáticamente · hace 1 min») · acciones: «Descartar borrador» (ghost→modal destructivo), «Guardar borrador» (secondary).

**Paso 1 · Identidad**
- `nombre` * (texto, ≤40 caracteres) — «DocAgent»
- `identificador` (slug mono, solo lectura, se genera del nombre al crear; inmutable después)
- `descripción corta` * (textarea ≤200; es la que ve el catálogo)
- `casos de uso` (lista de chips agregables; ≥1 recomendado; aparecen como sugerencias en el empty-state del chat)
- `usuario objetivo` (select: Consultores funcionales / Consultores técnicos / Ambos)
- **Matriz de visibilidad por rol** (tabla): filas Funcional / Técnico / Admin; columnas **Aparece en catálogo** (checkbox) · **Puede iniciar sesiones** (checkbox) · **Ve ficha técnica** (checkbox solo en fila Técnico; en Funcional la celda es «—» porque la ficha técnica es capacidad de rol, no de agente; fila Admin: checkboxes marcados y deshabilitados con hint «el Admin siempre ve todo»).
- Regla encadenada: «Puede iniciar sesiones» exige «Aparece en catálogo» — al desmarcar catálogo, la UI desmarca y deshabilita «iniciar sesiones» en esa fila.

**Paso 2 · Prompt**
- `versión base del registro` (select; opciones del Registro de Prompts: `docagent-prompt@12 — activa · publicada 02/06/2026`, `@11 — archivada`, `@10 — archivada`) + hint: editar crea `docagent-prompt@13 (borrador)`; las versiones publicadas son **inmutables** (ADR-0011).
- **Marco cache-safe (BLOQUEADO):** bloque con candado, encabezado «Marco cache-safe — no editable», cuerpo `pre` mono con el prefijo estático (identidad del agente, reglas de citas, política de abstención, marcador de escalación `<<<NEEDS_PRO>>>`). Pie del bloque: «Esta sección garantiza la economía de cache: el prefijo estático se comparte entre todas las sesiones y nunca cambia al inicio del prompt (ADR-0001).» + métrica `prefijo estático: 1.842 tok · cacheado ≈90% de ahorro`.
- **Secciones editables** (después del marco): `Tono y estilo` (textarea) · `Reglas de dominio — Bolivia` (textarea) · `Formato de respuesta` (textarea). Cada una con contador de tokens estimados (`≈210 tok`).
- Nota fija al pie: «Lo dinámico (fecha, usuario, memoria de usuario) entra al FINAL del contexto en runtime — nunca en este editor.»

**Paso 3 · Tools y políticas**
- **Allowlist de tools** (tabla desde el registry de tat-mcp): columnas `incluir` (checkbox) · `tool` (mono) · `descripción` · `tipo` (tag LECTURA/ESCRITURA) · `riesgo` (tag por mapa §8.6) · `HITL` («heredada — obligatoria» para escritura; «—» para lectura). Filas de ejemplo: `tdn_search` (lectura, bajo) · `tdn_get_page` (lectura, bajo) · `cst_search_tickets` (lectura, bajo) · `sx3_dictionary` (lectura, medio) · `protheus_query` (lectura, medio, nota «SQL SELECT solo INBOLSA») · `protheus_rest_write` (escritura, crítico, HITL heredada).
- Nota dura bajo la tabla: «El toolset es **completo y fijo por versión**: los schemas se canonicalizan (`stableToolSchemas()`) y no cambian a mitad de sesión. Cambiar la allowlist forma parte de esta versión nueva.» + «La política HITL viene del registry y **no es editable por agente**: toda escritura a Protheus pasa por aprobación humana.»
- **Escalación:** check-row «Permitir escalación manual a Pro» + select `perfil Pro: deepseek-v4-pro` + hint: el marcador `<<<NEEDS_PRO>>>` muestra la tarjeta; decisión 100% manual, un clic, abre rama nueva. Si se desactiva, la tarjeta no se renderiza en chat.
- **Política de attachments:** check-row «Permitir adjuntos» + checkboxes de tipos aceptados (PDF · DOCX · XLSX · PNG/JPG · TXT/MD) + select `tamaño máximo por archivo` (5/10/20 MB) + hint con niveles de datos: «los adjuntos se extraen a texto y consumen presupuesto de tokens (ANEXO-ATTACHMENTS); contenido N3 (personales/credenciales) jamás se envía al LLM — la UI lo advierte al usuario».

**Paso 4 · Evals y publicación**
- **Suite mínima requerida** (tabla): `categoría` (mono) · `mínimo` · `en suite` · `estado`. Para DocAgent: `smoke` 5→6 ✓ · `citas` 3→4 ✓ · `abstencion` 2→3 ✓ · `safety` 3→3 ✓ (nota: hard-fail individual). Enlace «Editar casos en evals/» (los casos viven en el repo de evals, no acá).
- Acción «Correr evals» + última corrida (`11/06/2026 14:32 · 16 casos · runner v0.9`).
- **Resultado y gate:** score grande en mono (`87%`) + tag `GATE OK ≥80%` (verde) o `GATE BLOQUEADO` (rojo, con error-card `EVALS_GATE` listando los casos fallidos, p. ej. `safety-003 — hard-fail`).
- **Publicación:** estado actual (`borrador`) → botón primario «Activar docagent@13» (habilitado solo con gate verde y pasos 1-3 válidos; deshabilitado con motivo en tooltip accesible). Modal de confirmación con resumen: versión de prompt, toolset (n tools + hash), score de evals, visibilidad; consecuencia: «docagent@12 queda archivada; el rollback es inmediato y sin deploy». Auditoría: quién/cuándo quedan registrados.

### Estados

| Estado | Comportamiento |
|---|---|
| **Carga** | Skeleton del encabezado + del paso activo (silueta real: labels y campos). Stepper visible de inmediato. `aria-busy` en el panel. |
| **Vacío (crear agente)** | Mismo wizard con campos en blanco, paso 1 activo, pasos 2-4 `pendiente`. El slug se genera al tipear el nombre. No hay versión base: el prompt parte de la plantilla del tipo de agente. |
| **Error** | (a) registry de tools inaccesible → error-card `REGISTRY_OFFLINE` en paso 3 con «Reintentar» (el resto del wizard sigue editable); (b) fallo al guardar → error-card `SAVE_FAILED` + reintento; **el input jamás se pierde** (§9.1); (c) runner de evals caído → `EVALS_RUNNER_OFFLINE` (degradado `--warn`: se puede seguir editando, no publicar). |
| **Éxito** | Toast `--ok` «Borrador guardado» (autosave silencioso, toast solo en guardado manual). Al activar: toast «Versión activada — docagent@13 es la versión activa» + redirección a la ficha del agente. |
| **Degradado** | Edición concurrente: lock optimista — el segundo Admin entra en **solo lectura** con error-card `--warn` `EDIT_LOCKED` («lucia está editando este borrador desde hace 4 min») + «Solicitar control». Telemetría caída no afecta al builder. |

### Interacciones y casos borde

- **Validación por paso** al salir del campo (`blur`) y al navegar de paso; el stepper acumula el conteo de errores por paso. «Activar» exige 4/4 válidos + gate verde.
- **Autosave** del borrador cada 30 s y al cambiar de paso; marca de tiempo visible. Salir con cambios sin guardar → confirmación.
- **Editar un agente activo** nunca edita la versión activa: el primer cambio crea el borrador `@n+1` (la UI lo anuncia). Solo puede existir **un borrador por agente**.
- **Slug inmutable** tras la creación (es la clave de versiones, prompts y evals).
- **Toolset:** desmarcar una tool usada por una skill horneada muestra advertencia con la lista de skills afectadas. La fila `protheus_rest_write` lleva su HITL como dato de solo lectura — no existe control para desactivarla.
- **Escalación off** → la tarjeta NEEDS_PRO no se renderiza en chat (variante documentada en §8.15).
- **Matriz:** desmarcar «catálogo» desmarca y deshabilita «iniciar sesiones» (regla encadenada); fila Admin siempre bloqueada en sí.
- **Evals:** correr evals es idempotente y no publica nada; el resultado queda asociado al borrador. Si se edita el prompt después de una corrida verde, el resultado se marca «desactualizado» y el gate vuelve a exigir corrida.
- **Descartar borrador** → modal destructivo normal (§9.2a). **Desactivar un agente con sesiones activas** (acción de la consola, no del builder) es crítico → escribir-para-confirmar (§9.2b).
- **Rollback** no vive acá: enlace a la ficha del agente / Registro de Prompts.

### Diferencias por rol

Ninguna dentro de la vista: es 100% Admin. Lo único que otros roles ven derivado de este builder es: catálogo (según matriz de visibilidad), ficha técnica (Técnico: versión, toolset, score — solo lectura) y la experiencia de chat resultante.

### Móvil

**Desktop-only** (DESIGN-SYSTEM §11). En <768 px la ruta muestra un gate: ícono `monitor` + «El builder es solo escritorio» + «Abrí esta vista en tu computadora para crear o editar agentes.» + botón «Copiar enlace». La entrada de navegación sigue visible para Admin en móvil (la capacidad existe), pero conduce al gate.

### Notas i18n

- Todos los strings por clave de catálogo; el mockup muestra es-BO con voseo («Seleccioná», «agregá»).
- **No se traducen:** nombres de tools (`protheus_rest_write`), modelos (`deepseek-v4-pro`), versiones (`docagent@13`), códigos (`EVALS_GATE`, `SAVE_FAILED`), marcador `<<<NEEDS_PRO>>>`, categorías de eval (`safety`).
- Labels del stepper deben tolerar 2 líneas (+25% PT-BR); los subtítulos de error usan ICU: `{n, plural, one {# error} other {# errores}}`.
- Mensajes con placeholders nombrados: «{usuario} está editando este borrador».
- Fechas/números por `Intl` es-BO (DD/MM/AAAA, coma decimal).

---

## Vista 42 — Builder de skills (`42-builder-skills.html`)

### Propósito

Registrar y mantener **skills versionadas** (bloques de conocimiento/comportamiento reutilizables que se **hornean** en versiones de agente — jamás se cargan a mitad de sesión, regla cache-first). La vista combina: registro (lista con estado y uso), editor/wizard de una skill (contenido versionado, agentes destino), **gate de publicación ≥3 casos de eval** con bloqueo visible, y changelog inmutable por skill.

### Quién la ve (roles y capacidades)

Idéntico a la vista 41: **solo Admin**; Técnico/Funcional no ven la entrada ni la ruta. El campo `owner` de una skill es informativo (quién la mantiene conceptualmente), no otorga permisos: la edición es siempre de Admin.

### Layout

Contenido máx. 1200 px, shell estándar. Dos zonas apiladas: **registro** (tabla) arriba y **editor** abajo (en producto el editor abre al seleccionar/crear; el mockup los muestra apilados con el recordatorio de horneado entre ambos). El editor es una columna principal (contenido + gate) con bloques de ancho completo para agentes destino y changelog.

```
┌──────────────────────────────────────────────────────────────────┐
│ ai-banner                                                        │
├──────────────────────────────────────────────────────────────────┤
│ Consola admin › Construcción › Skills       [ADMIN mgarcia] [🔔] │
├──────────────────────────────────────────────────────────────────┤
│ CONSOLA ADMIN · CONSTRUCCIÓN                                     │
│ Builder de skills                              [+ Crear skill]   │
│ ⚠ Las skills se hornean en la versión del agente — nunca se      │
│   cargan a mitad de sesión.                                      │
├──────────────────────────────────────────────────────────────────┤
│ │ skill │ versión │ owner │ agentes │ estado │ evals │ acciones ││
│ │ bol-localizacion │ @4 │ lucia │ Doc,Val │ ACTIVA │ 5/5 ✓ │ …  ││
│ │ cst-etiquetado   │ @1 │ lucia │ —       │ BORRADOR │ 2/3 ✗ │ …││
├──────────────────────────────────────────────────────────────────┤
│ ┌─ Editar skill — cst-etiquetado@1 · BORRADOR ─────────────────┐ │
│ │ nombre · owner · descripción                                 │ │
│ │ contenido versionado (mono, inmutable al publicar)           │ │
│ │ agentes destino [✓ DocAgent] [ ] ValidationAgent …           │ │
│ │ GATE: ▓▓▓▓▓▓░░░ 2/3 casos — agregá uno más para publicar     │ │
│ │ [tabla de casos de eval]      [Guardar borrador] [Publicar✗] │ │
│ └──────────────────────────────────────────────────────────────┘ │
│ ┌─ Changelog — bol-localizacion ───────────────────────────────┐ │
│ │ ④ @4 ACTIVA 02/06/2026 lucia — feriados 2026 …               │ │
│ └──────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

### Componentes usados

`tokens.css`: `.ai-banner` · `.badge-rol--admin` · `.notif-bell` · `.kicker` · `.panel`/`--flush` · `.table-wrap`+`.table` (registro, casos de eval) · `.tag` (estado: ACTIVA=`--money`, BORRADOR=`--warn`, ARCHIVADA=neutral; evals OK=`--money`, GATE=`--danger`) · `.btn` (primary/secondary/ghost, disabled con motivo) · `.field`/`.input`/`.select`/`.textarea`(`--mono` para contenido)/`.checkbox`/`.check-row` · `.quota-bar` (progreso del gate 2/3) · `.error-card`(`--warn` para recordatorio de horneado y para gate) · `.empty-state` · `.skeleton` · `.toast--ok` · `.wf` (changelog como timeline) · `.modal` (publicación) · utilidades.

Andamiaje local `bx-`: topbar, encabezados, banda de gate, grilla de agentes destino.

### Datos que muestra (campos exactos)

**Registro (tabla):** `skill` (slug mono) · `versión` (mono `@4`) · `owner` (usuario) · `agentes que la usan` (tags por agente; «—» si ninguno) · `estado` (ACTIVA/BORRADOR/ARCHIVADA) · `evals` (`n/min` + tag OK/GATE) · `acciones` (Editar · Changelog). Filas de ejemplo: `bol-localizacion@4` (lucia; DocAgent, ValidationAgent; ACTIVA; 5/5) · `mit-formato@2` (mgarcia; DocAgent; ACTIVA; 4/4) · `sx-diccionario@1` (jperez; ValidationAgent; ACTIVA; 3/3) · `cst-etiquetado@1` (lucia; —; BORRADOR; 2/3 GATE) · `adv-snippets@3` (mgarcia; DevAgent; ARCHIVADA; 3/3).

**Recordatorio permanente (banda `--warn`):** «Las skills se hornean en la versión del agente — nunca se cargan a mitad de sesión. Publicar una skill no cambia ningún agente: hay que crear y activar una versión nueva del agente que la incluya.»

**Editor / wizard de skill:**
- `nombre` * (slug mono al crear; inmutable tras publicar la primera versión)
- `owner` (select de usuarios) · `descripción corta` * (≤140)
- `contenido versionado` * (textarea mono, markdown; encabezado del bloque: `cst-etiquetado@1 · BORRADOR`) + hint: «Publicar congela esta versión. Editar una skill publicada crea `@2`.»
- `agentes destino` (check-rows: DocAgent ✓ · ValidationAgent · DevAgent) + hint por agente marcado: «se incluirá al hornear la próxima versión de DocAgent» + CTA secundaria «Crear borrador de DocAgent» (enlaza a vista 41).
- **Gate de publicación:** barra de progreso `2/3` (estado `--warn`) + mensaje exacto: **«2/3 casos — agregá uno más para poder publicar»**; tabla de casos (`caso` mono · `descripción` · `estado`): `cst-tag-001` ✓ · `cst-tag-002` ✓ · fila fantasma «+ Agregar caso de eval». Con 3/3: barra verde + «3/3 casos — listo para publicar» + botón «Publicar skill» habilitado. El botón deshabilitado lleva el motivo al lado (no solo tooltip).
- **Changelog** (timeline `.wf`, inmutable): por versión: `@n` + estado + fecha + autor + nota de cambio (≤140) + casos de eval de esa versión. Ejemplo `bol-localizacion`: `@4 ACTIVA 02/06/2026 lucia — agrega feriados 2026 y aclara MV_PAISLOC` · `@3 archivada 12/05/2026` · `@2 archivada 28/04/2026` · `@1 archivada 03/04/2026`.

### Estados

| Estado | Comportamiento |
|---|---|
| **Carga** | Tabla con 4-5 filas skeleton; editor con skeleton de campos si se abre directo por URL. |
| **Vacío** | Empty-state en el registro: «Todavía no hay skills. Una skill empaqueta conocimiento reutilizable que se hornea en versiones de agentes.» + CTA «Crear skill». |
| **Error** | Carga del registro falla → error-card `REGISTRY_OFFLINE` + Reintentar. Publicación falla → `PUBLISH_FAILED` + reintento (contenido no se pierde). |
| **Éxito** | Toast `--ok` «Skill publicada — cst-etiquetado@1 quedó activa» **seguido del recordatorio accionable**: «Para que un agente la use, horneá una versión nueva» + CTA. |
| **Degradado** | Runner de evals caído → los casos se listan pero «correr» queda deshabilitado con motivo; el gate no puede ponerse verde sin corrida (no se puentea). |
| **Bloqueado (gate)** | <3 casos: barra `--warn`, mensaje «N/3 casos — agregá …», botón Publicar deshabilitado con motivo visible. Caso fallido: tag `--danger` en el caso + gate bloqueado aunque haya ≥3. |

### Interacciones y casos borde

- **Versionado inmutable:** publicar congela contenido + casos; cualquier edición posterior crea borrador `@n+1`. Solo un borrador por skill.
- **El gate es del sistema, no una sugerencia:** sin 3 casos en verde no existe ruta de publicación (ni API «forzar»). El mensaje siempre dice cuántos faltan.
- **Publicar ≠ desplegar:** la publicación no toca agentes. La UI lo repite en el toast de éxito y junto a «agentes destino». Marcar un agente destino solo declara la intención de horneado.
- **Archivar una skill** usada por versiones activas de agentes: permitido con advertencia — las versiones ya horneadas **no cambian** (la skill vive dentro de ellas); archivar solo impide hornearla en versiones nuevas.
- **Quitar casos de eval** de una versión publicada: imposible (inmutable). En un borrador, si el conteo cae bajo 3, el gate vuelve a bloquearse en vivo.
- **Renombrar** una skill publicada: no (el slug es la clave); la descripción y el owner sí son editables sin nueva versión (metadatos, no contenido).
- **Eliminar borrador** → modal destructivo normal. Eliminar una skill con historial: no existe; se archiva.
- **Changelog** solo crece; cada entrada registra autor y fecha del sistema (no editables).
- **Concurrencia:** mismo lock optimista que la vista 41 (`EDIT_LOCKED`).

### Diferencias por rol

Ninguna interna (solo Admin). Derivados: el Técnico ve en la ficha técnica del agente qué skills están horneadas en la versión activa (solo lectura); el Funcional no ve el concepto «skill» en absoluto.

### Móvil

Desktop-only, mismo gate que la vista 41 («El builder es solo escritorio» + copiar enlace). Las aprobaciones/uso de agentes en móvil no se ven afectados.

### Notas i18n

- Claves de catálogo; voseo es-BO en mockup.
- **No se traducen:** slugs de skill (`bol-localizacion`), versiones (`@4`), nombres de agentes-producto (DocAgent), códigos (`PUBLISH_FAILED`), ids de casos (`cst-tag-001`).
- Mensaje del gate con ICU y placeholders: `{n}/{min} casos — {faltan, plural, one {agregá uno más} other {agregá # más}} para poder publicar`.
- La banda de recordatorio es texto largo: prever +25% sin truncar (envuelve, no ellipsis).
- Columnas de tabla con anchos fluidos; «agentes que la usan» envuelve tags en 2 líneas máx. + «+N».
