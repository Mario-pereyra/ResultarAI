# 04 — Workflows (sección propia)

> **Estado:** v1.0 — especificación de diseño del módulo Workflows.
> **Fuente visual:** [`../DESIGN-SYSTEM.md`](../DESIGN-SYSTEM.md) + [`../mockups/tokens.css`](../mockups/tokens.css).
> **Mockups de este módulo:**
> [`15-workflows-lista.html`](../mockups/15-workflows-lista.html) ·
> [`16-workflow-form.html`](../mockups/16-workflow-form.html) ·
> [`17-workflow-run.html`](../mockups/17-workflow-run.html) ·
> [`18-workflow-result.html`](../mockups/18-workflow-result.html) ·
> [`19-workflow-historial.html`](../mockups/19-workflow-historial.html)
> **Relación:** UX-SPEC (HITL §5, errores accionables), ADR-0006 (modelos), ADR-0007/0010 (cuotas), DESIGN-SYSTEM §8.19 (timeline `.wf`), §8.14 (tarjeta HITL), §9.8 (formatos es-BO).

---

## 0. Decisiones de módulo (aplican a las 5 vistas)

### 0.1 Sección de primer nivel (decisión D6)

Workflows es una entrada **propia del sidebar**, separada del catálogo de agentes. Un workflow no es "un agente con pasos": es un **proceso determinista con formulario tipado, pasos predefinidos y un artefacto de salida verificable** (informe GAP, YAML validado, checklist propuesto). El usuario no conversa con él: lo configura, lo ejecuta y recibe un resultado. Mezclarlo con el catálogo confundiría los dos modelos mentales.

### 0.2 Modelo conceptual

| Concepto | Definición | Identidad |
|---|---|---|
| **Workflow (definición)** | Proceso versionado e inmutable por versión: formulario tipado + secuencia de pasos + artefacto de salida. Publicado por Admin. | slug + versión, p. ej. `validacion-facturacion@1.4` (mono) |
| **Corrida (run)** | Una ejecución concreta de una versión, con parámetros congelados al ejecutar. | `WF-AAAA-NNNN`, p. ej. `WF-2026-0347` (mono) |
| **Paso** | Unidad de la secuencia. Determinista; puede invocar agentes/tools internamente, pero el orden no lo decide el LLM. | índice `n de N` |
| **Hallazgo** | Resultado unitario de una validación: regla + evidencia + severidad + recomendación. | código de regla, p. ej. `FAT-001` (mono) |

### 0.3 Máquina de estados

**Corrida:** `configurando → en_ejecucion → (pausada_hitl ⇄ en_ejecucion) → completada | error | cancelada`.
**Paso:** `pendiente → en_curso → completado | pausado_hitl | error`. Un paso en `error` puede reintentarse (si el workflow lo permite) y la corrida continúa desde ese paso — nunca se re-ejecutan pasos completados.

Etiquetas de estado (texto + color, nunca solo color):

| Estado corrida | Tag | Texto UI |
|---|---|---|
| en ejecución | `tag--accent` | `EN EJECUCIÓN` |
| pausada (HITL) | `tag--warn` | `ESPERANDO APROBACIÓN` |
| completada | `tag--money` | `COMPLETADA` |
| error | `tag--danger` | `ERROR` |
| cancelada | `tag` (neutral) | `CANCELADA` |

### 0.4 Severidad de hallazgos (escala propia del módulo)

| Severidad | Tag | Nota |
|---|---|---|
| crítico | `tag--danger` | bloquea operación del módulo validado |
| alto | `tag--alt` | mismo acento cálido que riesgo alto HITL (§8.6) |
| medio | `tag--warn` | |
| bajo | `tag` (neutral) | un hallazgo bajo **no** usa verde: sigue siendo una desviación |
| cumple / OK | `tag--money` | el verde queda reservado para "cumple" |

Coincide con el mapa de riesgo HITL salvo en "bajo": en HITL el riesgo bajo es verde (acción segura); acá un hallazgo bajo es neutral (desviación menor). Decisión consciente para no leer hallazgos como éxitos.

### 0.5 Roles y permisos del módulo

- **Disponibilidad por rol:** el Admin habilita cada workflow para uno o más roles (configuración de instancia). Lo no habilitado **no se renderiza** (§9.7 — ocultar, no deshabilitar).
- **Costos (estimación, taxímetro, costo de corrida):** solo Técnico/Admin. Funcional ve duración, nunca dinero ni tokens.
- **Visibilidad de corridas:** cada usuario ve sus propias corridas; Admin ve todas (en Historial gana el filtro «Usuario»).
- **Cancelar / re-ejecutar:** dueño de la corrida o Admin.
- **Aprobaciones HITL dentro de un workflow:** siguen el circuito normal de Aprobaciones (UX-SPEC §5); el workflow solo enlaza a la tarjeta, no la reimplementa.

### 0.6 Rutas y tiempo real

- `/workflows` (lista) · `/workflows/:slug/nuevo` (formulario) · `/workflows/runs/:id` (ejecución) · `/workflows/runs/:id/resultado` · `/workflows/historial`.
- La ejecución se sigue por stream (SSE/WSS). Si la conexión cae, la corrida **continúa en el servidor**: la vista muestra «reconectando…» y se re-sincroniza al volver. Al terminar una corrida con la vista cerrada, notifica por campana (§8.21: «workflow terminado/fallido»).
- Cuotas: se evalúan **antes** de ejecutar (ADR-0007). Sin cuota → ErrorCard `QUOTA` en el formulario, nunca a mitad de corrida sin aviso.

### 0.7 Datos de ejemplo canónicos (ficticios)

Cliente final «Comercial Andina S.A.» (también «Ferretería El Tornillo S.R.L.», «Agroindustrias Valle Alto S.A.»), usuaria «lucia», workflow ejemplar «Validación de módulo Facturación», checklist `checklist-fact-v3.xlsx`, corridas `WF-2026-0341/0347/0348`, montos pequeños (`USD 0,18`).

---

## 1. Vista 15 — Lista de workflows (`15-workflows-lista.html`)

### Propósito
Punto de entrada del módulo: mostrar los workflows que el rol del usuario tiene habilitados, con lo necesario para decidir cuál ejecutar (qué produce, cuánto tarda, qué requiere, qué tan maduro es) y el historial reciente propio de cada uno.

### Quién la ve (roles y capacidades)
- **Todos los roles** con ≥1 workflow habilitado. Si un rol no tiene ninguno, la entrada «Workflows» del sidebar **no aparece**.
- **Funcional:** cards sin costo estimado.
- **Técnico:** + costo estimado por corrida y versión del workflow en mono.
- **Admin:** + botón «Gestionar workflows» (enlace a la consola admin; la gestión NO vive en esta vista).

### Layout

Encabezado de página (kicker + h1 + descripción; acción Admin arriba a la derecha) y grid de cards `repeat(auto-fill, minmax(320px, 1fr))`.

```
┌──────────────────────────────────────────────────────────────┐
│ WORKFLOWS                              [Gestionar workflows]*│
│ Procesos deterministas…                          (*solo Admin)│
├────────────────────┬────────────────────┬────────────────────┤
│ ┌────────────────┐ │ ┌────────────────┐ │ ┌────────────────┐ │
│ │ icono  ESTABLE │ │ │ icono     BETA │ │ │ icono  ESTABLE │ │
│ │ Nombre         │ │ │ Nombre         │ │ │ Nombre         │ │
│ │ → produce: …   │ │ │ → produce: …   │ │ │ → produce: …   │ │
│ │ ≈10 min ≈USD…* │ │ │ ≈6 min         │ │ │ ≈3 min         │ │
│ │ req: bridge,XLSX│ │ │ req: bridge    │ │ │ req: bridge ⚠ │ │
│ │ ── historial ── │ │ │ sin corridas   │ │ │ WF-0322 ✓ …    │ │
│ │ [Configurar]   │ │ │ [Configurar]   │ │ │ [Configurar]   │ │
│ └────────────────┘ │ └────────────────┘ │ └────────────────┘ │
└────────────────────┴────────────────────┴────────────────────┘
```

### Componentes usados
`.panel` (card), `.kicker`, `.tag` / `--warn` / `--money`, `.btn--secondary`, `.btn--ghost` (Admin), `.live-dot` / `--off`, `.chip` (requisitos), `.skeleton`, `.empty-state`, íconos lucide: `list-checks`, `arrow-right-circle`, `clock`, `circle-dollar-sign`, `cable`, `file-spreadsheet`, `check`, `x`.

### Datos que muestra (campos exactos por card)
1. **Nombre** del workflow (h3, enlace a `/workflows/:slug/nuevo`).
2. **Estado de madurez:** `ESTABLE` (tag neutral) | `BETA` (tag--warn). BETA agrega hint «resultados en validación — revisalos con más cuidado».
3. **Versión** activa en mono (`v1.4`) — solo Técnico/Admin.
4. **Qué produce:** una línea con ícono («Produce: informe GAP exportable (PDF/CSV)»).
5. **Duración estimada:** mono, `≈ 10 min` (mediana de corridas recientes; si no hay datos, estimación del Admin).
6. **Costo estimado:** mono money, `≈ USD 0,18` — solo Técnico/Admin.
7. **Requisitos:** chips con estado en vivo cuando aplica: `bridge` (live-dot verde «conectado» / gris-warn «sin conexión»), `checklist XLSX` (estático: se valida en el formulario), `archivo MIT`, etc.
8. **Historial reciente propio:** últimas 2 corridas del usuario: id mono + fecha relativa + estado con ícono (`WF-2026-0347 · hace 1 día · ✓ completada`). Cada línea enlaza al resultado. Sin corridas → «Sin corridas tuyas todavía».
9. **CTA:** «Configurar» (`.btn--secondary` — no hay primario por card: nunca más de un primario por zona, §6.2).

### Estados
- **Carga:** grid con 3 cards skeleton (título 50% + 3 líneas + botón).
- **Vacío:** `.empty-state` — «Todavía no hay workflows habilitados para tu rol. Pedile al administrador que habilite los que necesités.» (sin CTA para no-Admin; Admin ve CTA «Gestionar workflows»).
- **Error de carga:** ErrorCard genérica con «Reintentar».
- **Éxito:** grid normal.
- **Degradado:** si el estado del bridge no se puede consultar, el chip muestra `bridge` con live-dot gris y tooltip «estado desconocido — se verifica al configurar»; la card no se bloquea.

### Interacciones y casos borde
- Click en card completa NO navega: solo el título y el botón «Configurar» (las cards tienen múltiples enlaces internos — historial — y un wrapper-link los rompería, §8.5).
- Requisito `bridge` sin conexión: la card sigue operable («Configurar» habilitado) — el bloqueo real ocurre en el formulario con error accionable. Acá solo se anticipa con el live-dot apagado + texto «sin conexión».
- Workflow BETA: nunca se oculta por ser beta; el tag + hint son la advertencia.
- Historial propio con corrida en ejecución: la línea muestra `EN EJECUCIÓN` y enlaza a la vista de ejecución (no al resultado).

### Diferencias por rol
| Elemento | Funcional | Técnico | Admin |
|---|---|---|---|
| Cards habilitadas para su rol | ✅ | ✅ | ✅ (todas) |
| Costo estimado | — | ✅ | ✅ |
| Versión del workflow (mono) | — | ✅ | ✅ |
| Botón «Gestionar workflows» | — | — | ✅ |

### Móvil
✅ funcional. Grid → 1 columna; chips de requisitos envuelven; historial reciente intacto. Touch targets ≥44 px en líneas de historial.

### Notas i18n
- Claves externalizadas; plurales ICU en historial («{n, plural, one {corrida} other {corridas}}»).
- No traducir: ids de corrida, `BETA`/`ESTABLE` se traducen como glosario cerrado, nombres de archivo.
- Reservar +25% en el botón «Configurar» (PT-BR «Configurar» coincide, pero el patrón es general).

---

## 2. Vista 16 — Formulario de workflow (`16-workflow-form.html`)

### Propósito
Configurar una corrida del workflow elegido con un **formulario tipado** (los campos los define la versión del workflow): contexto cliente/ambiente, insumos (checklist XLSX), parámetros, y ejecutar con estimación visible. Todo error se previene acá: la corrida no debe fallar por configuración.

### Quién la ve (roles y capacidades)
Roles con el workflow habilitado. Funcional sin costo estimado. El formulario es idéntico entre roles en campos y validación.

### Layout

Dos columnas en desktop: formulario (máx. 560 px, §6.1) + panel lateral «Resumen de ejecución» (340 px, sticky).

```
┌───────────────────────────────────────────────────────────────┐
│ WORKFLOW · ESTABLE · v1.4                                      │
│ Validación de módulo Facturación                               │
│ Produce: informe GAP …                                         │
├──────────────────────────────────┬────────────────────────────┤
│ Cliente final *      [select ▾]  │ RESUMEN DE EJECUCIÓN       │
│ Ambiente *           [select ▾]  │ duración    ≈ 10 min       │
│   ● bridge conectado · 38 ms     │ costo*      ≈ USD 0,18     │
│ Checklist XLSX *                 │ pasos previstos (1-5)      │
│   [── zona de arrastre ──]       │ cuota mensual ▓▓▓░ 62%     │
│   [chip checklist-fact-v3.xlsx]  │                            │
│ Módulo *             [select ▾]  │ (*solo Técnico/Admin)      │
│ País / localización  [select ▾]  │                            │
│ Comentario (opcional)[textarea]  │                            │
├──────────────────────────────────┴────────────────────────────┤
│ * obligatorio        [Cancelar]  [► Ejecutar workflow]        │
└───────────────────────────────────────────────────────────────┘
```

### Componentes usados
`.field` + `.input/.select/.textarea`, `.chip` (estados del adjunto, ANEXO-ATTACHMENTS), `.tag` (badges de ambiente), `.live-dot`, `.error-card` (`BRIDGE_OFFLINE`, `QUOTA`), `.btn--primary --lg`, `.btn--ghost`, `.quota-bar` (compacta), `.wf` en variante «definición» (pasos previstos), `.field-error`, `.field-hint`.

### Datos que muestra (campos exactos)
**Formulario (definidos por `validacion-facturacion@1.4`):**
1. **Cliente final** * — select; solo clientes con bridge configurado para la instancia. Placeholder «Seleccioná un cliente…».
2. **Ambiente** * — select encadenado al cliente (se resetea al cambiar cliente y lo anuncia, §8.3). Cada opción con badge: `PROD` (`tag--danger`), `VAL` (`tag--info`), `DEV` (`tag` neutral). Bajo el select, **estado del bridge en vivo**: `● bridge conectado · 38 ms · tat-mcp v0.9.2` (live-dot verde) o variante caída (ErrorCard `BRIDGE_OFFLINE`).
3. **Checklist XLSX** * — zona de arrastre + botón «Elegir archivo». Acepta `.xlsx` (XLSM rechazado por macros — ANEXO §4.2; máx. 10 MB). El archivo procesado se muestra como `.chip`:
   - subiendo/extrayendo: `.is-loading` + «extrayendo reglas…»
   - listo: nombre + meta `42 reglas · ≈3,1k tok` (tokens solo Técnico/Admin)
   - error: `.is-error` + motivo en `.field-error` («Formato .xlsm rechazado: contiene macros. Guardalo como .xlsx.»)
4. **Módulo** * — select (`SIGAFAT — Facturación` preseleccionado por el workflow; otros: SIGACOM, SIGAEST…).
5. **País / localización** — select, default `BOL — Bolivia (MV_PAISLOC=BOL)`. Hint: «Determina el set de reglas de localización del checklist.»
6. **Comentario para el historial** — textarea opcional; viaja a la trazabilidad de la corrida.

**Panel resumen:** workflow + versión (mono), duración estimada, **costo estimado** (money mono, solo Técnico/Admin), lista de pasos previstos (timeline `.wf` compacta sin estados), barra de cuota mensual del usuario (compacta).

### Estados
- **Carga:** skeleton del formulario (labels + inputs) — solo si la definición tarda >300 ms.
- **Vacío:** n/a (siempre hay definición).
- **Error:**
  - validación inline al `blur` (§9.1): «Seleccioná un ambiente para continuar», borde `--danger`;
  - `BRIDGE_OFFLINE` (warn → danger según contexto): ErrorCard bajo el campo ambiente con «Reintentar» y «Estado del bridge»; el CTA se deshabilita;
  - `QUOTA` al intentar ejecutar sin cuota: ErrorCard arriba del pie con «Solicitar liberación» / «Ver consumo»;
  - error de servidor al ejecutar: ErrorCard arriba del formulario, foco a ella, **el input no se pierde** (§9.1).
- **Éxito:** al ejecutar, redirección inmediata a `/workflows/runs/:id` (vista 17). El botón pasa a `.btn--loading` durante el round-trip; doble submit bloqueado.
- **Degradado:** latencia del bridge > umbral (p. ej. 800 ms): live-dot ámbar + «conexión inestable — la corrida puede tardar más»; ejecutar sigue permitido.

### Interacciones y casos borde
- **CTA deshabilitado con razón visible** (§9.7): junto al botón, texto `--ink-dim` enumerando lo que falta: «Para ejecutar falta: checklist XLSX». Nunca un botón muerto sin explicación.
- Ambiente `PROD` seleccionado: nota warn permanente bajo el campo: «Ambiente productivo: el workflow solo lee. Cualquier escritura propuesta requerirá aprobación.»
- Cambiar cliente con ambiente ya elegido: resetea ambiente + chip de bridge; anuncio `aria-live="polite"`.
- XLSX con 0 reglas reconocibles: chip `.is-error` + «El archivo no contiene reglas reconocibles. Descargá la plantilla.» (enlace a plantilla).
- Archivo > 10 MB o tipo real ≠ extensión (magic bytes): rechazo inmediato con motivo en el chip.
- El usuario abandona la página con el formulario a medias: sin autosave en v1 (configuración es barata); confirmación nativa solo si hay archivo ya subido.
- Bridge se cae entre validación y submit: el servidor revalida; vuelve `BRIDGE_OFFLINE` como error de submit.

### Diferencias por rol
| Elemento | Funcional | Técnico | Admin |
|---|---|---|---|
| Campos y validación | idénticos | idénticos | idénticos |
| Costo estimado (resumen) | — | ✅ | ✅ |
| Tokens del checklist en el chip | — (solo «42 reglas») | ✅ `≈3,1k tok` | ✅ |
| Versión del workflow visible | — | ✅ | ✅ |

### Móvil
✅ funcional: 1 columna, el resumen pasa debajo del formulario (antes del CTA); zona de arrastre se vuelve botón «Elegir archivo» (el drag no existe en táctil); CTA full-width abajo (zona del pulgar).

### Notas i18n
- Placeholders y errores por catálogo; plantillas con placeholders nombrados («Para ejecutar falta: {lista}»).
- No traducir: `MV_PAISLOC`, `SIGAFAT`, `BRIDGE_OFFLINE`, `QUOTA`, nombres de archivo.
- El texto del estado del bridge concatena valores técnicos (`38 ms`) por plantilla, no por concatenación de fragmentos.

---

## 3. Vista 17 — Ejecución en vivo (`17-workflow-run.html`)

### Propósito
Seguir una corrida en tiempo real: qué paso va, qué ya pasó, dónde se pausó (HITL) o falló, con log amigable por paso y la posibilidad de cancelar. La vista debe transmitir que el proceso es **determinista y auditable** — nada de "magia en progreso".

### Quién la ve (roles y capacidades)
Dueño de la corrida (cualquier rol) y Admin. Técnico/Admin ven además metadatos técnicos en el log (latencias, conteos de consulta). Cancelar: dueño o Admin.

### Layout

Encabezado con identidad de la corrida + progreso global; timeline vertical `.wf` como cuerpo único.

```
┌──────────────────────────────────────────────────────────────┐
│ EN EJECUCIÓN   WF-2026-0348                [Cancelar ejecución]│
│ Validación de módulo Facturación                              │
│ Comercial Andina S.A. · VAL · iniciada 14:32 · 2 min 41 s     │
│ Paso 4 de 5 ▓▓▓▓▓▓▓░░░ · regla 23 de 42                       │
├──────────────────────────────────────────────────────────────┤
│ ✓ 1 Conexión al ambiente            12 s                      │
│ │   ▸ log (colapsado)                                         │
│ ✓ 2 Lectura del checklist           3 s · 42 reglas           │
│ ✓ 3 Consulta de parámetros          1 min 04 s · 38 consultas │
│ ◌ 4 Análisis de diferencias         en curso · regla 23/42    │
│ │   ▾ log: 14:34:12 comparando MV_SIMB1…                      │
│ ○ 5 Generación del informe GAP      pendiente                 │
└──────────────────────────────────────────────────────────────┘
   Variantes de paso: ⛨ pausado HITL (link a tarjeta) · ✕ error + reintentar
```

### Componentes usados
`.wf` + `.wf-step` (`is-done`, `is-active`, `is-error` + variante local pausado-HITL con dot `shield` warn), `.tag` (estado de corrida), `.error-card` (error de paso), `.btn--secondary/--danger`, `.modal` (confirmar cancelación), `<details>` nativo para logs colapsables, `.live-dot`, barra de progreso (mismas primitivas de `.quota-bar` con fill `--accent`), íconos `check`, `shield-check`, `x`, `clock`, `rotate-ccw`.

### Datos que muestra (campos exactos)
**Encabezado:** tag de estado de corrida (§0.3) · id `WF-2026-0348` (mono) · nombre y versión del workflow · cliente final · ambiente (badge) · «iniciada 11/06/2026 14:32» · tiempo transcurrido en vivo (mono) · usuario dueño (solo si el viewer es Admin) · botón «Cancelar ejecución».
**Progreso global:** «Paso {n} de {N}» + barra + sub-progreso del paso activo si lo reporta («regla 23 de 42»).
**Por paso:** número/ícono de estado · título · meta mono (duración real al completar; «en curso» + sub-progreso en activo; «pendiente» en futuros) · log colapsable.
**Log amigable (por paso):** líneas con hora `HH:mm:ss` + evento en lenguaje claro («conectado al bridge (38 ms)», «42 reglas cargadas del checklist», «consultando SX6: MV_PAISLOC…»). Detalle técnico extra (args, latencias por consulta) solo Técnico/Admin.

**Paso pausado (HITL):** dot `shield` ámbar + título + «pausado · esperando aprobación» + panel embebido: descripción en claro («El workflow propone corregir 2 parámetros MV_* y necesita aprobación humana»), id de solicitud `HITL-0921` (mono), expiración («expira en 23 h 12 min»), botón «Ver tarjeta de aprobación» (lleva a Aprobaciones; la tarjeta NO se duplica acá).
**Paso en error:** dot `✕` rojo + ErrorCard anidada: código (`BRIDGE_TIMEOUT`), qué pasó, por qué, acciones «Reintentar paso» / «Ver log» + nota «al reintentar, la corrida continúa desde este paso».

### Estados
- **Carga:** skeleton del encabezado + 5 dots grises (solo al abrir una corrida existente).
- **Vacío:** n/a.
- **Error:** (a) de paso → dentro de la timeline (arriba); (b) de conexión al stream → banner warn «reconectando…» con live-dot ámbar; la corrida sigue en el servidor; al reconectar, la timeline se re-sincroniza de golpe (sin replays animados).
- **Éxito:** al completar el último paso, banner ok + CTA primario «Ver resultado» (→ vista 18); auto-redirección NO (el usuario puede estar leyendo el log).
- **Degradado:** si el sub-progreso no está disponible, el paso activo muestra solo el spinner + «en curso» — jamás una barra inventada.

### Interacciones y casos borde
- **Cancelar:** modal de confirmación (§9.2 nivel a): «¿Cancelar la ejecución? Se detiene el paso en curso. Lo completado queda en el historial; no se genera informe.» Botón danger «Cancelar ejecución» / ghost «Seguir ejecutando». Esc no confirma. Cancelar con HITL pendiente también retira la solicitud de Aprobaciones (se registra en audit).
- **HITL aprobada:** el paso se reanuda solo; anuncio `aria-live="polite"` («paso 4 reanudado»).
- **HITL expirada:** el paso pasa a error con código `HITL_EXPIRED` y acción «Volver a solicitar aprobación».
- **Reintentar paso:** máximo de reintentos definido por workflow (default 2); agotados, la corrida queda en `error` con «Re-ejecutar workflow» (corrida nueva, parámetros congelados — enlaza al flujo de la vista 19).
- Usuario cierra la pestaña: la corrida continúa; campana notifica al terminar.
- Dos pestañas con la misma corrida: ambas se sincronizan por stream (lectura pura, sin conflicto).
- Auto-scroll del log activo solo si el usuario está abajo (patrón §9.4).

### Diferencias por rol
| Elemento | Funcional | Técnico | Admin |
|---|---|---|---|
| Timeline y logs amigables | ✅ | ✅ | ✅ |
| Detalle técnico del log (latencias, args) | — | ✅ | ✅ |
| Costo parcial acumulado en encabezado | — | ✅ `USD 0,14 · 61,0k tok` | ✅ |
| Ver corridas ajenas / cancelarlas | — | — | ✅ |

### Móvil
✅ funcional (el timeline vertical es nativamente móvil): encabezado apila tags; «Cancelar ejecución» full-width al fondo del encabezado; logs colapsados por defecto (igual que desktop).

### Notas i18n
- Estados de paso como claves («paso {n} de {N}, {estado}») — también alimentan `aria-label` del `<ol>`.
- Horas con `Intl.DateTimeFormat('es-BO')`; duraciones con unidades cortas (`1 min 04 s`).
- No traducir códigos (`BRIDGE_TIMEOUT`, `HITL_EXPIRED`) ni ids (`HITL-0921`).

---

## 4. Vista 18 — Resultado (`18-workflow-result.html`)

### Propósito
Presentar el artefacto de salida —el informe GAP— de forma ejecutiva primero (conteos por severidad + resumen) y detallada después (tabla de hallazgos con evidencia y recomendación), con export y trazabilidad completa. Es el documento que el consultor lleva al cliente: la credibilidad del producto se juega acá.

### Quién la ve (roles y capacidades)
Dueño de la corrida y Admin. Export disponible para todos los que la ven. Costo y tokens de la corrida: solo Técnico/Admin.

### Layout

```
┌──────────────────────────────────────────────────────────────┐
│ COMPLETADA  WF-2026-0347        [PDF] [CSV] [Re-ejecutar]    │
│ Informe GAP — Validación de módulo Facturación               │
├──────────────────────────────────────────────────────────────┤
│ RESUMEN EJECUTIVO                                             │
│ ┌────────┬────────┬────────┬────────┬────────┐               │
│ │ 1      │ 3      │ 5      │ 2      │ 31     │               │
│ │ CRÍTICO│ ALTO   │ MEDIO  │ BAJO   │ CUMPLEN│               │
│ └────────┴────────┴────────┴────────┴────────┘               │
│ Párrafo ejecutivo (3-4 líneas)…                               │
├──────────────────────────────────────────────────────────────┤
│ [Todos 11] [Crítico 1] [Alto 3] [Medio 5] [Bajo 2]  ← tabs   │
│ ┌─────────┬───────────────┬───────────┬───────────────────┐  │
│ │ REGLA   │ EVIDENCIA     │ SEVERIDAD │ RECOMENDACIÓN     │  │
│ │ FAT-001 │ actual/esperado│ CRÍTICO  │ …                 │  │
│ └─────────┴───────────────┴───────────┴───────────────────┘  │
├──────────────────────────────────────────────────────────────┤
│ TRAZABILIDAD  quién·cuándo·cliente·ambiente·checklist·costo* │
└──────────────────────────────────────────────────────────────┘
```

### Componentes usados
`.panel`, tiles de conteo (mono `--fs-display` + tag de severidad), `.tabs` (filtro por severidad con contadores), `.table-wrap` + `.table`, `.tag` por severidad (§0.4), `.btn--secondary` (exports), `.btn--ghost` (re-ejecutar), `.chip-cache` (Técnico/Admin), grid de metadatos estilo `hitl-card__meta`, `.empty-state` (variante 0 hallazgos), íconos `download`, `rotate-ccw`, `check`, `quote`.

### Datos que muestra (campos exactos)
**Encabezado:** tag `COMPLETADA` + id mono + título «Informe GAP — {workflow}» + fecha-hora de fin + acciones: «Exportar PDF», «Exportar CSV», «Re-ejecutar» (mismos parámetros — abre el modal de la vista 19).
**Resumen ejecutivo:** 5 tiles: crítico / alto / medio / bajo / cumplen, con número grande mono y label-tag. Línea de totales: «42 reglas evaluadas · 31 cumplen · 11 hallazgos». Párrafo ejecutivo generado (3-4 líneas, lenguaje claro, sin jerga interna) — lleva la marca implícita del ai-banner: es contenido generado.
**Tabla de hallazgos** (orden default: severidad desc, luego código de regla):
| Columna | Contenido |
|---|---|
| Regla | código mono (`FAT-001`) + nombre corto de la regla |
| Evidencia | dos líneas mono: `actual: MV_PAISLOC = ""` / `esperado: "BOL"` (+ origen `SX6` como tag-outline) |
| Severidad | tag §0.4 con palabra |
| Recomendación | texto accionable en claro («Configurá MV_PAISLOC=BOL en SX6 antes de emitir facturas») |
**Trazabilidad** (grid dt/dd): Ejecutado por (`lucia`) · Inicio / Fin (`11/06/2026 14:32` / `14:41`) · Duración (`9 min 42 s`) · Cliente final · Ambiente (badge) · Checklist (`checklist-fact-v3.xlsx · v3 · sha256 a41f…9c2e`) · Workflow (`validacion-facturacion@1.4`) · Corrida (`WF-2026-0347`) · Comentario del formulario (si hubo) · **Costo** (`USD 0,21 · 84,2k tok` + chips de cache) — solo Técnico/Admin. Cierra con la advertencia: «Informe generado por IA — verificá cada hallazgo antes de aplicar cambios en el cliente.»

### Estados
- **Carga:** skeleton de tiles + 4 filas de tabla.
- **Vacío (0 hallazgos):** los tiles muestran 0/0/0/0/42 y la tabla se reemplaza por panel ok: «La parametrización cumple las 42 reglas del checklist v3.» con ícono check `--money`. El export sigue disponible (un informe "todo cumple" también se entrega al cliente).
- **Error:** corrida en `error` no tiene esta vista completa: muestra encabezado + ErrorCard con enlace a la ejecución (vista 17) para ver el paso fallido; si hubo hallazgos parciales, banner warn «informe parcial: la corrida no terminó» encima de la tabla.
- **Éxito:** vista completa.
- **Degradado:** export en generación: botón con `.btn--loading`; si el servicio de export falla, toast `--danger` con reintentar (la vista no se bloquea).

### Interacciones y casos borde
- Tabs de severidad filtran la tabla client-side; «Todos» activo por defecto; el filtro no altera el orden.
- Ordenable por columna Regla y Severidad (`aria-sort`).
- Evidencia larga (valores de parámetros extensos): truncado con tooltip + el valor completo siempre en el export.
- «Re-ejecutar»: congela parámetros de ESTA corrida; si la versión activa del workflow cambió, el modal lo advierte (ver vista 19).
- El export PDF/CSV se genera server-side desde los datos de la corrida (no un screenshot); CSV con encabezados estables para Excel (separador `;` por locale es-BO).
- Resultado de corrida vieja con checklist superado: banner info «existe una versión más nueva del checklist (v4)» si el sistema la conoce.

### Diferencias por rol
| Elemento | Funcional | Técnico | Admin |
|---|---|---|---|
| Resumen, tabla, exports | ✅ | ✅ | ✅ |
| Costo + tokens + chips cache en trazabilidad | — | ✅ | ✅ |
| Hash del checklist y versión de workflow | ✅ (es trazabilidad, no jerga de costo) | ✅ | ✅ |
| Ver resultados ajenos | — | — | ✅ |

### Móvil
✅ funcional: tiles 2×3, tabla con scroll-x y sombra-affordance; exports en fila full-width. La lectura fina del informe se asume en desktop, pero nada se oculta.

### Notas i18n
- Conteos con ICU («{n, plural, one {hallazgo} other {hallazgos}}»).
- Severidades como glosario cerrado (crítico/alto/medio/bajo → PT-BR crítico/alto/médio/baixo).
- No traducir: códigos de regla (`FAT-001`), parámetros (`MV_PAISLOC`), tablas (`SX6`), hashes, nombres de archivo.
- El párrafo ejecutivo lo genera el LLM en el idioma de la instancia (instrucción del prompt, no del catálogo de UI).

---

## 5. Vista 19 — Historial de corridas (`19-workflow-historial.html`)

### Propósito
Buscar corridas previas, re-ejecutar con los mismos parámetros y **comparar dos corridas** del mismo workflow para ver la evolución de hallazgos (nuevos / resueltos / persistentes) — el valor de seguimiento entre visitas al cliente.

### Quién la ve (roles y capacidades)
Todos los roles ven **sus** corridas. Admin ve todas + filtro «Usuario». Costo por corrida: columna solo Técnico/Admin.

### Layout

```
┌──────────────────────────────────────────────────────────────┐
│ HISTORIAL DE CORRIDAS                                         │
│ [Cliente ▾][Workflow ▾][Estado ▾][Desde][Hasta][Usuario ▾*]  │
│                                            [Limpiar filtros] │
├──────────────────────────────────────────────────────────────┤
│ ☑ WF-0347 Validación Fact. C.Andina·VAL 10/06 9m42s COMPLETADA│
│ ☑ WF-0341 Validación Fact. C.Andina·VAL 06/06 11m08s COMPLETADA│
│ ☐ WF-0338 …                                  ERROR            │
│   …                       hallazgos 1C·3A·5M·2B  USD 0,21*   │
├──────────────────────────────────────────────────────────────┤
│ 2 seleccionadas: WF-0341 → WF-0347        [Comparar corridas]│
├──────────────────────────────────────────────────────────────┤
│ COMPARACIÓN  +3 nuevos · 5 resueltos · 8 persistentes        │
│ ┌ nuevos ─┐ ┌ resueltos ─┐ ┌ persistentes ─┐                 │
└──────────────────────────────────────────────────────────────┘
```

### Componentes usados
`.panel` (filtros, diff), `.select`, `.input` (fechas), `.table-wrap` + `.table--dense`, `.checkbox`, `.tag` (estados §0.3, severidades §0.4, `NUEVO`/`RESUELTO`/`PERSISTENTE`), `.btn--primary` (comparar — único primario de la vista), `.btn--ghost --sm` (re-ejecutar, ver), `.empty-state` (sin resultados), `.modal` (confirmar re-ejecución), paginación clásica (§9.5).

### Datos que muestra (campos exactos)
**Filtros:** Cliente final · Workflow · Estado (§0.3) · Fecha desde / hasta · Usuario (solo Admin) · «Limpiar filtros».
**Tabla (orden default: fecha desc):**
| Columna | Contenido |
|---|---|
| ☐ comparar | checkbox (máx. 2; ver casos borde) |
| Corrida | id mono, enlace (a resultado si terminó; a ejecución si vive) |
| Workflow | nombre + versión mono (versión solo Técnico/Admin) |
| Cliente · ambiente | nombre + badge de ambiente |
| Fecha | `dd/mm/aaaa HH:mm` |
| Duración | mono (`9 min 42 s`; `—` si no terminó) |
| Estado | tag §0.3 |
| Hallazgos | mini-resumen mono coloreado: `1C 3A 5M 2B` (tooltip con palabras); `—` si no aplica |
| Costo | `USD 0,21` — columna entera solo Técnico/Admin |
| Acciones | «Ver» (ghost) · «Re-ejecutar» (ghost, solo corridas terminadas: completada/error/cancelada) |

**Barra de comparación** (aparece con 2 seleccionadas): «2 seleccionadas: {idA} → {idB}» + «Comparar corridas» (primary) + «Quitar selección».
**Panel de comparación (diff de hallazgos):**
- Encabezado: «{idA} ({fechaA}) → {idB} ({fechaB})» + cliente/ambiente + advertencia warn si el checklist difiere de versión («v2 → v3: el diff puede incluir reglas nuevas del checklist»).
- Resumen: `+3 nuevos` (tag--danger) · `5 resueltos` (tag--money) · `8 persistentes` (tag--warn).
- Tres listas agrupadas; cada ítem: código de regla mono + nombre + severidad actual (+ flecha de cambio de severidad si varió: `medio → alto`).
- La clave de matching del diff es el **código de regla** del checklist.

### Estados
- **Carga:** tabla skeleton (5 filas).
- **Vacío (sin corridas):** empty-state «Todavía no ejecutaste ningún workflow. Las corridas van a aparecer acá.» + CTA «Ir a workflows».
- **Vacío (filtros sin resultados):** empty-state «Sin resultados para los filtros aplicados» + «Limpiar filtros».
- **Error de carga:** ErrorCard + reintentar.
- **Éxito:** tabla + paginación («Mostrando 1–20 de 156»).
- **Degradado:** si el cómputo del diff tarda (>1,5 s), mensaje de progreso real («comparando 42 reglas…»), no skeleton infinito.

### Interacciones y casos borde
- **Selección para comparar:** al marcar la primera, las filas de **otros workflows u otros pares cliente/ambiente se deshabilitan** con tooltip «solo se comparan corridas del mismo workflow y cliente» (deshabilitar-con-motivo, §9.7: es temporal, no de permiso). Con 2 marcadas, el resto de checkboxes se deshabilita.
- Comparar corridas no completadas: checkbox deshabilitado (tooltip «la corrida no terminó»).
- **Orden del diff:** siempre cronológico (vieja → nueva) aunque el usuario marque al revés.
- **Re-ejecutar:** modal con los parámetros congelados (cliente, ambiente, checklist nombre+versión+hash, módulo, país). Si la versión activa del workflow cambió desde la corrida original, advertencia warn: «La corrida original usó v1.3; hoy se ejecuta v1.4». Si el bridge está caído, el modal muestra `BRIDGE_OFFLINE` y el CTA se deshabilita. Confirmar crea **corrida nueva** (jamás se sobreescribe la vieja) y navega a la vista 17.
- Re-ejecutar cuyo checklist original fue borrado del storage: bloqueado con motivo + acción «Configurar de nuevo» (pre-carga lo demás en la vista 16).
- Paginación clásica (auditabilidad, §9.5); los filtros viven en la URL (compartibles).

### Diferencias por rol
| Elemento | Funcional | Técnico | Admin |
|---|---|---|---|
| Corridas propias | ✅ | ✅ | ✅ (todas) |
| Filtro «Usuario» | — | — | ✅ |
| Columna Costo | — | ✅ | ✅ |
| Versión de workflow en tabla/modal | — | ✅ | ✅ |
| Comparar / re-ejecutar | ✅ (sobre las propias) | ✅ | ✅ |

### Móvil
✅ funcional con concesiones: filtros colapsados en un panel desplegable; tabla con scroll-x; la comparación se lee en vertical (tres grupos apilados). Re-ejecutar y Ver con targets ≥44 px.

### Notas i18n
- `NUEVO/RESUELTO/PERSISTENTE` como glosario cerrado; conteos ICU.
- Las letras del mini-resumen (`1C 3A 5M 2B`) derivan de la inicial de severidad **por locale** (clave de catálogo, no hardcode — en PT-BR coinciden).
- Fechas de filtros con `Intl`; no traducir ids ni hashes.

---

## Apéndice — Inventario de archivos del módulo

| Archivo | Contenido |
|---|---|
| `mockups/15-workflows-lista.html` | lista + carga + vacío |
| `mockups/16-workflow-form.html` | formulario + estados de chip + CTA deshabilitado + BRIDGE_OFFLINE |
| `mockups/17-workflow-run.html` | timeline en vivo + variantes pausado-HITL / error + modal cancelar |
| `mockups/18-workflow-result.html` | resumen ejecutivo + tabla de hallazgos + trazabilidad + variante 0 hallazgos |
| `mockups/19-workflow-historial.html` | filtros + tabla + comparación (diff) + modal re-ejecutar + vacío |
