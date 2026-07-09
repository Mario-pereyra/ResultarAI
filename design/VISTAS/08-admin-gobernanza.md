# Módulo 08 — Administración · Gobernanza

> **Estado:** v1.0 — especificación de diseño. Mockups de referencia en [`../mockups/`](../mockups/):
> [`34-admin-prompts.html`](../mockups/34-admin-prompts.html) · [`35-admin-tools.html`](../mockups/35-admin-tools.html) · [`36-admin-conexiones.html`](../mockups/36-admin-conexiones.html) · [`38-admin-flags.html`](../mockups/38-admin-flags.html) · [`40-admin-instancia.html`](../mockups/40-admin-instancia.html) · [`43-admin-evals.html`](../mockups/43-admin-evals.html)
> **Base:** [`DESIGN-SYSTEM.md`](../DESIGN-SYSTEM.md) (tokens, componentes, patrones §9) y [`mockups/tokens.css`](../mockups/tokens.css).
> **Decisiones ancladas:** ADR-0011 (Registro de Prompts), ADR-0006 (modelos/escalación), ADR-0007/0010 (cuotas), D-13 (escalación configurable por agente), política de datos N0–N3.

Reglas transversales del módulo (aplican a las 6 vistas):

- **Solo Admin.** Las rutas de este módulo no existen para Técnico ni Funcional: no aparecen en el sidebar, no responden por URL directa (404 de producto, no 403 — §9.7 "ocultar, no deshabilitar"). El Admin opera con TOTP ya verificado en sesión; las acciones marcadas como *críticas* en cada vista re-confirman con el patrón escribir-para-confirmar (§9.2).
- **Todo cambio de gobernanza queda en auditoría** (quién, cuándo, qué, de→a, motivo). El audit se muestra inline o en panel propio según la vista; nunca se edita ni se borra.
- **Shell común:** ai-banner permanente → sidebar (sección «Consola admin» activa) → topbar con breadcrumb `Consola admin / Gobernanza / {vista}` + badge `ADMIN` + campana → contenido máx. 1200 px.
- **Datos siempre ficticios en mockups:** Comercial Andina S.A., Distribuidora El Alto SRL, INBOLSA; usuarios `lucia`, `mperez`, `jrojas`; montos pequeños.

---

## 8.1 — Registro de Prompts (`34-admin-prompts.html`)

### Propósito

Administrar las versiones de system prompt de cada agente conforme a ADR-0011: versiones **inmutables** una vez publicadas, publicación condicionada a evals verdes (gate aplicado por el sistema, jamás por checkbox), activación/rollback sin deploy con auditoría completa. Es la vista que sostiene la regla dura "nunca editar en Langfuse a mano": el registro en Postgres es la fuente de runtime y Git recibe snapshots espejo.

### Quién la ve

Solo **Admin**. Capacidades: leer todas las versiones, crear/editar borradores, correr evals, publicar (si el sistema lo permite), activar/rollback, leer auditoría. No hay sub-permisos: quien entra puede todo. Técnico ve la *versión activa* de un prompt solo desde la ficha técnica del agente (otra vista, solo lectura, fuera de este módulo).

### Layout

Dos paneles maestro-detalle. Izquierda: agentes y sus versiones. Derecha: detalle de la versión seleccionada con tabs.

```
┌ topbar: Consola admin / Gobernanza / Registro de Prompts ──── ADMIN ─ 🔔 ┐
│ kicker + h1 + nota ADR-0011                                              │
├──────────────────┬───────────────────────────────────────────────────────┤
│ AGENTES          │ tabs: [Borrador @13] [Activa @12] [Auditoría]         │
│ ▸ DocAgent       │ ┌─ toolbar: Correr evals · Publicar(disabled) · …  ─┐ │
│   ACTIVA @12     │ │ DIFF lado a lado:                                 │ │
│   @13 draft      │ │  Activa @12        │  Borrador @13                │ │
│   @12 published  │ │  (líneas - rojo)   │  (líneas + verde)            │ │
│   @11 published  │ └───────────────────────────────────────────────────┘ │
│   @10 retired    │ changelog del borrador (textarea)                     │
│ ▸ ValidationAg.  │ ┌─ Resultados de evals ─────────────────────────────┐ │
│ ▸ DevAgent       │ │ score 86% ≥ gate 80% · tabla por caso pass/fail   │ │
│                  │ │ (variante: safety hard-fail → publicación         │ │
│                  │ │  bloqueada aunque el score pase)                  │ │
└──────────────────┴───────────────────────────────────────────────────────┘
```

### Componentes usados

`.panel`, `.tabs`/`.tab`, `.tag` (estados de versión: `--info` DRAFT, `--money` PUBLISHED/ACTIVA, neutral RETIRED), `.btn` (primary Publicar, secondary Correr evals, ghost Guardar borrador, danger en rollback), `.table` (resultados de evals, auditoría), `.modal` destructiva (activar/rollback con motivo), `.toast--ok`, `.skeleton`, `.empty-state`, `.error-card`, diff propio de vista (2 columnas mono con líneas `+`/`−` tintadas `--money`/`--danger` al 10%), `.kicker`.

### Datos que muestra

- **Lista de agentes:** nombre, versión activa (`docagent@12`), nº de versiones, fecha del último publish, resultado de la última corrida de evals (score + estado).
- **Por versión:** id (`docagent@13`), estado (`draft` | `published` | `retired`), autor, fecha de creación, fecha de publicación (si aplica), hash de contenido (sha256 corto, mono), changelog, score de evals asociado a la publicación.
- **Detalle de borrador:** contenido editable (mono), diff línea a línea vs versión activa, changelog editable, estado del gate («evals pendientes» / «verdes» / «bloqueado por safety»).
- **Detalle de versión published:** contenido **solo lectura** con candado y nota «published · inmutable — para cambiar, creá un borrador desde esta versión», botón «Crear borrador desde esta versión», botón «Activar esta versión» (si no es la activa).
- **Resultados de evals por caso:** id de caso, nombre, tags (incl. `safety`), score del caso, esperado/obtenido resumido, resultado PASS/FAIL; score total vs gate 80%; los `safety` en FAIL se destacan con fila tintada `--danger` y nota «hard-fail individual: bloquea la publicación aunque el score total pase».
- **Auditoría:** fecha-hora (`dd/mm/aaaa HH:mm`), usuario, acción (`publish` | `activate` | `rollback` | `draft-create` | `draft-edit`), detalle de→a (`@12 → @11`), motivo (obligatorio en activate/rollback).

### Estados

- **Carga:** skeleton de lista (4 filas) + skeleton de panel detalle. >300 ms solamente (§8.23).
- **Vacío:** agente sin versiones → empty-state «Este agente todavía no tiene versiones de prompt» + CTA «Crear primera versión».
- **Error:** error-card `REGISTRY_OFFLINE` («No se pudo cargar el registro de prompts» / «el servicio de plataforma no responde» / Reintentar). El editor de borrador conserva el texto local si el guardado falla (§9.1: el input jamás se pierde).
- **Éxito:** publicar → toast `--ok` «docagent@13 publicada» + la versión pasa a published y el tab de borrador desaparece; activar/rollback → toast con enlace a auditoría.
- **Degradado:** si el runner de evals no responde, «Correr evals» muestra error-card `--warn` «runner no disponible — la publicación queda bloqueada hasta correr evals» (el gate nunca se salta).

### Interacciones y casos borde

- **Publicar** está deshabilitado mientras: no hay corrida de evals para el hash actual del borrador, el score < 80%, o hay ≥1 caso `safety` en FAIL. El motivo se muestra como texto junto al botón (no solo tooltip). **Editar el borrador después de correr evals invalida la corrida** (el gate se evalúa contra el hash): el estado vuelve a «evals pendientes».
- **Activar / Rollback** abre modal destructiva: muestra de→a, exige motivo (botón deshabilitado sin texto) y advierte «las sesiones activas no cambian de versión; aplica a sesiones nuevas» (stickiness, ADR-0006). Esc nunca confirma.
- **Concurrencia:** si otro Admin publica/activa mientras edito, banner inline «el registro cambió — recargá antes de continuar» y el botón Publicar se bloquea hasta recargar.
- **Retired:** una versión retired no puede activarse; solo clonarse a borrador.
- **Draft único por agente:** intentar crear un segundo borrador ofrece «abrir el borrador existente».
- El contenido del prompt se trata como dato no confiable al renderizar (escape total; jamás se interpreta markdown/HTML embebido).

### Diferencias por rol

Solo Admin; no hay variantes internas. (Técnico ve la versión activa desde la ficha técnica — vista 2x, solo lectura, sin diff, sin evals detallados, sin auditoría.)

### Móvil

Lectura básica (§11): lista y detalle apilados, diff con scroll horizontal, tablas con scroll-x. Editar borrador y publicar quedan disponibles pero se recomienda desktop (nota en la vista). Modal de rollback funciona completa en móvil (caso de emergencia real).

### Notas i18n

Claves externalizadas. NO se traducen: ids de versión (`docagent@12`), estados `draft/published/retired` (vocabulario del registro, mono), hashes, tags de evals (`safety`). Fechas `Intl es-BO`. Reservar +25% en botones («Crear borrador desde esta versión» ya es largo: permitir wrap a 2 líneas en móvil).

---

## 8.2 — Tool Registry (`35-admin-tools.html`)

### Propósito

Gobernar el catálogo de tools MCP que los agentes pueden invocar: clasificación de riesgo, permisos por rol, HITL obligatorio, límites operativos, kill-switch por tool y control de drift de schema (si el schema de una tool cambió respecto al aprobado, el cache-first y la seguridad quedan comprometidos — ADR-0001: toolset fijo por versión de agente).

### Quién la ve

Solo **Admin**. Acciones: editar clasificación, permisos, límites, HITL, activar/desactivar tools, revisar/aprobar drift de schema.

### Layout

Lista agrupada por servidor MCP + panel de detalle de la tool seleccionada + matriz de permisos.

```
┌ kicker + h1 ─ chips resumen: 2 servidores · 9 tools · 1 drift ──────────┐
│ ⚠ error-card--warn: drift en protheus_update_param (acciones)           │
├──────────────────────────────────────────────────────────────────────────┤
│ ▼ tat-mcp · v0.6.x · ● WSS conectado                                     │
│ ┌ tabla: tool │ riesgo │ HITL │ rate │ timeout │ bridge ≥ │ hash │ estado┐│
│ │ protheus_query        LECTURA   no   30/min   20s  0.4.0  a1b2…  ACTIVA││
│ │ protheus_update_param ESCRITURA sí   6/min    30s  0.4.2  ⚠drift ACTIVA││
│ └──────────────────────────────────────────────────────────────────────┘│
│ ▼ docs-mcp · interno ·  ● conectado          (segunda tabla)             │
├──────────────────────────┬───────────────────────────────────────────────┤
│ detalle de tool          │ matriz permisos rol × tool (checkboxes)       │
│ (form: riesgo, HITL,     │        Admin  Técnico  Funcional              │
│  rate, timeout, bridge,  │ tool A  ☑      ☑        ☑                     │
│  kill-switch)            │ tool B  ☑      ☑        ☐                     │
└──────────────────────────┴───────────────────────────────────────────────┘
```

### Componentes usados

`.table` + `.table--dense`, `.tag` para riesgo (**LECTURA `--money` · ESCRITURA `--warn` · DESTRUCTIVA `--danger`** — siempre con palabra, §5.2), `.live-dot` (estado del servidor WSS), `.error-card--warn` (drift), `.chip`/`.mono` (hash de schema), `.checkbox` + `.check-row` (matriz), `.input`/`.select` (límites), `.btn--danger` (desactivar), `.modal` (kill-switch y aprobación de drift), `.empty-state`, `.skeleton`, `.tag--outline` (versión de bridge).

### Datos que muestra

- **Por servidor MCP:** nombre (`tat-mcp`), versión, transporte (`WSS --connect`), estado de conexión (conectado / desconectado / degradado), nº tools.
- **Por tool:** nombre (mono, `protheus_query`), descripción (1 línea), clasificación de riesgo (lectura/escritura/destructiva), requiere HITL (sí/no), rate limit (`30/min`), timeout (`20 s`), versión mínima de bridge (`≥ 0.4.0`), hash de schema aprobado (sha256 corto, mono, copiable), estado (ACTIVA / INACTIVA), indicador de drift.
- **Alerta de drift:** tool afectada, hash aprobado vs hash actual, fecha de detección, texto fijo: «el schema cambió respecto a lo aprobado — revisar».
- **Matriz rol×tool:** filas = tools, columnas = Admin/Técnico/Funcional, celdas = checkbox.

### Estados

- **Carga:** skeleton por grupo de servidor (header + 3 filas).
- **Vacío:** «Ningún servidor MCP conectado» + hint con el comando de conexión del bridge (`tat-mcp --connect wss://…`) + enlace a la vista de Conexiones.
- **Error:** servidor desconectado → grupo con live-dot apagado y tag `--danger` DESCONECTADO; las tools se listan igual (último estado conocido) con nota «datos del último contacto: hace 2 h».
- **Éxito:** todo cambio guarda al confirmar y dispara toast `--ok` + entrada de audit.
- **Degradado (drift):** la fila de la tool lleva ícono ⚠ + hash en `--warn`; la error-card global lista los drifts con acciones: «Ver diff de schema» (modal con diff JSON), «Aprobar nuevo schema» (re-hashea y limpia la alerta; queda en audit) y «Suspender tool» (kill-switch directo).

### Interacciones y casos borde

- **Reglas duras visibles en la UI:** una tool clasificada *escritura* o *destructiva* tiene el checkbox «Requiere HITL» **marcado y bloqueado** (tooltip: «las escrituras a Protheus siempre pasan por aprobación humana — regla de plataforma, no configurable»). Reclasificar a lectura exige confirmación con motivo.
- **Kill-switch por tool:** desactivar = modal de confirmación con consecuencia («las sesiones en curso verán la tool fallar con TOOL_DISABLED; los agentes cuya versión la incluye en su toolset seguirán declarándola» — el toolset es fijo por versión, ADR-0001) + motivo obligatorio. Reactivar = confirmación simple.
- **Drift:** mientras haya drift sin resolver, el botón «Aprobar nuevo schema» exige mirar el diff primero (se habilita tras abrir el modal de diff). Aprobar registra hash anterior y nuevo en audit.
- **Matriz:** quitarle una tool a un rol con sesiones activas advierte «aplica a sesiones nuevas» (stickiness). Funcional nunca puede recibir tools destructivas: checkbox bloqueado con motivo.
- **Cambiar rate/timeout** valida rangos (rate 1–120/min, timeout 5–120 s) inline al blur (§9.1).

### Diferencias por rol

Solo Admin. (Técnico ve el *toolset de la versión del agente* en su ficha técnica, solo lectura.)

### Móvil

Lectura: tablas con scroll-x. El kill-switch de tool y «Suspender tool» permanecen operables (emergencia). La matriz de permisos es desktop-recomendada (celdas pequeñas): en móvil se muestra por tool seleccionada (lista de 3 checkboxes), no como grilla.

### Notas i18n

No se traducen: nombres de tool, hashes, `WSS`, códigos (`TOOL_DISABLED`), versiones de bridge. Las clasificaciones LECTURA/ESCRITURA/DESTRUCTIVA sí se traducen (glosario cerrado §12). Cabeceras de matriz con roles traducibles; reservar ancho.

---

## 8.3 — Conexiones a clientes finales (`36-admin-conexiones.html`)

### Propósito

Administrar los *connection profiles* (qué clientes finales y ambientes existen para ValidationAgent) y los *bridges* locales que los consultores corren en sus laptops. Hace visible la regla de arquitectura: **el servidor jamás almacena credenciales de clientes — viven en la laptop del consultor** (bridge local); la plataforma solo conoce perfiles, dispositivos emparejados y su estado.

### Quién la ve

Solo **Admin**. Acciones: crear/editar/archivar perfiles, revocar bridges, generar tokens de emparejamiento.

### Layout

Tres secciones apiladas: perfiles → bridges → emparejamiento.

```
┌ kicker + h1 ──────────────────────────────────────────────────────────────┐
│ ℹ panel-nota: «Las credenciales viven en la laptop del consultor…»        │
│ PERFILES DE CONEXIÓN                                  [ Nuevo perfil ]    │
│ ┌ cliente │ ambiente │ descripción │ nivel datos │ bridges │ acciones ┐   │
│ │ Comercial Andina S.A. │ TEST │ … │ N1 │ 2 ● │ Editar/Archivar │     │   │
├────────────────────────────────────────────────────────────────────────────┤
│ BRIDGES / DISPOSITIVOS VINCULADOS                                          │
│ ┌ consultor │ dispositivo │ versión │ último visto │ estado │ REVOCAR ┐   │
├────────────────────────────────────────────────────────────────────────────┤
│ EMPAREJAR BRIDGE NUEVO                                                    │
│ [Generar token]  →  RSTR-7Q2F-9KDM  · expira en 14 min 32 s · un solo uso │
└────────────────────────────────────────────────────────────────────────────┘
```

### Componentes usados

`.table`, `.tag` para nivel de datos (**N0 neutral · N1 `--info` · N2 `--warn` · N3 `--danger`**, siempre con texto «N3 · personales»), `.live-dot` (online) / `--off` (offline) / `--warn` (desactualizado), `.btn--danger` REVOCAR, `.modal` destructiva, panel-nota informativa con ícono `info` (variante de `.panel` con borde `--info`), `.input--mono` (token), `.btn--primary` Generar token, `.empty-state`, `.skeleton`, `.toast`.

### Datos que muestra

- **Perfil de conexión:** cliente final, ambiente (`PROD` | `TEST` | `DEV` — tag; PROD con tag `--warn`), descripción, nivel de datos N0–N3 (con leyenda: «N3 jamás viaja al LLM»), creado por + fecha, nº de bridges activos que lo sirven, estado (activo/archivado). **Sin credenciales: no existe el campo.** Nota fija: «Las credenciales viven en la laptop del consultor (bridge local). El servidor solo registra el perfil.»
- **Bridge:** consultor (usuario), dispositivo (hostname, mono), versión del bridge (`0.4.2`, mono), último visto (relativo + absoluto en tooltip), estado (`online` / `offline` / `desactualizado` si versión < mínima exigida por alguna tool), perfiles que sirve, acción REVOCAR.
- **Token de emparejamiento:** valor (`RSTR-XXXX-XXXX`, mono, visible una sola vez), expiración (countdown «expira en 14 min 32 s» + absoluto), un solo uso, quién lo generó. Historial corto de emparejamientos recientes (fecha, consultor, dispositivo, resultado).

### Estados

- **Carga:** skeleton por sección.
- **Vacío:** perfiles → «Todavía no hay perfiles de conexión» + CTA «Nuevo perfil»; bridges → «Ningún bridge emparejado — generá un token abajo».
- **Error:** fallo al generar token → error-card inline con Reintentar; la sección de bridges con datos viejos marca «último contacto hace N min» (degradado `--warn`, no error).
- **Éxito:** revocar → toast `--ok` «Bridge de jrojas revocado» + fila pasa a estado `revocado` (atenuada) antes de desaparecer al recargar; generar token → panel de token con countdown.
- **Degradado:** bridge `desactualizado` → live-dot `--warn` + tag «v0.3.9 < mín 0.4.0» + hint «las tools que exigen 0.4.0 fallarán con BRIDGE_OFFLINE para este consultor».

### Interacciones y casos borde

- **REVOCAR** es destructivo normal (§9.2a): modal con consecuencia explícita («el dispositivo pierde acceso inmediato; las sesiones de ValidationAgent de lucia fallarán con BRIDGE_OFFLINE; para volver a conectar hay que emparejar de nuevo») + botón danger. No exige escribir-para-confirmar (recuperable re-emparejando).
- **Generar token:** invalida cualquier token anterior no usado (aviso inline). El token se muestra **una sola vez**; al salir de la vista no puede recuperarse, solo regenerarse. Botón copiar con feedback «copiado».
- **Expiración del token:** al llegar a 0 el panel pasa a estado expirado con «Generar nuevo token».
- **Archivar perfil** con bridges activos: aviso «2 bridges sirven este perfil — seguirán emparejados pero el perfil no aparecerá en el selector cliente/ambiente». Archivado ≠ borrado (auditabilidad).
- **PROD:** crear/editar un perfil PROD muestra recordatorio de política «solo datos de prueba hacia los LLM (política §3.3)»; un perfil marcado N3 exige confirmar la advertencia «N3 jamás al LLM — la UI lo advertirá en sesión».

### Diferencias por rol

Solo Admin. (El consultor ve sus propios bridges y su token de emparejamiento en *su* configuración personal — otra vista; acá está la flota completa.)

### Móvil

Funcional para lo urgente: revocar un bridge desde el celular es caso real (laptop robada). Tablas → scroll-x; fila de bridge con botón REVOCAR accesible ≥44 px. Generar token también disponible (el consultor está al lado, emparejando).

### Notas i18n

No se traducen: hostnames, versiones, `PROD/TEST/DEV`, `N0–N3`, formato de token, `BRIDGE_OFFLINE`. Countdown con unidades cortas localizables («min»/«s»). El texto legal-operativo de la nota de credenciales es clave i18n única (no concatenar).

---

## 8.4 — Feature flags y kill-switches (`38-admin-flags.html`)

### Propósito

Punto único de control operativo: flags con alcance (global/agente/rol) para encender capacidades sin deploy, kill-switch por agente para emergencias («apagar DocAgent») con razón obligatoria y banner automático a usuarios, y el control D-13: escalación a Pro habilitada/deshabilitada por agente.

### Quién la ve

Solo **Admin**. Acciones: cambiar flags, apagar/encender agentes, habilitar/deshabilitar escalación.

### Layout

```
┌ kicker + h1 ──────────────────────────────────────────────────────────────┐
│ FEATURE FLAGS                                                             │
│ ┌ clave │ descripción │ scope │ estado │ último cambio (quién/cuándo) ┐   │
│ │ workflows.enabled │ … │ GLOBAL │ [on] │ mperez · 09/06/2026 18:40 │ │   │
├────────────────────────────────────────────────────────────────────────────┤
│ KILL-SWITCH POR AGENTE                                                    │
│ ┌ DocAgent ● activo ┐ ┌ ValidationAgent ● activo ┐ ┌ DevAgent ○ APAGADO ┐ │
│ │ [Apagar agente]   │ │ [Apagar agente]          │ │ razón + banner     │ │
│ │                   │ │                          │ │ [Encender]         │ │
│ └ preview del banner que ven los usuarios cuando está apagado ──────────┘ │
├────────────────────────────────────────────────────────────────────────────┤
│ ESCALACIÓN A PRO POR AGENTE (D-13)                                        │
│ ┌ agente │ escalación │ modelo Pro │ último cambio ┐                      │
└────────────────────────────────────────────────────────────────────────────┘
```

### Componentes usados

`.table`, `.tag` para scope (**GLOBAL `--accent` · AGENTE `--info` · ROL neutral**), interruptor accesible (checkbox estilizado rol `switch`), `.panel` por agente con `.live-dot` / `--off`, `.btn--danger` «Apagar agente», `.modal` destructiva con `textarea` de razón obligatoria, banner de degradación (variante `--warn` del `.ai-banner` como preview), `.tag--alt` para escalación, audit inline (texto mono `usuario · fecha`), `.toast`, `.empty-state`, `.skeleton`.

### Datos que muestra

- **Flag:** clave (mono, `workflows.enabled`, `attachments.preview`, `rag.search` — no se traducen), descripción, scope (global / agente:`DocAgent` / rol:`funcional`), estado on/off, **audit inline**: quién lo cambió + cuándo (`mperez · 09/06/2026 18:40`), enlace «historial» (sheet con todos los cambios del flag).
- **Kill-switch por agente:** agente, estado (activo/apagado), si apagado: razón, quién, cuándo, y **preview literal del banner** que ven los usuarios: «DevAgent está temporalmente fuera de servicio — {razón}. Tus sesiones quedan guardadas.»
- **Escalación (D-13):** agente, escalación habilitada sí/no, modelo Pro destino (`deepseek-v4-pro`, mono), quién/cuándo lo cambió. Nota: «si está deshabilitada, el marcador `<<<NEEDS_PRO>>>` no genera tarjeta de escalación en ese agente».

### Estados

- **Carga:** skeleton de tabla + 3 cards.
- **Vacío:** sin flags definidos → empty-state «No hay flags configurados» (los kill-switches y escalación siempre existen: un por agente del catálogo).
- **Error:** cambio de flag falla → el switch vuelve a su estado anterior + toast `--danger` con Reintentar (nunca queda en estado mentiroso).
- **Éxito:** cambio aplicado → toast `--ok` + audit inline se actualiza al instante.
- **Degradado:** agente apagado = estado deliberado, se muestra `--warn` (no rojo): el sistema funciona como se ordenó.

### Interacciones y casos borde

- **Apagar agente** = crítico (§9.2b): modal exige **razón obligatoria** (botón deshabilitado sin texto) y muestra el preview del banner resultante antes de confirmar; con sesiones activas advierte «N sesiones activas recibirán el banner y no podrán enviar mensajes nuevos». Encender = confirmación simple + audit.
- **Flags con scope rol o agente:** el cambio advierte a quién impacta («afecta a 14 usuarios con rol Funcional»).
- **Deshabilitar escalación** con tarjetas NEEDS_PRO ya emitidas: las tarjetas existentes quedan inertes (botón desaparece, queda nota); se advierte en la confirmación.
- **Doble cambio concurrente:** optimistic-lock — si otro Admin cambió el flag entre la carga y mi clic, se rechaza con «el flag cambió hace un momento (lucia) — recargá».
- Ningún flag controla reglas duras: no existe flag para «HITL off» ni para «SQL write» — esa ausencia es deliberada y se documenta con nota al pie de la vista.

### Diferencias por rol

Solo Admin. Los demás roles ven los **efectos**: banner de agente apagado (todos), desaparición de la tarjeta de escalación (todos), capacidades flageadas ocultas (§9.7).

### Móvil

Operable completo: apagar un agente desde el celular a las 2 AM es exactamente el caso de uso. Cards apiladas, modal full-width, razón dictable. Tabla de flags con scroll-x.

### Notas i18n

Claves de flag jamás se traducen (son identificadores). La razón del kill-switch se almacena tal como se escribió (no se traduce). El template del banner usa placeholders nombrados: `«{agente} está temporalmente fuera de servicio — {razón}»` (§12: nunca concatenar). Scopes GLOBAL/AGENTE/ROL traducibles como glosario cerrado.

---

## 8.5 — Configuración de instancia (`40-admin-instancia.html`)

### Propósito

Configurar la identidad y los valores por defecto de **esta instancia** del producto (modelo instancia-por-cliente): nombre, logo, brand, tema e idioma default, texto del acuerdo de uso (versionado con re-aceptación), zona horaria/moneda y datos del licenciatario. Materializa la tabla §2.1 del design system: brand/logo/tema-default son configuración de instancia, no preferencia personal.

### Quién la ve

Solo **Admin**. Una sub-acción (publicar nueva versión del acuerdo de uso) es crítica por su efecto masivo (re-aceptación de todos los usuarios).

### Layout

Formulario seccionado en una columna (máx. 560 px para campos) con previews al lado derecho cuando aplica.

```
┌ kicker + h1 ─────────────────────────── [estado: cambios sin guardar] ───┐
│ IDENTIDAD     nombre ▭          logo: [subir] → preview shell dark/light │
│ APARIENCIA    brand (◉ default ○ totvs — cards con muestra de paleta)    │
│               tema default (◉ dark ○ light) · idioma (es-BO ▾)           │
│ ACUERDO DE USO  versión v3 · publicada 02/05/2026                        │
│               editor (textarea) → al publicar: v4 + re-aceptación        │
│ REGIONAL      zona horaria (America/La_Paz ▾) · moneda (USD · es-BO)     │
│ LICENCIATARIO razón social · NIT · contacto · instancia-id (RO)          │
│                                            [ Guardar cambios ]           │
└───────────────────────────────────────────────────────────────────────────┘
```

### Componentes usados

`.field`/`.input`/`.select`/`.textarea`, radio-cards de brand (panel seleccionable con muestra de los 4 colores clave del brand y borde `--accent` al elegir), upload de logo (input file + zona de preview), **preview del shell en miniatura** (sidebar + topbar de juguete mostrando logo y nombre, en dark y light), `.tag` (versión del acuerdo), `.modal` de confirmación crítica para publicar acuerdo, `.btn--primary` Guardar, `.toast`, `.error-card`, `.kicker` por sección, `.mono` para instancia-id.

### Datos que muestra

- **Identidad:** nombre de instancia («Resultar Bolivia»), logo claro + logo oscuro (PNG/SVG, ≤512 KB; preview inmediato en mini-shell dark y light — Apéndice A exige logo en ambos).
- **Apariencia:** brand (`default` | `totvs`) con preview de paleta; tema default (`dark` | `light`); idioma default (`es-BO` hoy; `pt-BR` listado como disponible-preparado). Nota: «el usuario puede alternar su tema; el brand es de la instancia» (§2.1).
- **Acuerdo de uso:** versión vigente (`v3`), fecha de publicación, texto completo (editor), historial de versiones (fecha, quién publicó, nº de usuarios que ya re-aceptaron). Aviso fijo: «al publicar una nueva versión, todos los usuarios deberán re-aceptarla en su próximo inicio de sesión (checkbox auditado)».
- **Regional:** zona horaria (IANA, `America/La_Paz`), formato de moneda con ejemplo vivo (`USD 1.284,50` — §9.8).
- **Licenciatario:** razón social, NIT, contacto (email), plan, `instancia-id` (mono, solo lectura, copiable).

### Estados

- **Carga:** skeleton del formulario.
- **Vacío:** n/a (la instancia siempre existe); logo sin subir → placeholder con iniciales del nombre.
- **Error:** logo inválido (formato/peso) → field-error inline sin perder el resto del form; guardado fallido → error-card arriba del botón + datos intactos (§9.1).
- **Éxito:** guardar → toast `--ok` «Configuración guardada»; cambios de brand/tema se reflejan en el preview al instante (no en la app del Admin hasta guardar).
- **Degradado:** n/a.

### Interacciones y casos borde

- **Barra de estado «cambios sin guardar»** persistente mientras el form esté sucio; intentar navegar con cambios → confirmación.
- **Publicar acuerdo de uso** = crítico: modal escribir-para-confirmar (tipear `PUBLICAR`), muestra el diff de texto vs versión vigente y el alcance («32 usuarios deberán re-aceptar»). La versión anterior queda en historial, inmutable.
- **Editar el texto sin publicar** guarda borrador local del acuerdo (tag `--info` BORRADOR); el vigente no cambia hasta publicar.
- **Cambiar brand** advierte: «aplica a todos los usuarios al recargar; los temas claro/oscuro personales se conservan».
- **Idioma default** solo afecta usuarios nuevos/sin preferencia; nota explícita.
- Logo: se exige versión clara y oscura o una sola marcada «sirve para ambos» (checkbox); preview muestra ambas combinaciones.

### Diferencias por rol

Solo Admin. Los efectos (logo, brand, acuerdo) los ven todos los roles.

### Móvil

Lectura básica; edición desktop-recomendada (aviso arriba en <768 px: «editá la configuración de instancia desde escritorio»). El historial del acuerdo es legible en móvil.

### Notas i18n

El **texto del acuerdo de uso no es UI**: se versiona tal cual en el idioma en que el Admin lo escriba (si la instancia es bilingüe, el acuerdo lleva ambos textos en el mismo documento — decisión del licenciatario). Identificadores (`instancia-id`, IANA timezone) no se traducen. Labels y avisos por claves; ejemplo de moneda generado con `Intl` según locale elegido (cambia en vivo al cambiar idioma default).

---

## 8.6 — Evals (`43-admin-evals.html`)

### Propósito

Centro de control de calidad de los agentes: suites por agente, corridas (CI y manuales) contra el gate de 80% con `safety` hard-fail, detalle por caso, gestión del golden set, calibración del juez LLM contra el experto humano, y la bandeja que convierte feedback negativo de usuarios en casos de regresión con un clic (regla de CLAUDE.md: «todo bug de producción → caso de regresión en `evals/`»).

### Quién la ve

Solo **Admin**. (Técnico ve el *score de evals de la versión activa* en la ficha técnica — número y fecha, sin detalle por caso.)

### Layout

```
┌ kicker + h1 ─ chips: 3 suites · 124 casos · última corrida CI ✓ 86% ─────┐
│ SUITES POR AGENTE                                                        │
│ ┌ agente │ suite │ casos │ safety │ última corrida │ score │ estado ┐    │
│ CORRIDAS                                       [ Correr suite ▾ ]        │
│ ┌ id │ fecha │ disparador │ prompt │ score │ gate │ safety │ duración ┐  │
│ │ run-512 │ 11/06 09:14 │ CI │ docagent@13 │ 86% │ ✓ │ 0 │ 4m12s │   │  │
│ │ run-511 │ 10/06 22:03 │ manual │ docagent@13 │ 84% │ ✓ │ 1✗ │ BLOQ │  │
│ DETALLE DE CORRIDA run-511 (por caso, safety destacado)                  │
│ ┌ caso │ tags │ esperado │ obtenido │ score │ resultado ┐                │
├───────────────────────────┬───────────────────────────────────────────────┤
│ GOLDEN SET (gestión)      │ CALIBRACIÓN DEL JUEZ LLM                      │
│ tabla de casos etiquetados│ 91% acuerdo con experto · ≥85% · CALIBRADO    │
├───────────────────────────┴───────────────────────────────────────────────┤
│ BANDEJA: FEEDBACK NEGATIVO → CASO CANDIDATO   [Convertir en caso]        │
└────────────────────────────────────────────────────────────────────────────┘
```

### Componentes usados

`.table` + `.table--dense` (corridas, casos), `.tag` (disparador **CI `--info` / MANUAL neutral / PROGRAMADA `--outline`**; resultado **PASS `--money` / FAIL `--danger`**; `safety` `--danger` outline), `.kicker`, display de score en mono (`--money` ≥ gate, `--danger` < gate), `.quota-bar` reutilizada como barra de score vs gate (marca al 80%), `.panel` (calibración con cifra `--fs-display`), `.btn--primary` «Convertir en caso», `.modal` (formulario de caso prellenado), `.empty-state`, `.skeleton`, `.error-card`, `.toast`.

### Datos que muestra

- **Suites:** agente, nombre de suite (`docagent-core.yaml`, mono), nº de casos, nº de casos `safety`, fecha/score de última corrida, estado (verde / en rojo / sin correr).
- **Corridas:** id (`run-512`, mono), fecha-hora, disparador (CI push / manual / programada) + quién (si manual), agente@versión-de-prompt evaluada, score total (%), gate (✓/✗ vs 80%), nº safety fails (≥1 = corrida BLOQUEANTE aunque el score pase — destacado), duración, costo de la corrida (USD, mono — transparencia P2).
- **Detalle por caso:** id, nombre, tags, input (truncado, expandible), esperado (truncado, expandible), obtenido (truncado, expandible), score del juez por caso, resultado PASS/FAIL. Fila `safety` en FAIL: tinte `--danger` + nota «hard-fail individual: bloquea deploy/publicación».
- **Golden set:** caso id, título, etiquetas, origen (**manual / feedback / bug-producción** — tags), agente, última edición (quién/cuándo), acciones (editar, retirar con confirmación).
- **Calibración del juez:** % de acuerdo juez-vs-experto (cifra protagonista), n de casos calibrados, umbral (≥85%), estado (`CALIBRADO` `--money` / `REQUIERE REVISIÓN` `--warn`), fecha de última calibración, botón «Recalibrar con experto».
- **Bandeja de feedback:** usuario (con badge de rol), agente, fecha, sesión (enlace), texto del feedback, estado (pendiente / convertido / descartado), botón «Convertir en caso».

### Estados

- **Carga:** skeletons por sección (las corridas llegan primero; el detalle al seleccionar).
- **Vacío:** bandeja → «No hay feedback negativo pendiente. Cuando un usuario marque una respuesta como incorrecta, va a aparecer acá.»; suite sin corridas → «Sin corridas — corré la suite para obtener un score».
- **Error:** runner caído → error-card `RUNNER_OFFLINE` con Reintentar; las corridas históricas siguen visibles.
- **Éxito:** convertir feedback → toast `--ok` «Caso candidato creado en docagent-core» + el ítem pasa a `convertido` con enlace al caso.
- **Degradado:** corrida en curso → fila con spinner + «en ejecución (2 min)»; juez descalibrado (<85%) → panel `--warn` y nota «los scores de corridas nuevas se marcan como provisorios hasta recalibrar».

### Interacciones y casos borde

- **«Correr suite»** (split-button por agente) pide confirmar costo estimado (USD, mono) — toda corrida gasta tokens y la economía es visible (P2). La corrida aparece de inmediato «en ejecución».
- **Convertir feedback en caso:** un clic abre modal con el caso **prellenado** (input = mensaje del usuario; obtenido = respuesta del agente; esperado = vacío a completar; tags sugeridos). El caso nace con origen `feedback` y entra al golden set como candidato (tag `--info` CANDIDATO) hasta que el Admin complete «esperado» — un candidato incompleto no corre en CI.
- **Safety hard-fail:** la corrida queda BLOQUEANTE; desde el detalle hay enlace directo «ver versión de prompt en el Registro» (cruce con vista 8.1, donde Publicar estará bloqueado).
- **Retirar caso del golden set** = destructivo normal con motivo (el caso queda `retirado`, no se borra — el histórico de corridas lo referencia).
- **Privacidad:** el texto de feedback puede contener datos del cliente — la vista lo trata como dato no confiable (escape) y recuerda la política de datos de prueba al convertir.
- Paginación clásica en corridas (auditabilidad, §9.5).

### Diferencias por rol

Solo Admin. Técnico: score agregado en ficha técnica (sin detalle). Funcional: solo el efecto («Enviar feedback» en el chat alimenta la bandeja).

### Móvil

Lectura: tablas scroll-x, detalle de caso apilado. «Correr suite» y «Convertir en caso» quedan disponibles pero el formulario de caso es desktop-recomendado.

### Notas i18n

No se traducen: ids (`run-512`), nombres de suite/archivo, tags de dataset (`safety`, `bol-localization`), nombres de modelo. PASS/FAIL se mantienen en mono sin traducir (vocabulario del runner); su explicación adyacente sí se traduce. Porcentajes con formato local (`86%` sin espacio). Costos `USD 0,42` (es-BO).

---

## Trazabilidad de decisiones

| Decisión | Vista | Manifestación |
|---|---|---|
| ADR-0011 prompts inmutables + gate por sistema | 8.1 | published solo-lectura; Publicar deshabilitado con motivo; gate evaluado contra hash |
| ADR-0001/0006 toolset fijo, stickiness | 8.2 | aviso «aplica a sesiones nuevas»; drift de schema como alerta de primera clase |
| Credenciales solo en laptop del consultor | 8.3 | perfiles sin campo de credencial + nota fija; emparejamiento por token efímero |
| HITL no desactivable para escrituras | 8.2 | checkbox HITL bloqueado en escritura/destructiva |
| D-13 escalación por agente | 8.4 | sección propia con audit |
| Re-aceptación del acuerdo auditada | 8.5 | versionado del acuerdo + escribir-para-confirmar |
| Gate 80% + safety hard-fail | 8.1 y 8.6 | score vs gate visible; fila safety destacada; corrida BLOQUEANTE |
| Feedback → caso de regresión | 8.6 | bandeja con conversión a un clic y estado CANDIDATO |
