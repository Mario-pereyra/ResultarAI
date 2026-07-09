# Módulo 01 — Acceso y shell

> **Estado:** v1.0. Sistema de diseño: [`../DESIGN-SYSTEM.md`](../DESIGN-SYSTEM.md) · Tokens: [`../mockups/tokens.css`](../mockups/tokens.css).
> Mockups: [`01-login.html`](../mockups/01-login.html) · [`02-primer-acceso.html`](../mockups/02-primer-acceso.html) · [`03-shell.html`](../mockups/03-shell.html) · [`04-notificaciones.html`](../mockups/04-notificaciones.html).
> Decisiones de producto que gobiernan este módulo: instancia por cliente (branding = config de instancia) · sin registro público (cuentas las crea el Admin) · TOTP obligatorio para Admin · una sola UI con capas por rol (ocultar, no deshabilitar — DS §9.7) · banner IA permanente · acuerdo de uso auditado en primer login.

---

## Vista 1 — Login (`01-login.html`)

### Propósito
Puerta de entrada de la instancia. Autentica usuario+contraseña y, como segundo paso, el challenge TOTP cuando aplica. Comunica la identidad de la instancia (logo + nombre) y deja claro que **no existe registro**: las cuentas las crea el administrador.

### Quién la ve
Todos (usuario no autenticado). No hay variación por rol antes de autenticar; el TOTP del paso 2 aparece para Admin **siempre** y para Técnico/Funcional solo si lo enrolaron.

### Layout
Pantalla centrada, una sola columna, card ≤400 px sobre `--bg`. Sin sidebar, sin topbar; el banner IA no aparece (no hay contenido generado).

```
┌──────────────────────────────────────┐
│                                      │
│        [logo instancia]              │
│        NOMBRE DE INSTANCIA  (kicker) │
│   ┌────────────────────────────┐     │
│   │ Iniciar sesión        (h2) │     │
│   │ [error-card si falla]      │     │
│   │ Usuario        [input]     │     │
│   │ Contraseña     [input 👁]   │     │
│   │ [ Ingresar ──────────── ]  │     │
│   ├────────────────────────────┤     │
│   │ ⓘ Las cuentas las crea el  │     │
│   │   administrador…           │     │
│   └────────────────────────────┘     │
│        v1.0 · es-BO     (faint)      │
└──────────────────────────────────────┘
```

Paso 2 (TOTP) reemplaza el contenido de la card: título «Verificación en dos pasos», 6 casillas de un dígito (o un input de 6), enlace «← Volver», botón «Verificar».

### Componentes usados
`.panel--raised` (card) · `.field` + `.input` (usuario, contraseña con toggle mostrar/ocultar `.btn--ghost` con `aria-pressed`) · `.input--mono` (código TOTP) · `.btn--primary --block --lg` (Ingresar/Verificar) · `.error-card` (credenciales inválidas — `--warn` no: es `danger`) · `.error-card--warn` no aplica; bloqueada usa `danger` · `.kicker` (nombre de instancia) · texto-hint con ícono `info`.

### Datos que muestra
- Logo de instancia (asset de config) + nombre de instancia (string de config; ej. «Resultar Bolivia»).
- Campos: `usuario` (texto, autocomplete="username"), `contraseña` (password, autocomplete="current-password").
- Paso TOTP: `código` (6 dígitos, inputmode="numeric", autocomplete="one-time-code") + nombre de usuario en verificación («lucia») para confirmar identidad.
- Pie: versión de la plataforma + locale (mono, `--ink-faint`).
- **No** muestra: enlace de registro, recuperación self-service de contraseña (la resetea el Admin — el hint lo dice).

### Estados
- **Carga (submit):** botón `.btn--loading` + `aria-busy`; campos `disabled` durante el round-trip.
- **Vacío:** estado inicial; foco en `usuario`.
- **Error — credenciales inválidas:** error-card `role="alert"` arriba del form: «Usuario o contraseña incorrectos» + por qué genérico (no revelar cuál de los dos falló) + «Reintentar». Los campos conservan el usuario, limpian la contraseña, foco a contraseña.
- **Error — cuenta bloqueada por intentos:** error-card código `ACCOUNT_LOCKED`: «Cuenta bloqueada temporalmente» / «Demasiados intentos fallidos. Se desbloquea en 15 min o pedile al administrador que la libere.» Form deshabilitado (excepción justificada a §9.7: el bloqueo es temporal y el motivo está al lado).
- **Error — TOTP inválido:** inline en el paso 2, contador de intentos restantes; al 3.º fallido vuelve a `ACCOUNT_LOCKED`.
- **Éxito:** redirige al shell (última sección visitada o Catálogo).
- **Degradado — gateway de auth caído:** error-card `AUTH_OFFLINE` «El servicio no está disponible» + Reintentar.

### Interacciones y casos borde
- Enter envía el form. El toggle de contraseña no rompe el orden de tabulación.
- Rate-limit progresivo del lado servidor; la UI solo refleja `ACCOUNT_LOCKED`.
- Sesión expirada → vuelve al login con toast info «Tu sesión expiró, ingresá de nuevo» (sin perder la URL destino: redirect post-login).
- TOTP: pegar un código de 6 dígitos lo distribuye/acepta completo; «Volver» regresa al paso 1 sin perder el usuario.
- Usuario deshabilitado por Admin → mismo mensaje genérico de credenciales inválidas (no filtrar existencia/estado de cuentas).
- Primer login detectado → tras autenticar, redirige obligatoriamente al wizard de primer acceso (Vista 2); no hay forma de saltarlo.

### Diferencias por rol
Ninguna visible pre-auth. Post-auth: Admin → siempre paso TOTP; Técnico/Funcional → paso TOTP solo si enrolado.

### Móvil
Card a ancho completo menos `--sp-4`; inputs ≥44 px de alto táctil; teclado numérico en TOTP (`inputmode="numeric"`).

### Notas i18n
Textos externalizados; «Las cuentas las crea el administrador de tu organización» reserva +25%. No traducir códigos (`ACCOUNT_LOCKED`, `AUTH_OFFLINE`). Voseo: «pedile al administrador», «ingresá».

---

## Vista 2 — Primer acceso (`02-primer-acceso.html`)

### Propósito
Wizard obligatorio del primer login: (1) cambio de contraseña, (2) enrolamiento TOTP, (3) acuerdo de uso auditado. Hasta no completarlo, el usuario no entra al shell.

### Quién la ve
Todo usuario nuevo (cuenta recién creada por el Admin) o con contraseña reseteada. El paso TOTP es **obligatorio para Admin** y **opcional (saltable) para Técnico/Funcional**; el resto de pasos son idénticos para todos.

### Layout
Misma puesta en escena que el login (centrada, sin sidebar), card ≤480 px con indicador de pasos arriba (timeline `.wf` horizontalizada o dots numerados 1·2·3).

```
┌──────────────────────────────────────────┐
│  [logo]  Primer acceso                   │
│  (1)──(2)──(3)   pasos: contraseña ·     │
│                  TOTP · acuerdo          │
│  ┌────────────────────────────────────┐  │
│  │ PASO ACTIVO                        │  │
│  │ …contenido del paso…               │  │
│  │            [Atrás] [Continuar →]   │  │
│  └────────────────────────────────────┘  │
└──────────────────────────────────────────┘
```

**Paso 1 — Contraseña nueva:** contraseña actual (la temporal) + nueva + repetir, con **medidor de fortaleza** (barra 4 segmentos: débil `--danger` / regular `--warn` / buena `--info` / fuerte `--money`, siempre con palabra) y checklist de requisitos (≥12 caracteres, mayúscula+minúscula, número, símbolo) que se tachan en vivo.
**Paso 2 — TOTP:** QR (placeholder en mockup) + clave manual mono copiable + input de 6 dígitos para confirmar el enrolamiento. Para no-Admin: botón ghost «Configurar más tarde». Para Admin: sin salida — hint «Tu rol requiere verificación en dos pasos».
**Paso 3 — Acuerdo de uso:** resumen en panel scrolleable con los puntos duros: *no pegar datos reales de clientes ni credenciales (niveles N0-N3; N3 jamás)* · *las respuestas son generadas por IA, verificá antes de aplicar* · *toda la actividad queda registrada y es auditable*. Enlace «Leer el acuerdo completo». Checkbox «Leí y acepto el acuerdo de uso» + nota explícita: «Tu aceptación queda registrada con fecha, hora y versión del acuerdo.» Botón final «Aceptar y entrar».

### Componentes usados
`.wf` (indicador de pasos, variante compacta) · `.field`/`.input` · medidor de fortaleza (composición de `.quota-bar` reutilizada con colores semánticos) · checklist con íconos check/x · `.panel--flush` (QR) · `.chip` o bloque mono copiable (clave TOTP) · `.check-row` + `.checkbox` (acuerdo) · `.btn--primary` / `.btn--ghost` · `.error-card`.

### Datos que muestra
- Usuario y rol (badge-rol) en cabecera del wizard — el usuario confirma quién es.
- Paso 1: campos contraseña; fortaleza calculada client-side; requisitos de la política.
- Paso 2: QR `otpauth://`, clave en Base32 (`RSLT AB12 CD34 …`), nombre de cuenta que verá la app («Resultar · lucia»).
- Paso 3: versión del acuerdo (`acuerdo-uso v1.2 · 03/05/2026`), resumen, checkbox.

### Estados
- **Carga:** transición entre pasos con loading en botón; verificación del TOTP con spinner.
- **Error paso 1:** nueva contraseña no cumple política (inline `.is-invalid` + lista de pendientes) · no coincide la repetición · igual a la temporal.
- **Error paso 2:** código TOTP incorrecto («Código incorrecto o vencido — los códigos rotan cada 30 s») con reintento ilimitado (todavía no protege nada).
- **Error paso 3 / submit final:** error-card de servidor; nada se pierde.
- **Éxito:** toast ok «Cuenta lista» + entra al shell.
- **Degradado:** sin reloj sincronizado (TOTP falla repetido) → hint «verificá la hora del teléfono».

### Interacciones y casos borde
- No se puede cerrar/saltar el wizard; logout es la única salida (y al volver, retoma en el paso pendiente — el progreso de pasos completados persiste).
- «Atrás» disponible entre pasos pero el paso 1 completado no se repite (la contraseña ya cambió: atrás desde 2 muestra el 1 en solo-lectura con check).
- Copiar clave TOTP → feedback «copiada» accesible (`aria-live`).
- Si el rol cambia de Funcional a Admin después, el sistema fuerza enrolamiento TOTP en el siguiente login (reusa el paso 2 standalone).
- El checkbox del acuerdo deshabilita «Aceptar y entrar» hasta marcarse (deshabilitar con motivo visible — §9.7 caso legítimo).

### Diferencias por rol
| Paso | Admin | Técnico / Funcional |
|---|---|---|
| Contraseña | obligatorio | obligatorio |
| TOTP | obligatorio (sin «más tarde») | opcional, saltable |
| Acuerdo | obligatorio | obligatorio |

### Móvil
Wizard a una columna; QR ≥200 px; en móvil suele ser el mismo dispositivo que la app TOTP → la clave manual copiable es la vía principal (hint lo sugiere).

### Notas i18n
Textos de política de contraseña y resumen de acuerdo desde catálogo (legal varía por instancia/idioma). Versión del acuerdo no se traduce. Plurales ICU en «quedan {n} requisitos».

---

## Vista 3 — Shell de aplicación (`03-shell.html`)

### Propósito
Marco persistente de toda la app autenticada: navegación lateral, topbar contextual, banner IA permanente y el slot de contenido. Materializa la regla «una sola UI con capas por rol».

### Quién la ve
Todos los roles autenticados. Las capas agregan secciones e instrumentos según rol; lo que un rol no tiene **no se renderiza**.

### Layout
Ver DS §6.1. Banner IA arriba (28 px, permanente — el mockup lo ubica arriba; si producto lo decide abajo, es un cambio de slot, no de anatomía), sidebar 240 px (colapsable a 64), topbar 56 px, contenido.

```
┌─────────────────────────────────────────────────────┐
│ ⚠ Respuestas generadas por IA — verificá antes de   │
│   aplicar en cliente                     (ai-banner)│
├──────────┬──────────────────────────────────────────┤
│ [logo]   │ [buscador global ⌘K]  [☾] [🔔3] [lucia ▾]│
│ Catálogo │  (Admin: ● gateway · deepseek-v4-flash)  │
│ Chat     ├──────────────────────────────────────────┤
│ Workflows│                                          │
│ Aprobac.③│            CONTENIDO                     │
│ Mi espac.│                                          │
│ ──────── │                                          │
│ Administr│  ← solo Admin                            │
│ Construcc│  ← solo Admin                            │
│ ──────── │                                          │
│ [≡ colap]│                                          │
└──────────┴──────────────────────────────────────────┘
```

**Sidebar** (orden fijo): Catálogo (`layout-grid`) · Chat (`message-square`) · Workflows (`list-checks`) · Aprobaciones (`shield-check`, **badge contador** de pendientes) · Mi espacio (`user`) — y para Admin, tras divisor con kicker «ADMIN»: Administración (`settings-2`) · Construcción (`hammer`). Abajo: botón colapsar. Ítem activo: fondo `--accent-soft` + barra 2 px `--accent` a la izquierda + texto `--accent`.

**Topbar:** buscador global opcional (input con atajo `Ctrl K`, placeholder «Buscar agentes, sesiones, docs…») · switcher de tema (sol/luna, persiste por usuario) · campana `.notif-bell` (abre Vista 4) · menú de usuario (avatar iniciales + nombre + **badge-rol visible**: dropdown con Mi espacio / Tema / Cerrar sesión). **Solo Admin:** a la izquierda de la campana, estado del gateway: `live-dot` (verde ok / ámbar degradado / rojo caído) + perfil LLM activo en mono (`deepseek-v4-flash`), con tooltip y enlace a telemetría.

**Banner IA:** `.ai-banner`, presente en TODAS las vistas autenticadas, todos los roles, no descartable.

### Componentes usados
`.ai-banner` · sidebar (composición: nav `<nav aria-label="Principal">` + ítems con ícono 20 + label) · `.notif-bell` + `__count` · `.badge-rol` · `.live-dot` · `.input` (buscador) · `.tag` mono (perfil LLM) · tooltip `[data-tip]` · skip-link (sr-only hasta focus).

### Datos que muestra
- Logo+nombre de instancia (sidebar header).
- Contador de aprobaciones pendientes **visibles para el usuario** (badge sidebar; se oculta en 0).
- Contador de notificaciones no leídas (campana).
- Usuario: nombre, iniciales, rol.
- Admin: estado gateway (`ok|degradado|caído`) + `model_profile` activo del gateway.
- Estado de colapso del sidebar y tema: persisten por usuario.

### Estados
- **Carga:** shell pinta primero (estático); contadores llegan después (badges con skeleton breve o aparecen al llegar — sin saltos de layout: reservar el ancho).
- **Vacío:** badge de aprobaciones ausente si 0; campana sin contador.
- **Error/Degradado:** gateway caído → dot rojo (Admin) y, para todos, las vistas de chat mostrarán `GATEWAY_OFFLINE`; el shell en sí no bloquea. Telemetría diferida → dot ámbar.
- **Éxito:** estado normal.

### Interacciones y casos borde
- Colapsar sidebar → 64 px, solo íconos con tooltip; el badge de Aprobaciones se conserva sobre el ícono; estado persistido.
- `Ctrl/⌘+K` enfoca el buscador desde cualquier vista.
- El switcher de tema alterna `data-theme` y persiste; el brand NO es conmutable por el usuario (config de instancia).
- Cambio de rol en caliente (Admin edita al usuario): aplica en el siguiente login; el shell no muta en vivo.
- Badge de aprobaciones >99 → «99+».
- Skip-link «Saltar al contenido» como primer foco.

### Diferencias por rol
| Elemento | Funcional | Técnico | Admin |
|---|---|---|---|
| Catálogo · Chat · Workflows · Aprobaciones · Mi espacio | ✅ | ✅ | ✅ |
| Administración · Construcción | — (no existe) | — (no existe) | ✅ |
| Taxímetro en topbar (en vistas de chat) | — | ✅ | ✅ |
| Dot gateway + perfil LLM en topbar | — | — | ✅ |
| Buscador global · tema · campana · menú usuario · banner IA | ✅ | ✅ | ✅ |
| Badge de rol en menú de usuario | FUNCIONAL | TÉCNICO | ADMIN |

Aprobaciones es de todos: cualquier rol puede ser aprobador asignado; la lista muestra lo suyo.

### Móvil
<768 px: sidebar → **drawer** sobre scrim (botón hamburguesa a la izquierda del topbar; cierre por scrim/Esc/swipe); topbar conserva hamburguesa + campana + avatar (buscador dentro del drawer; dot gateway de Admin pasa al drawer); banner IA permanece (texto puede acortarse a «Respuestas generadas por IA — verificá antes de aplicar»). Drawer con trampa de foco y `aria-modal`.

### Notas i18n
Labels de navegación cortas y externalizadas (PT-BR: «Aprovações» etc.); el ancho de 240 px ya reserva el +25%. El texto del banner es clave de catálogo única por instancia/idioma.

---

## Vista 4 — Panel de notificaciones (`04-notificaciones.html`)

### Propósito
Dropdown de la campana: agrupa lo accionable (aprobaciones, cuotas, sistema), permite marcar leído y saltar al destino. No es un centro de mensajería: cada ítem referencia algo que existe en una vista.

### Quién la ve
Todos. El **contenido** se filtra por rol (ver tabla abajo).

### Layout
Dropdown anclado a la campana, 380 px, max-height 70vh con scroll; en móvil, sheet a pantalla completa.

```
┌──────────────────────────────────┐
│ Notificaciones      [Marcar leídas]│
├──────────────────────────────────┤
│ APROBACIONES PENDIENTES  (kicker)│
│ ●🛡 Escritura MV_* — Comercial   │
│     Andina S.A./TEST · RIESGO    │
│     ALTO · expira en 5 h   [Ver] │
├──────────────────────────────────┤
│ CUOTAS                           │
│ ●⚠ Tu cuota mensual al 82%  [Ver]│
│  ⛔ Cuota del grupo bloqueada     │
├──────────────────────────────────┤
│ SISTEMA (solo Admin)             │
│ ●🔌 Bridge de Comercial Andina   │
│     offline desde 14:32    [Ver] │
│  ✖ Eval docagent@13: 76% — deploy│
│     bloqueado              [Ver] │
│  ✖ Backup nocturno falló   [Ver] │
├──────────────────────────────────┤
│            Ver todas             │
└──────────────────────────────────┘
```

### Componentes usados
`.notif-bell` (disparador) · panel `.panel--flush --raised` · `.kicker--dim` (grupos) · ítem de notificación (composición: punto no-leído `--accent` + ícono semántico 16 + título 13 px + meta mono 12 px + acción «Ver») · `.tag` de riesgo (mapa DS §8.6) · `.live-dot--warn` (crítica pulsante) · `.empty-state` · `.skeleton`.

### Datos que muestra
Por ítem: tipo (ícono+grupo) · título con entidades concretas (cliente final ficticio, parámetro, agente) · severidad cuando aplica (tag riesgo / warn / danger) · tiempo relativo (`hace 12 min`, absoluto en tooltip) · expiración si HITL (`expira en 5 h`) · estado leído/no-leído (punto + peso tipográfico).
Grupos y tipos:
- **Aprobaciones:** pendiente asignada a vos (con riesgo y expiración) · resuelta por otro (informativa) · expirada.
- **Cuotas:** aviso 80% (propia) · bloqueo 100% (propia o del grupo) · liberación concedida.
- **Sistema (solo Admin):** bridge offline · VPN/gateway degradado o caído · eval fallida (deploy bloqueado) · backup fallido · caída de proveedor LLM.

### Estados
- **Carga:** 3 ítems skeleton.
- **Vacío:** empty-state «Estás al día» + hint «Acá vas a ver aprobaciones, avisos de cuota y novedades del sistema.»
- **Error:** error-card compacta «No se pudieron cargar las notificaciones» + Reintentar.
- **Éxito:** lista agrupada; los grupos sin ítems no se renderizan.
- **Crítica:** HITL de riesgo crítico → ítem destacado con `live-dot--warn` y orden prioritario.

### Interacciones y casos borde
- Click en ítem o «Ver» → navega al destino (tarjeta HITL, Mi espacio→cuota, telemetría) y marca leído.
- «Marcar leídas» = todas las visibles del usuario; los pendientes HITL siguen contando en el badge del sidebar (el badge cuenta pendientes reales, no no-leídos).
- Notificación cuyo objeto ya no existe (aprobación resuelta/expirada) → al click muestra el estado final, nunca 404.
- Llegada en vivo: contador sube sin robar foco; sin toasts duplicados para lo que ya notifica la campana (excepto HITL crítica: toast warn además).
- Máx. ~7 ítems en dropdown; «Ver todas» → vista completa paginada (módulo Mi espacio/Actividad).
- Teclado: flechas entre ítems, Enter abre, Esc cierra y devuelve foco a la campana.

### Diferencias por rol
| Tipo | Funcional | Técnico | Admin |
|---|---|---|---|
| Aprobaciones (asignadas a vos / resueltas) | ✅ | ✅ | ✅ (todas las de su alcance) |
| Cuota propia 80%/100% · liberación | ✅ | ✅ | ✅ |
| Cuota de grupo/global | — | — | ✅ |
| Sistema: bridge/VPN/gateway | — («el asistente no está disponible» lo verá en contexto, sin jerga) | — | ✅ |
| Eval fallida · backup fallido · proveedor caído | — | — | ✅ |

Redacción por rol: Funcional jamás ve códigos ni jerga (DS §4.2); Técnico/Admin ven códigos mono.

### Móvil
Sheet a pantalla completa con header fijo («Notificaciones» + cerrar); ítems ≥44 px; «Ver» como toda-la-fila tappable.

### Notas i18n
Tiempos relativos por `Intl.RelativeTimeFormat`; plantillas con placeholders nombrados («{agente} solicita aprobar {n} escrituras en {cliente}/{ambiente}»); plurales ICU; códigos y nombres de modelo sin traducir.
