# 05 — Aprobaciones HITL y validación

> **Módulo:** cola de aprobaciones, tarjeta de aprobación (componente estrella), historial de decisiones, selector cliente/ambiente de ValidationAgent y gestión/revisión de checklists.
> **Mockups:** [`20-aprobaciones-cola.html`](../mockups/20-aprobaciones-cola.html) · [`21-aprobacion-detalle.html`](../mockups/21-aprobacion-detalle.html) · [`22-aprobaciones-historial.html`](../mockups/22-aprobaciones-historial.html) · [`27-selector-cliente-ambiente.html`](../mockups/27-selector-cliente-ambiente.html) · [`28-checklists.html`](../mockups/28-checklists.html) · [`29-checklist-review.html`](../mockups/29-checklist-review.html)
> **Base normativa:** UX-SPEC §5 (HITL) · DESIGN-SYSTEM §8.14 (tarjeta HITL), §9.2 (confirmación destructiva), §9.3 (anti-fatiga), §9.7 (ocultar vs deshabilitar), §9.8 (formatos es-BO) · CLAUDE.md reglas duras (jamás SQL write; escrituras solo API REST oficial + HITL).
> Todos los datos de ejemplo son **ficticios** (Comercial Andina S.A., Distribuidora Altiplano SRL, usuaria «lucia»).

---

## 0. Modelo común del módulo

### 0.1 Ciclo de vida de una solicitud de aprobación

```
agente propone escritura
        │
        ▼
   PENDIENTE ──────────────► EXPIRADA (venció el plazo; reabrible por el solicitante)
   │       │
   │       └─► RECHAZADA (comentario obligatorio) ─ fin
   ▼
APROBADA (1 firma; irreversibles exigen 2 firmas de usuarios distintos)
   │
   ▼
EJECUCIÓN (API REST oficial, nunca SQL) ──► ÉXITO │ FALLÓ (código + detalle)
```

Reglas duras transversales:

- **Toda escritura a Protheus pasa por aquí.** No existe la vía rápida.
- **Append-only:** las solicitudes y decisiones jamás se editan ni borran; toda decisión queda auditada con identidad, fecha-hora, comentario y firma(s).
- **Expiración visible siempre** (relativa + absoluta). Una solicitud expirada no es aprobable: el solicitante puede «Reabrir solicitud» (crea solicitud nueva enlazada, payload re-validado por el agente).
- **Comentario obligatorio:** al **rechazar** (todos los niveles) y al **aprobar riesgo crítico**. El botón se habilita recién con texto.
- **Segunda aprobación** para acciones marcadas irreversibles: dos usuarios distintos; el primer firmante no puede dar la segunda firma; ambas firmas quedan en el audit.
- **Concurrencia:** si otro aprobador resuelve primero, la tarjeta abierta se actualiza a resuelta y lo anuncia (`aria-live`), sin perder el comentario tipeado (queda en el campo, descartable).
- **Una ejecución fallida no se reintenta desde el historial:** el agente genera una solicitud nueva (enlazada a la fallida) para que el aprobador re-evalúe.

### 0.2 Taxonomía de riesgo (clasificada por el sistema, explicada siempre)

| Riesgo | Tag | Criterio (ejemplos) | Exigencias UI |
|---|---|---|---|
| **Bajo** | `tag--money` «RIESGO BAJO» | DEV/VAL, datos no contables, reversible | Elegible para lote |
| **Medio** | `tag--warn` «RIESGO MEDIO» | VAL con datos compartidos, o PROD no contable reversible | Individual |
| **Alto** | `tag--alt` «RIESGO ALTO» | PROD reversible que afecta operación (parámetros, tablas de configuración) | Individual |
| **Crítico** | `tag--danger` «RIESGO CRÍTICO» | PROD contable/fiscal, o cualquier irreversible | Comentario obligatorio + confirmación reforzada (tipear `APROBAR`); irreversibles además 2ª firma |

El color jamás viaja solo: el tag siempre lleva la palabra. La tarjeta lista **por qué** se clasificó así (bullets generados por reglas, no por el LLM).

### 0.3 Ambientes y niveles de datos

| Ambiente | Badge | Nivel de datos resultante |
|---|---|---|
| `PROD` | `tag--danger` «PROD» (siempre resaltado) | **N2** — datos operativos reales: advertencia explícita; prohibido pegar datos personales/credenciales (N3) |
| `VAL` | `tag--info` «VAL» | N1 — datos de prueba compartidos |
| `DEV` | `tag` neutral «DEV» | N1 — datos de prueba |

### 0.4 Roles y capacidades del módulo

| Capacidad | Funcional | Técnico | Admin |
|---|---|---|---|
| Generar solicitudes (usando agentes) | ✅ | ✅ | ✅ |
| Ver sección «Aprobaciones» (vistas 20/21/22) | ❌ (no existe en su UI) | ✅ si tiene capacidad **aprobador** (la otorga Admin; los Técnicos no la tienen por defecto) | ✅ (aprobador nato) |
| Historial: «Mis decisiones» | ❌ | ✅ | ✅ |
| Historial: «Todas las decisiones» + export | ❌ | ❌ | ✅ |
| Selector cliente/ambiente (vista 27) | ✅ (al iniciar ValidationAgent/workflow) | ✅ | ✅ |
| Gestión de checklists (28) y revisión (29) | ❌ | ✅ | ✅ |

El solicitante Funcional sigue el estado de **sus** solicitudes desde la tarjeta HITL embebida en su sesión de chat (UX-SPEC §5), no desde este módulo.

### 0.5 Navegación

`Sidebar → Aprobaciones` abre la **cola (20)**. Fila → **detalle (21)**. Tab «Historial» → **vista 22**. El **selector (27)** es un modal disparado al iniciar sesión de ValidationAgent o un workflow que toca ambiente. `Sidebar → Checklists` (capa Técnico) abre la **lista (28)**; «Revisar» abre la **revisión (29)**.

---

## 1. Vista 20 — Cola de aprobaciones (`20-aprobaciones-cola.html`)

### Propósito
Bandeja única de solicitudes de escritura pendientes para los aprobadores. Optimizada para decidir rápido sin perder rigor: lo urgente arriba (expiración ascendente), riesgo visible de un vistazo, y **modo lote anti-fatiga** restringido a riesgo bajo.

### Quién la ve
Admin y Técnico con capacidad aprobador. Funcional: la sección no se renderiza (ni el ítem de sidebar). No hay estado «sin permiso»: lo que el rol no tiene, no existe (§9.7).

### Layout

Tabla densa a ancho admin (máx. 1200 px), filtros arriba, barra de lote pegajosa abajo al haber selección.

```
┌──────────────────────────────────────────────────────────────────────┐
│ APROBACIONES                                  [○ auto-refresco 30 s] │
│ Cola de aprobaciones                 5 pendientes · 1 crítica        │
│ [Pendientes (5)] [Historial ↗]                                       │
│ [buscar…] [cliente ▾] [ambiente ▾] [riesgo ▾] [agente ▾] [limpiar]   │
├──────────────────────────────────────────────────────────────────────┤
│ ☑ │RIESGO  │ACCIÓN          │CLIENTE/AMB │SOLICITANTE│EXPIRA │       │
│ — │CRÍTICO │Anular títulos… │C.Andina PROD│valeria   │1h 58m │Revisar│
│ — │ALTO    │Actualizar MV_* │C.Andina PROD│valeria   │23h12m │Revisar│
│ ☑ │BAJO    │Desc. campo SX3 │D.Altiplano VAL│marco   │46h…   │Revisar│
│ ☑ │BAJO    │Desc. campo SX3 │D.Altiplano VAL│marco   │46h…   │Revisar│
├──────────────────────────────────────────────────────────────────────┤
│ ▣ 2 seleccionadas — lote: actualizaciones SX3 · D.Altiplano / VAL    │
│   diff resumido agregado ▾   [Limpiar] [Rechazar lote] [Aprobar lote]│
└──────────────────────────────────────────────────────────────────────┘
```

### Componentes usados
`.table-wrap`+`.table` (densa) · `.tag` (riesgo, ambiente) · `.tabs` (Pendientes / Historial como nav-link) · `.input`/`.select` (filtros) · `.checkbox` (selección de lote) · `.btn` · `.empty-state` · `.skeleton` · `.error-card` · `.toast` · `.live-dot` (auto-refresco) · `.kicker`.

### Datos que muestra (campos exactos por fila)
- **Selección**: checkbox **solo** en riesgo bajo; en medio/alto/crítico la celda muestra `—` con `sr-only` «no elegible para lote» (la elegibilidad nunca existirá para ese ítem → no se deshabilita, se omite).
- **ID** `APR-0148` (mono, secundario bajo la acción).
- **Riesgo**: tag con palabra (§0.2).
- **Acción resumida**: 1 línea en lenguaje claro («Actualizar 3 parámetros de localización (SX6)»); debajo, agente origen (`validationagent@7`, mono).
- **Cliente / ambiente**: nombre + badge; **PROD siempre `tag--danger`**.
- **Solicitante**: usuario (`valeria`) + rol abreviado.
- **Creada**: relativo (`hace 2 h`), absoluto en tooltip.
- **Expira**: countdown mono (`23 h 12 min`); `--warn` < 2 h, `--danger` < 30 min; absoluto en tooltip. Tag adicional `tag--alt` «2ª FIRMA 1/2» cuando espera segunda aprobación.
- **Acción**: botón secundario «Revisar» → vista 21.
- Encabezado de página: contador «5 pendientes · 1 crítica» + indicador de auto-refresco (`live-dot` + «actualizado hace 12 s»).

### Estados
- **Carga**: 4 filas skeleton con anchos variados dentro del `table-wrap` (`aria-busy`).
- **Vacío**: empty-state «Nada pendiente» + «Cuando un agente necesite escribir en Protheus, la solicitud va a aparecer acá.» Sin CTA (no se crean solicitudes a mano).
- **Vacío por filtro**: «Sin resultados para los filtros aplicados» + botón «Limpiar filtros».
- **Error**: error-card en lugar del cuerpo («No se pudo cargar la cola» / por qué / «Reintentar»); código copiable para Técnico/Admin.
- **Éxito**: toast `--ok` tras lote («Lote aprobado — 3 escrituras encoladas para ejecución»).
- **Degradado**: si el servicio de ejecución no reporta countdowns, la columna Expira muestra `—` + tooltip «expiración sin sincronizar»; tag `--warn` global «datos de hace N min» si el auto-refresco falla (no es bloqueo).

### Interacciones y casos borde
- Orden por defecto: expiración ascendente. Encabezados ordenables (`aria-sort`): riesgo, cliente, creada, expira.
- Click en fila = «Revisar» (la fila entera enlaza; el botón explícito existe para a11y y móvil).
- **Lote (anti-fatiga §9.3):** al marcar la primera fila se fija el grupo (mismo tipo de acción + cliente + ambiente). Checkboxes de filas incompatibles pasan a `disabled` con tooltip «otro cliente/ambiente — no agrupable» (imposibilidad temporal → deshabilitar con motivo). La barra de lote muestra: conteo, resumen agregado («2 actualizaciones de descripción de campo (SX3) en Distribuidora Altiplano SRL / VAL»), **diff resumido agregado** expandible por ítem, y acciones. «Aprobar lote» registra una entrada de audit **por ítem**. No existe «aprobar todo» global.
- Riesgo crítico jamás entra al lote (sin checkbox).
- Solicitud que expira mientras la vista está abierta: la fila se atenúa, countdown → «expirada», checkbox se desmarca solo y sale del lote (anunciado por `aria-live`).
- Concurrencia: fila resuelta por otro aprobador desaparece en el siguiente refresco con anuncio «APR-0152 resuelta por rodrigo».

### Diferencias por rol
- Técnico aprobador y Admin ven exactamente lo mismo en esta vista; la diferencia aparece en historial (22).
- Funcional: vista inexistente.

### Móvil (380 px) — primera clase
Tabla → cards apiladas: riesgo + acción arriba, cliente/ambiente, expira en grande, botón «Revisar» full-width. El lote se conserva (checkbox 44 px); la barra de lote es bottom-sheet pegajoso.

### Notas i18n
- Claves externalizadas; plural ICU para «{n, plural, one {# pendiente} other {# pendientes}}».
- Countdown con unidades cortas localizables («23 h 12 min»); no concatenar («expira en {countdown}»).
- No traducir: IDs (`APR-0148`), versiones de agente, `MV_*`, `SX3`, códigos de error.
- Botones con +25% de reserva («Aprobar lote» → pt-BR «Aprovar lote» entra holgado).

---

## 2. Vista 21 — Detalle de aprobación (`21-aprobacion-detalle.html`)

### Propósito
**El componente más crítico del producto** (§8.14): tarjeta autosuficiente donde el aprobador entiende qué se va a ejecutar sin navegar a ningún otro lado, y decide con fricción proporcional al riesgo.

### Quién la ve
Admin y Técnico aprobador (desde la cola o desde la notificación). El solicitante (cualquier rol) ve la **misma tarjeta en modo lectura** embebida en su sesión de chat, sin botones de decisión.

### Layout

Columna única máx. 880 px. Orden de lectura = orden de decisión: qué → dónde → riesgo → evidencia (diff/payload) → comentario → decidir.

```
┌────────────────────────────────────────────────┐
│ ⛨ APROBACIÓN REQUERIDA   APR-0147  [RIESGO ALTO]│ ← head ámbar .hitl-card__head
├────────────────────────────────────────────────┤
│ Qué se va a ejecutar (lenguaje claro, 1-2 fr.) │
│ ┌meta grid───────────────────────────────────┐ │
│ │cliente│ambiente PROD│agente│solicitante│…  │ │
│ └────────────────────────────────────────────┘ │
│ Clasificación de riesgo — por qué (bullets)    │
│ Cambio propuesto (diff: actual → propuesto)    │
│ Payload (formateado, visible) [▸ crudo JSON]   │
│ Comentario [textarea]  (* obligatorio crítico) │
│ ⏱ expira en 23 h 12 min · 12/06/2026 13:44     │
│ 🔏 esta decisión queda auditada con tu identidad│
├────────────────────────────────────────────────┤
│                       [Rechazar] [Aprobar escritura]│
└────────────────────────────────────────────────┘
```

### Componentes usados
`.hitl-card` (head/body/meta/payload/expire/foot) · `.tag` (riesgo, ambiente, estado) · tabla de diff (variante local de `.table--dense`) · `<details>` para payload crudo · `.field`+`.textarea` (comentario con validación) · `.btn--primary`/`--secondary`/`--danger` · `.overlay`+`.modal` (confirmación reforzada) · `.error-card` (fallo de envío) · `.toast` · `.skeleton`.

### Datos que muestra (campos exactos)
- **Head:** «Aprobación requerida» + ícono `shield-check` · ID `APR-0147` · tag de riesgo.
- **Qué se va a ejecutar:** frase en lenguaje claro, sin jerga de API: «El agente va a actualizar 3 parámetros de localización (SX6) en el ambiente productivo de Comercial Andina S.A., vía API REST oficial.»
- **Meta grid:** cliente final · ambiente (badge **PROD rojo**) · agente + versión (`validationagent@7`) · solicitante (usuario + rol) · sesión de origen (enlace) · método («API REST oficial — nunca SQL») · creada (fecha-hora absoluta) · reversibilidad («reversible: se conservan los valores anteriores» / «IRREVERSIBLE»).
- **Clasificación de riesgo y por qué:** tag + bullets de reglas («escribe en ambiente productivo», «afecta parámetros contables `MV_*`», «reversible mediante restauración de valores»).
- **Cambio propuesto (diff/preview):** tabla parámetro → valor actual → valor propuesto (mono; propuesto resaltado `--money` suave). Cuando no hay diff aplicable (alta de registro), preview del registro a crear.
- **Payload:** versión formateada SIEMPRE visible (clave→valor legible) + **crudo colapsable** (`<details>` «Ver payload crudo (JSON)», mono, scrollable, copiable).
- **Comentario:** textarea. Obligatorio al aprobar críticos y al rechazar siempre; hint lo dice antes de fallar; error `.is-invalid` + `.field-error` si se intenta sin texto.
- **Expiración:** relativa + absoluta, siempre visibles (no solo tooltip).
- **Registro de auditoría:** «Esta decisión queda auditada con tu identidad: **lucia (Admin)** · 11/06/2026 14:32.»
- **Variante irreversible:** banda «Esperando segunda aprobación (1/2)» + primera firma completa (usuario, fecha-hora, comentario).

### Estados
- **Carga:** skeleton con la silueta de la tarjeta.
- **Pendiente (riesgo bajo/medio/alto):** flujo estándar, comentario opcional al aprobar.
- **Crítica:** comentario obligatorio (botón Aprobar `disabled` con motivo al lado hasta que haya texto) + al click, **confirmación reforzada**: modal que exige tipear `APROBAR` (§9.2); el botón danger del modal se habilita solo con coincidencia exacta; Esc jamás confirma.
- **Irreversible:** todo lo de crítica + estado «1/2». Si el viewer es el primer firmante: botones ocultos + nota «Ya firmaste esta solicitud. La segunda aprobación debe darla otra persona.»
- **Resuelta (aprobada/rechazada):** solo lectura; quién/cuándo/comentario; sin botones; + resultado de ejecución cuando exista.
- **Expirada:** atenuada, tag `EXPIRADA`, botón «Reabrir solicitud» visible solo para el solicitante.
- **Error de envío:** error-card inline sobre el foot; la decisión y el comentario **no se pierden**; «Reintentar».
- **Concurrencia:** banner inline «rodrigo aprobó esta solicitud hace un momento» y la tarjeta pasa a resuelta.
- **Éxito:** toast `--ok` «Decisión registrada» y retorno a la cola.

### Interacciones y casos borde
- **Foco inicial en el cuerpo, jamás en «Aprobar»** (anti-aprobación accidental, §8.14).
- Rechazar abre confirmación simple (no reforzada) con el comentario ya exigido.
- El payload crudo colapsado no oculta información de decisión: todo lo decisorio está en el formateado y el diff.
- Si el bridge/VPN del ambiente está caído al momento de aprobar, la aprobación **se registra igual** y la ejecución queda «en cola — esperando conexión» (error-card `--warn`, no bloquea la decisión).
- Cambio de payload imposible: el aprobador no edita; si algo está mal, rechaza con motivo y el agente propone de nuevo.

### Diferencias por rol
- Solicitante (cualquier rol): modo lectura en su chat; ve estado y resultado, jamás botones.
- Funcional nunca ve esta vista en el módulo (no existe para él); su tarjeta embebida omite jerga técnica adicional (sin versión de agente).
- Técnico aprobador y Admin: idéntica.

### Móvil — primera clase
Meta grid a 1 columna; payload con scroll horizontal; botones full-width en columna con **primario abajo** (zona del pulgar); confirmación reforzada como modal a ancho completo. Aprobar desde el celular es caso de uso real.

### Notas i18n
- «esta decisión queda auditada con tu identidad» — plantilla con placeholders nombrados: `{usuario} ({rol})`.
- La palabra a tipear en la confirmación reforzada se localiza como glosario cerrado (`APROBAR` / pt-BR `APROVAR`) y se muestra siempre en el propio modal — nunca se asume.
- No traducir payload, parámetros ni códigos. Fechas por `Intl` es-BO.

---

## 3. Vista 22 — Historial de decisiones (`22-aprobaciones-historial.html`)

### Propósito
Trazabilidad completa: qué se decidió, quién, cuándo, con qué comentario, y **qué pasó después** (resultado de la ejecución). Cierra el ciclo de confianza: una aprobación no termina al aprobar.

### Quién la ve
- **Técnico aprobador:** tab «Mis decisiones» (solo las propias).
- **Admin:** además tab «Todas» (todas las decisiones de la instancia) + export CSV.
- Funcional: no existe.

### Layout

```
┌──────────────────────────────────────────────────────────────────────┐
│ APROBACIONES · Historial                            [⬇ Exportar CSV] │
│ [Mis decisiones (24)] [Todas (212)]            ← «Todas» solo Admin  │
│ [desde] [hasta] [cliente ▾] [decisión ▾] [ejecución ▾] [buscar…]     │
├──────────────────────────────────────────────────────────────────────┤
│FECHA      │ID/ACCIÓN     │CLIENTE/AMB│RIESGO│DECISIÓN │EJECUCIÓN│COM.│
│11/06 14:32│APR-0147 MV_* │C.And. PROD│ALTO  │APROBADA │ÉXITO    │ «…»│
│11/06 11:05│APR-0144 SE1  │C.And. PROD│CRÍT. │APROBADA ×2│FALLÓ ↗│ «…»│
│10/06 16:48│APR-0139 SX3  │D.Alt. VAL │BAJO  │RECHAZADA│—        │ «…»│
├──────────────────────────────────────────────────────────────────────┤
│                              ‹ 1 2 3 … 9 ›  paginación clásica       │
└──────────────────────────────────────────────────────────────────────┘
```

### Componentes usados
`.tabs` · `.table-wrap`+`.table` · `.tag` · `.input type=date`/`.select` · `.btn--secondary` (export) · `.empty-state` · `.skeleton` · `.error-card` · sheet lateral (modal variante) para el detalle resuelto.

### Datos que muestra (columnas exactas)
- **Fecha decisión** `dd/mm/aaaa HH:mm` (mono).
- **ID + acción** (`APR-0147` mono + resumen 1 línea).
- **Cliente / ambiente** (PROD resaltado).
- **Riesgo** (tag).
- **Decisión:** `APROBADA` (`tag--money`) · `APROBADA ×2` (irreversible, ambas firmas en tooltip y en el detalle) · `RECHAZADA` (tag neutral con ícono ×) · `EXPIRADA` (`tag--warn`).
- **Decidida por:** usuario(s); en «Mis decisiones» se omite (siempre sos vos) y en «Todas» es columna visible.
- **Resultado de ejecución:** `ÉXITO` (`tag--money`) · `FALLÓ` (`tag--danger` + enlace «ver error»: código `BRIDGE_TIMEOUT`, HTTP, fecha) · `EN CURSO` (`tag--info`) · `EN COLA` (esperando conexión) · `—` (rechazada/expirada: nunca se ejecutó).
- **Comentario:** truncado a 1 línea, completo en el detalle.
- Fila → abre **sheet lateral** con la tarjeta 21 en modo resuelta (sin perder los filtros).

### Estados
- **Carga:** filas skeleton.
- **Vacío:** «Todavía no decidiste ninguna aprobación.» / en «Todas»: «No hay decisiones en el rango elegido.»
- **Vacío por filtro:** + «Limpiar filtros».
- **Error:** error-card con reintento.
- **Éxito (export):** botón en loading durante la generación; toast `--ok` «Export listo — descargando aprobaciones-2026-06.csv».
- **Degradado:** si el resultado de ejecución aún no sincroniza: `tag` neutral «SIN DATOS» + tooltip «el ejecutor no reportó todavía».

### Interacciones y casos borde
- El export respeta los filtros activos y lo dice junto al botón («exporta 38 filas filtradas»).
- `FALLÓ` muestra, si existe, el enlace a la **solicitud nueva** generada para reintentar («reintento: APR-0151») — desde acá no se re-ejecuta nada.
- Aprobada ×2 con ejecución fallida es el caso de auditoría más sensible: el detalle muestra firmas + error + cadena de reintento completa.
- Paginación clásica (auditabilidad §9.5), 25 por página.
- Orden por defecto: fecha de decisión descendente.

### Diferencias por rol
- Técnico: solo «Mis decisiones», sin export.
- Admin: tabs «Mis decisiones»/«Todas», columna «Decidida por», export CSV.
- La tab que el rol no tiene **no se renderiza**.

### Móvil
Lectura: tabla → cards (fecha + acción + decisión + ejecución); filtros en acordeón; export disponible (genera y descarga igual).

### Notas i18n
- Estados de decisión/ejecución como glosario cerrado (1 término → 1 traducción).
- El CSV exporta encabezados localizados pero códigos sin traducir.
- Fechas y números por `Intl` es-BO; tooltips con fecha absoluta.

---

## 4. Vista 27 — Selector de cliente y ambiente (`27-selector-cliente-ambiente.html`)

### Propósito
Compuerta obligatoria al iniciar sesión de ValidationAgent (o un workflow que toca un ambiente): elegir **contra qué cliente final y ambiente** se trabaja, viendo en vivo si la VPN y el bridge responden, y entendiendo el **nivel de datos** que implica la elección antes de escribir el primer mensaje.

### Quién la ve
Todos los roles que inician ValidationAgent o un workflow con ambiente (Funcional incluido). Sin selección no hay sesión: el modal no se puede saltar (cancelar = no iniciar).

### Layout

Modal 640 px (bottom-sheet en móvil). Acordeón de clientes; radios por ambiente; panel de consecuencia (nivel de datos) bajo la selección.

```
┌── Seleccioná cliente y ambiente ──────────────── ✕ ─┐
│ El agente va a leer (y proponer escrituras) solo    │
│ contra el ambiente que elijas.                      │
│ ▾ Comercial Andina S.A.        [última elección]    │
│   ◉ VAL  [VAL]  VPN ● online 38ms · bridge ● v1.4.2 │
│   ○ PROD [PROD] VPN ● online 41ms · bridge ● v1.4.2 │
│   ○ DEV  [DEV]  VPN ◌ offline desde 09:12           │
│        └ diagnóstico + [Reintentar] [Guía de VPN]   │
│ ▸ Distribuidora Altiplano SRL (2 ambientes)         │
│ ▸ Agroindustrias del Sur S.A. (1 ambiente)          │
│ ┌─────────────────────────────────────────────────┐ │
│ │ Nivel de datos resultante: N1 — datos de prueba │ │
│ └─────────────────────────────────────────────────┘ │
│ ☑ Recordar esta elección para la próxima sesión     │
├─────────────────────────────────────────────────────┤
│            [Cancelar] [Iniciar con C. Andina · VAL] │
└─────────────────────────────────────────────────────┘
```

### Componentes usados
`.overlay`+`.modal` (variante ancha local) · acordeón nativo (`<details>`-like con botones) · radios nativos estilados con `.checkbox` accent · `.tag` (PROD/VAL/DEV) · `.live-dot` (VPN/bridge) · `.error-card`/`--warn` (diagnóstico, N2) · `.check-row` (recordar) · `.btn` · `.skeleton`.

### Datos que muestra (campos exactos)
- Por **cliente final:** nombre, nº de ambientes, «último uso hace N d», tag «última elección» cuando aplica.
- Por **ambiente:** tipo (badge §0.3) · **VPN**: estado online/offline + latencia ms u «offline desde HH:mm» · **Bridge (tat-mcp)**: estado + versión (`v1.4.2`) o diagnóstico («el conector local no responde») · radio de selección.
- **Panel de nivel de datos** (reactivo a la selección): DEV/VAL → nota tranquila «N1 — datos de prueba»; **PROD → advertencia `--warn`**: «N2 — vas a operar contra datos reales del cliente. No pegues datos personales ni credenciales (N3): no se envían al modelo. Toda escritura requerirá aprobación.»
- **Recordar última elección:** checkbox; se guarda por usuario+agente; la próxima vez el cliente viene pre-expandido y preseleccionado (nunca se salta el modal: confirmar sigue siendo explícito).
- Footer: «Cancelar» + primario dinámico «Iniciar con {cliente} · {ambiente}» (`disabled` sin selección, con motivo en tooltip accesible).

### Estados
- **Carga:** skeleton de 3 clientes.
- **Vacío:** «No tenés clientes asignados. Pedile al Admin acceso a un cliente final.» (la asignación es de instancia).
- **Error total:** error-card «No se pudo cargar la lista de clientes» + Reintentar.
- **Ambiente offline:** radio `disabled` + diagnóstico inline + acciones «Reintentar» / «Guía de VPN» (VPN) o «Estado del bridge» (`BRIDGE_OFFLINE`). Offline = imposibilidad temporal → deshabilitar con motivo, no ocultar.
- **Degradado:** estados de conexión con caché: tag `--warn` «estado de hace 5 min» + «Actualizar estados».
- **Éxito:** el modal cierra y la sesión abre con chip persistente de contexto «Comercial Andina · VAL» en el topbar del chat.

### Interacciones y casos borde
- Verificación en vivo: al abrir, se sondean VPN/bridge de los ambientes visibles; re-sondeo al expandir un cliente. «Reintentar» sondea solo ese ambiente (botón loading).
- Seleccionar PROD **no** exige confirmación extra acá (la fricción fuerte vive en la aprobación de escrituras), pero el panel N2 es imposible de no ver (entre la lista y el footer).
- Si el ambiente recordado está offline al volver: preseleccionado pero `disabled`, con el diagnóstico abierto — el primario queda deshabilitado hasta elegir otro.
- Cambiar de cliente/ambiente a mitad de sesión: no existe — es **sesión nueva** (consistente con stickiness de modelo; el chip de contexto lo recuerda).
- Teclado: acordeón con Enter/Espacio; radios con flechas; el panel N2 se anuncia (`aria-live="polite"`) al cambiar la selección.

### Diferencias por rol
- Funcional: idéntico flujo, texto del panel N2 sin jerga («datos reales del cliente — tratalos con cuidado»); no ve versiones de bridge (`v1.4.2` es capa Técnico/Admin).
- Técnico/Admin: ven latencia y versión del bridge; enlace «Estado del bridge» abre diagnóstico técnico.

### Móvil
Bottom-sheet a pantalla completa; radios y filas ≥44 px; footer pegajoso con primario abajo.

### Notas i18n
- Primario con plantilla «Iniciar con {cliente} · {ambiente}» (reordenable).
- Estados de conexión como glosario cerrado (online/offline se traduce — pt-BR «conectado/desconectado» si el glosario lo define).
- No traducir versiones (`v1.4.2`) ni códigos (`BRIDGE_OFFLINE`).

---

## 5. Vista 28 — Gestión de checklists (`28-checklists.html`)

### Propósito
Administrar los checklists de parametrización que usa ValidationAgent: lista versionada por módulo y localización, subir un XLSX nuevo (dispara el workflow de conversión a YAML), descargar originales y entrar a la revisión humana.

### Quién la ve
Técnico y Admin (capa Técnico del sidebar: «Checklists»). Funcional: no existe.

### Layout

```
┌──────────────────────────────────────────────────────────────────────┐
│ VALIDACIÓN · Checklists                              [⬆ Subir XLSX]  │
│ [buscar…] [módulo ▾] [localización ▾] [estado ▾]                     │
├──────────────────────────────────────────────────────────────────────┤
│CHECKLIST        │MÓDULO │LOC│VER│ESTADO      │OWNER  │ACTUALIZADO│   │
│Parametr. fiscal │SIGAFIN│BOL│v3 │APROBADO    │rodrigo│10/06 18:20│⬇ ⊙│
│Parametr. fiscal │SIGAFIN│BOL│v4 │EN REVISIÓN │rodrigo│11/06 09:15│⬇ ▸Revisar│
│Compras          │SIGACOM│BOL│v1 │BORRADOR    │marco  │09/06 11:02│⬇ ⊙│
│Facturación      │SIGAFAT│BOL│v2 │CONVERSIÓN FALLÓ │…│…          │↻  │
├──────────────────────────────────────────────────────────────────────┤
│ (modal Subir XLSX: dropzone + módulo + localización + base)          │
│ (workflow .wf: Subida ✓ → Conversión ● → Revisión ○ → Aprobada ○)    │
└──────────────────────────────────────────────────────────────────────┘
```

### Componentes usados
`.table-wrap`+`.table` · `.tag` (estado) · `.btn--primary` (Subir XLSX) · `.overlay`+`.modal` (subida) · dropzone local (borde dashed + estados) · `.chip` (archivo elegido, `.is-loading`/`.is-error`) · `.wf` (timeline de conversión) · `.empty-state` · `.skeleton` · `.toast`.

### Datos que muestra (campos exactos)
- **Checklist:** nombre + ID mono (`CHK-FIN-BOL`).
- **Módulo:** `SIGAFIN` / `SIGACOM` / `SIGAFAT`… (mono).
- **Localización:** `BOL` (mono; preparado para otras).
- **Versión:** `v3` (mono). Cada (módulo, localización) puede tener: 1 versión **aprobada activa** (la más reciente aprobada), versiones aprobadas anteriores (consultables, inmutables), y a lo sumo 1 borrador/en revisión.
- **Estado:** `APROBADO` (`tag--money`) · `EN REVISIÓN` (`tag--info`) · `BORRADOR` (`tag` neutral) · `CONVERSIÓN FALLÓ` (`tag--danger`).
- **Owner** (quien subió) · **Actualizado** (`dd/mm HH:mm`) · nº de reglas (en aprobados).
- **Acciones por fila:** «Descargar XLSX» (ghost, siempre) · «Revisar» (en revisión → vista 29) · «Ver» (aprobados: vista 29 en solo lectura) · «Reintentar conversión» (falló).
- **Modal de subida:** dropzone XLSX (máx. 10 MB) · selects módulo + localización · «Basado en» (versión aprobada existente, opcional) · al confirmar: inicia workflow y la fila nueva aparece con su `.wf` (Subida ✓ → Conversión automática (en curso) → Revisión humana → Versión aprobada).

### Estados
- **Carga:** filas skeleton.
- **Vacío:** «Todavía no hay checklists. Subí el primer XLSX para que ValidationAgent pueda validar parametrizaciones.» + CTA «Subir XLSX».
- **Error de lista:** error-card + reintento.
- **Conversión en curso:** fila con tag `--info` «CONVIRTIENDO» + spinner; al terminar pasa a «EN REVISIÓN» + notificación (campana).
- **Conversión fallida:** tag `--danger` + acción «Reintentar» + detalle del error (fila expandible: «la hoja ‘Parámetros’ no tiene columna ‘valor esperado’»).
- **Éxito de subida:** toast `--ok` «XLSX subido — conversión iniciada».
- **Degradado:** sin conexión al convertidor: la subida queda «EN COLA» (`tag--warn`), no se pierde.

### Interacciones y casos borde
- Subir un XLSX para un (módulo, localización) que ya tiene borrador/en revisión: el modal lo bloquea con motivo («ya existe v4 en revisión — finalizala o descartala antes de subir otra»).
- Dropzone valida tipo (.xlsx) y tamaño al soltar; error en `.chip.is-error` con motivo, sin perder el resto del formulario.
- Las versiones aprobadas son **inmutables**: no hay editar ni borrar; «corregir» = subir versión nueva.
- Descargar XLSX siempre baja el original tal como se subió (auditable).
- Borrador descartable (acción secundaria con confirmación destructiva normal §9.2a).

### Diferencias por rol
- Técnico y Admin: idéntico (ambos suben, revisan y aprueban).
- Admin adicional: puede descartar borradores de otros owners; Técnico solo los propios.

### Móvil
Lectura (⚠️): tabla con scroll-x o cards; subir XLSX se recomienda en desktop (el botón existe y funciona; el modal advierte «mejor en escritorio» sin bloquear).

### Notas i18n
- Estados como glosario cerrado. No traducir módulos (`SIGAFIN`), localizaciones (`BOL`), IDs ni versiones.
- Mensajes de error de conversión vienen del backend con clave + parámetros (no strings libres).

---

## 6. Vista 29 — Revisión de checklist convertido (`29-checklist-review.html`)

### Propósito
Revisión humana regla por regla de la conversión XLSX → YAML antes de aprobar: lado a lado el original y la interpretación estructurada, con aprobar / corregir inline / descartar con razón. Al finalizar, la versión queda **aprobada e inmutable** y pasa a ser la activa para ValidationAgent.

### Quién la ve
Técnico y Admin. El revisor puede ser distinto del owner que subió (cuatro ojos recomendado, no obligatorio en v1).

### Layout

```
┌──────────────────────────────────────────────────────────────────────┐
│ CHECKLISTS · Revisión — Parametrización fiscal BOL · v4 (borrador)   │
│ ▓▓▓▓▓▓▓▓░░░░░░ 12 de 34 reglas revisadas (35%)                       │
│ [filtro: ▾ pendientes] [Aprobar todo lo restante] [Finalizar revisión]│
├──────────────────────────────────────────────────────────────────────┤
│ REGLA 13 · fila XLSX 14                       [pendiente]            │
│ ┌ XLSX original ──────────────┬ Regla interpretada (YAML) ─────────┐ │
│ │ celdas tal cual (tabla)     │ id / tabla / campo / condición /   │ │
│ │                             │ valor esperado / severidad / msj   │ │
│ └─────────────────────────────┴────────────────────────────────────┘ │
│            [Descartar] [Corregir] [Aprobar regla]                    │
│ … (regla aprobada, regla en edición, regla descartada, baja confianza)│
└──────────────────────────────────────────────────────────────────────┘
```

### Componentes usados
`.panel` por regla · barra de progreso (`.quota-bar` reutilizada como progreso de revisión, fill `--money`) · grid 2 columnas local (original vs interpretado) · `.table--dense` (celdas XLSX) · `.field`/`.input--mono`/`.select`/`.textarea` (edición inline y razón de descarte) · `.tag` (estado por regla, «BAJA CONFIANZA») · `.btn` · `.overlay`+`.modal` (aprobar-restante y finalizar) · `.empty-state` · `.toast`.

### Datos que muestra (campos exactos)
- **Header:** nombre + módulo/localización + versión (`v4 — borrador`) + owner + origen («convertido de plan-fiscal-bol-v4.xlsx, 11/06/2026 09:15»).
- **Progreso:** «12 de 34 reglas revisadas» + barra; desglose: 9 aprobadas · 2 corregidas · 1 descartada · 22 pendientes.
- **Por regla:**
  - Identidad: `REGLA 13` + «fila XLSX 14» (trazabilidad al original).
  - **Izquierda — XLSX original:** las celdas crudas de esa fila (columna: encabezado de hoja → valor), sin interpretación.
  - **Derecha — interpretación YAML:** campos estructurados: `id` (`fin-bol-013`) · `tabla` (`SX6`) · `campo/parámetro` (`MV_SIMB1`) · `condición` (`igual a`) · `valor esperado` (`"Bs"`) · `severidad` (`error|advertencia`) · `mensaje al consultor` (texto).
  - Estado: `PENDIENTE` (neutral) · `APROBADA` (`tag--money`, borde izquierdo verde) · `CORREGIDA` (`tag--info` + diff de lo cambiado: interpretado → corregido) · `DESCARTADA` (`tag` neutral, card atenuada + razón visible) · flag automático `BAJA CONFIANZA` (`tag--warn`) cuando el convertidor dudó.
- **Acciones por regla:** «Aprobar regla» (primario sm) · «Corregir» (secondary → campos editables inline con Guardar/Cancelar) · «Descartar» (ghost → textarea razón obligatoria + confirmar).

### Estados
- **Carga:** skeletons de 3 reglas.
- **Vacío:** no aplica (una revisión siempre tiene reglas); si la conversión produjo 0 reglas, la vista muestra error-card y devuelve a 28.
- **Error de guardado:** error-card inline en la regla; la edición no se pierde.
- **Edición inline:** validación al blur (valor esperado vacío, severidad sin elegir → `.is-invalid` + mensaje).
- **Aprobar todo lo restante:** modal de confirmación con conteo explícito («Vas a aprobar las 22 reglas pendientes sin revisarlas una por una») — **excluye** las marcadas `BAJA CONFIANZA`, y lo dice («3 reglas de baja confianza quedan fuera: revisalas individualmente»).
- **Finalizar revisión:** habilitado solo con 0 pendientes; modal resumen (aprobadas/corregidas/descartadas) + consecuencia («v4 queda aprobada e inmutable y pasa a ser la versión activa») → éxito: toast + redirect a 28.
- **Degradado:** autosave de decisiones por regla; si se corta la conexión, banner `--warn` «cambios pendientes de sincronizar» (no se pierde nada al volver).

### Interacciones y casos borde
- Las decisiones se guardan regla por regla (se puede abandonar y volver; el progreso persiste).
- «Corregir» edita **solo la interpretación**, jamás el XLSX original (queda como evidencia inmutable, lado a lado para siempre).
- Una regla corregida muestra el diff interpretado→corregido en la card y en el audit de la versión.
- Descartar exige razón (queda en la versión aprobada como regla descartada — auditable; ValidationAgent no la usa).
- Filtro por estado (pendientes por defecto) + salto «siguiente pendiente» al decidir una regla (anti-scroll).
- Si otro revisor trabaja la misma versión: lock optimista por regla; conflicto → la regla se recarga con la decisión del otro y lo anuncia.
- Aprobada la versión: la vista pasa a **solo lectura** permanente (el mismo layout sirve como «Ver» desde la 28).

### Diferencias por rol
- Técnico y Admin idénticos. (El flag de baja confianza y el diff son visibles para ambos: acá los dos son revisores expertos.)

### Móvil
Funcional con reservas (⚠️): las dos columnas se apilan (original arriba, interpretación abajo); edición inline posible pero la vista recomienda escritorio en un banner discreto.

### Notas i18n
- Severidades (`error`/`advertencia`) como glosario cerrado.
- El contenido del checklist (mensajes al consultor) NO se traduce por la UI: pertenece al checklist (cada localización trae su idioma).
- Plurales ICU en progreso y en los modals de confirmación.
- No traducir: `MV_*`, `SX6`, ids de regla, nombres de archivo.
