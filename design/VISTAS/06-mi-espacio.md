# 06 — Mi espacio (perfil)

> **Módulo de documentación de diseño** — Resultar Agents Platform. No es código de producción.
> Sistema visual: [`../DESIGN-SYSTEM.md`](../DESIGN-SYSTEM.md) · tokens: [`../mockups/tokens.css`](../mockups/tokens.css).
> Decisiones de producto que este módulo materializa: ADR-0007 (cuotas jerárquicas), ADR-0010 §1 (memoria snapshot) y §4 (consumo propio), UX-SPEC §8/§10b/§10e, política §3.3 (datos N0–N3).

## Alcance del módulo

«Mi espacio» es el área personal de **todos los roles** (Admin, Técnico, Funcional). Es una sola sección del shell con cuatro vistas internas navegadas por tabs:

| # | Vista | Mockup | Ruta propuesta |
|---|---|---|---|
| 23 | Mi consumo | [`23-mi-consumo.html`](../mockups/23-mi-consumo.html) | `/espacio/consumo` |
| 24 | Mi memoria | [`24-mi-memoria.html`](../mockups/24-mi-memoria.html) | `/espacio/memoria` |
| 25 | Mi auditoría | [`25-mi-auditoria.html`](../mockups/25-mi-auditoria.html) | `/espacio/auditoria` |
| 26 | Configuración personal | [`26-config-personal.html`](../mockups/26-config-personal.html) | `/espacio/configuracion` |

**Punto de entrada:** menú del avatar en la topbar («Mi espacio») y, en móvil, el drawer de navegación. La sección existe para todos los roles — lo que cambia por rol son capas internas (§9.7 del design system: lo que un rol no tiene **no se renderiza**).

**Principio rector del módulo:** transparencia personal. Acá el usuario ve lo que la plataforma sabe de él (memoria), lo que gasta (consumo), lo que hizo (auditoría) y controla su cuenta (configuración). Nada oculto, nada editable a espaldas del usuario.

**Navegación interna:** tabs de ruta (nav-links, no tabs ARIA — design system §8.7): «Mi consumo · Mi memoria · Mi auditoría · Configuración». Orden fijo; ninguna tab se oculta por rol (las cuatro aplican a todos).

---

## Vista 23 — Mi consumo

### Propósito

Que cada usuario vea su consumo del día y del mes contra sus cuotas **antes** de chocar con el límite («nadie llega al límite por sorpresa», ADR-0010 §4), entienda qué sesiones consumieron qué, y pueda pedir liberación cuando está bloqueado — con el estado de esa solicitud visible. Para el Admin, la misma vista agrega su capa de telemetría personal (anillo de cache hit y hit-rate por sesión) sin cambiar la estructura.

### Quién la ve (roles y capacidades)

| Rol | Acceso | Capa visible |
|---|---|---|
| Funcional | ✅ | Base: barras de cuota (hoy/mes) + sesiones recientes (agente, inicio, turnos, costo). Sin tokens, sin cache, sin nombres de modelo. |
| Técnico | ✅ | Base + columna **Tokens** en sesiones recientes (el técnico ya ve tokens en el chat: taxímetro/chips). **Sin** anillo de cache ni hit-rate: la telemetría agregada es exclusiva del Admin. |
| Admin | ✅ | Base + Tokens + **capa de telemetría**: anillo de cache hit del mes, columna **Hit-rate** por sesión, ahorro estimado por cache. |

Nota de decisión: el **costo en USD aparece para todos los roles en esta vista** (incluido Funcional) porque la cuota se define en presupuesto (ADR-0007) y la barra «usado/límite» sería ilegible sin la cifra. La regla «Funcional no ve costos» aplica a la experiencia de chat (taxímetro, costo por turno), no a su propia página de consumo, que existe precisamente para la transparencia del límite. Lo que Funcional jamás ve: tokens, cache, modelos.

### Layout (descripción + wireframe)

Página de dos zonas: arriba las dos tarjetas de cuota (Hoy / Este mes) lado a lado; debajo, panel de telemetría (solo Admin) y tabla de sesiones recientes. Contenido máx. 1200 px.

```
┌──────────────────────────────────────────────────────────────┐
│ MI ESPACIO                                                   │
│ Mi consumo                                                    │
│ [Mi consumo]·[Mi memoria]·[Mi auditoría]·[Configuración]      │
├──────────────────────────┬───────────────────────────────────┤
│ HOY                      │ ESTE MES                          │
│ USD 1,12 / USD 5,00      │ USD 41,20 / USD 50,00             │
│ ▓▓▓░░░░░░░ 22%           │ ▓▓▓▓▓▓▓▓░░ 82%  ⚠ aviso 80%      │
│ se renueva a medianoche  │ se renueva el 01/07               │
├──────────────────────────┴───────────────────────────────────┤
│ (SOLO ADMIN) CACHE — anillo 87% + leyenda + ahorro estimado  │
├──────────────────────────────────────────────────────────────┤
│ SESIONES RECIENTES                                            │
│ agente · inicio · turnos · costo [· tokens · hit-rate]        │
│ DocAgent        11/06 14:32   12   USD 0,18   48,2k    91%    │
│ ValidationAgent 10/06 16:48   21   USD 0,42   96,7k    88%    │
└──────────────────────────────────────────────────────────────┘
```

El mockup muestra las variantes **Funcional y Admin lado a lado** (andamiaje de documentación, no UI real) y debajo la escalera completa de estados de cuota.

### Componentes usados

`.panel`, `.quota-row` + `.quota-bar` (estados `is-warn`/`is-over`), `.table` dentro de `.panel--flush`, `.error-card` (código `QUOTA`), `.btn--primary` («Solicitar liberación»), `.tag` (`--warn` PENDIENTE, `--money` CONCEDIDA, `--danger` RECHAZADA), `.badge-rol`, `.kicker`, `.skeleton`, `.empty-state`, anillo SVG de cache (composición local con tokens, solo Admin), `.toast--ok` (confirmación de solicitud enviada).

### Datos que muestra (campos exactos)

**Tarjeta de cuota (×2: `hoy`, `mes`):**
- `scope` («Hoy» / «Este mes»)
- `used_usd`, `limit_usd` — formato es-BO mono: `USD 1,12 / USD 5,00`
- `pct` — entero, sin espacio: `22%`
- `renews_at` — texto humano: «se renueva a medianoche» / «se renueva el 01/07/2026»
- `estado` ∈ ok (<80%) · warn (≥80%) · bloqueado (≥100%)
- Si bloqueado: `liberacion.estado` ∈ sin_solicitar · pendiente · concedida · rechazada, `liberacion.solicitada_hace`, `liberacion.monto_extra` (si concedida: «límite ampliado a USD 7,00 por hoy»)

**Anillo de cache (solo Admin):** `cache_hit_rate_mes` (87%), `ahorro_estimado_usd_mes` (USD 12,40), leyenda hit/miss.

**Tabla «Sesiones recientes»** (últimas 10, orden inicio desc):
- `agente` (nombre + ícono `bot`)
- `inicio` — `dd/mm/aaaa HH:mm` mono
- `turnos` — entero, columna `.num`
- `costo` — `USD 0,18`, columna `.num` en `--money`
- `tokens` (Técnico/Admin) — `48,2k tok`, `.num`
- `hit_rate` (solo Admin) — `91%`, `.num`; si <60% acompañado de tag `--warn` BAJO (detecta uso que rompe cache, ADR-0010 §4)

### Estados

- **Carga:** skeleton con la silueta real — 2 tarjetas de cuota (título 50% + barra) y 4 filas de tabla. `aria-busy="true"`.
- **Vacío:** tarjetas de cuota en `USD 0,00 / límite` (la cuota siempre existe) + empty-state en la tabla: «Todavía no usaste ningún agente este mes. Cuando abras tu primera conversación, va a aparecer acá.» CTA «Ir al catálogo».
- **Error:** error-card en lugar del cuerpo: «No pudimos cargar tu consumo» + por qué + «Reintentar». Las cuotas, si vienen de otro origen y cargaron, se conservan.
- **Éxito (flujo liberación):** al enviar la solicitud → toast `--ok` «Solicitud enviada — el Admin va a recibir una notificación» + el botón pasa a deshabilitado con tag `PENDIENTE` («enviada hace 12 min»). Concedida → tag `--money` CONCEDIDA + barra recalculada con el límite ampliado + toast. Rechazada → tag `--danger` RECHAZADA + motivo del Admin en texto.
- **Degradado:** si la telemetría (Langfuse) no responde, los montos se muestran con `~` antepuesto y nota «costo estimado, telemetría diferida» (mismo patrón que el taxímetro §8.12). El anillo de cache muestra `—`.

### Interacciones y casos borde

- **«Solicitar liberación»** solo aparece con cuota al 100% (estado bloqueado). Un clic → confirma envío (sin modal: acción no destructiva), notifica al Admin, queda en audit log (ADR-0007). Doble clic bloqueado (loading). Mientras hay una solicitud `pendiente`, el botón no se re-renderiza: se muestra el estado.
- La fila de sesión **navega a la conversación** (toda la fila = un enlace explícito, §8.4): caso borde — sesión en rama: abre la rama activa.
- Cuota diaria bloqueada pero mensual sana: el bloqueo es real (el gateway evalúa todos los niveles, ADR-0007); la tarjeta «Hoy» manda y la de mes queda informativa.
- Cambio de estado 79%→80% **mientras la vista está abierta:** la barra cambia a warn y se anuncia por `aria-live="polite"` (§8.11).
- Liberación concedida que expira (fin del día): la barra vuelve al límite normal sin avisos adicionales.
- El usuario nunca ve consumo de otros: esta vista es estrictamente personal (la agregación por usuario/grupo vive en la consola Admin).

### Diferencias por rol

| Elemento | Funcional | Técnico | Admin |
|---|---|---|---|
| Barras de cuota hoy/mes (USD) | ✅ | ✅ | ✅ |
| Sesiones: agente/inicio/turnos/costo | ✅ | ✅ | ✅ |
| Columna tokens | — | ✅ | ✅ |
| Anillo cache hit + ahorro | — | — | ✅ |
| Columna hit-rate | — | — | ✅ |
| «Solicitar liberación» y su estado | ✅ | ✅ | ✅ (puede auto-liberarse desde consola; acá ve lo mismo) |

Lo no visible **no se renderiza** (ni columnas vacías ni candados).

### Móvil

✅ Funcional completo. Tarjetas de cuota apiladas (1 columna); tabla con scroll-x y sombra de affordance; el anillo de cache (Admin) se centra arriba de la tabla. «Solicitar liberación» full-width. Objetivos táctiles ≥44 px.

### Notas i18n

- Claves externalizadas: `espacio.consumo.*`. Plurales ICU para turnos: `{n, plural, one {# turno} other {# turnos}}`.
- Números/fechas por `Intl` es-BO (coma decimal, `dd/mm/aaaa`); preparado pt-BR.
- No se traducen: `QUOTA` (código), nombres de agentes (nombres propios del catálogo).
- Reservar +25% en «Solicitar liberación» (pt-BR: «Solicitar liberação» similar, pero el estado «enviada hace 12 min» crece).

---

## Vista 24 — Mi memoria

### Propósito

Dar control total sobre la memoria personal (ADR-0010 §1, UX-SPEC §10b): el usuario ve **en claro** qué sabe la plataforma de él, edita el texto fuente con límite duro (~1.000 tokens), guarda con confirmación obligatoria entendiendo que **el cambio aplica recién desde su próxima conversación** (snapshot por sesión — preserva el cache y el append-only), borra todo si quiere, y revisa el historial de sus propios cambios. El validador bloquea credenciales y datos personales (N3) con explicación.

### Quién la ve (roles y capacidades)

Todos los roles, idéntica para todos: la memoria es personal y su mecánica no es jerga técnica (se explica en lenguaje claro). Ningún rol ve ni edita la memoria de otro usuario — tampoco el Admin (el Admin puede *borrar* memorias desde consola por política, pero jamás leer/editar contenido ajeno desde esta vista; eso queda fuera de este módulo).

### Layout (descripción + wireframe)

Dos columnas en desktop: editor (principal, máx. 760 px) + panel lateral «Qué sabe la plataforma de vos» (320 px). Debajo, historial de cambios. Formularios según §8.2.

```
┌──────────────────────────────────────────────────────────────┐
│ MI ESPACIO — Mi memoria          [tabs]                       │
│ ⓘ La memoria se aplica al CREAR una conversación nueva.       │
├───────────────────────────────────┬──────────────────────────┤
│ TU MEMORIA (editable)             │ QUÉ SABE LA PLATAFORMA   │
│ ┌───────────────────────────────┐ │ DE VOS (en claro)        │
│ │ textarea                      │ │ · Rol y área             │
│ │                               │ │ · Clientes que atendés   │
│ └───────────────────────────────┘ │ · Módulos que dominás    │
│ ▓▓▓▓░░░░ ≈412 / 1.000 tokens      │ · Preferencias de formato│
│ [Guardar memoria] [Descartar]     │                          │
│                    [Borrar todo]  │                          │
├───────────────────────────────────┴──────────────────────────┤
│ HISTORIAL DE CAMBIOS (propio, solo lectura)                   │
│ versión · fecha · origen · cambio · tamaño                    │
└──────────────────────────────────────────────────────────────┘
```

### Componentes usados

`.panel`, `.field` + `.textarea` (+ `.is-invalid`), contador con `.quota-bar` reutilizada (estados warn/over), `.btn--primary` / `--ghost` / `--danger`, `.overlay`+`.modal` (confirmar guardado; borrar todo con escribir-para-confirmar §9.2b), `.field-error`, `.table` (historial), `.empty-state`, `.toast--ok`, nota informativa con ícono `info`, kicker.

### Datos que muestra (campos exactos)

**Editor:**
- `memoria.texto` — texto plano libre (sin markdown en v1)
- `memoria.tokens_estimados` / `limite_tokens` (1.000) — «≈ 412 / 1.000 tokens» (estimación ~4 caracteres/token, mostrada con `≈` honesto)
- `memoria.version` actual y `actualizada_el` («versión 7 · actualizada el 09/06/2026 18:21»)

**Panel «Qué sabe la plataforma de vos»:** lectura derivada del texto, agrupada en lenguaje claro (sin jerga): Rol y área · Clientes que atendés (solo nombres de prueba/ficticios — la política prohíbe PII real) · Módulos que dominás · Preferencias de formato. Si la memoria está vacía: «Nada todavía».

**Historial de cambios (propio):**
- `version` — `v7`, mono
- `fecha` — `dd/mm/aaaa HH:mm`
- `origen` ∈ «vos» · «propuesta del agente (aceptada por vos)» — el agente jamás escribe solo (ADR-0010 regla 2)
- `cambio` — resumen humano («+2 líneas: módulos ACT/FIN», «borraste todo»)
- `tamano` — `≈ 412 tok`

### Estados

- **Carga:** skeleton del editor (bloque) + 3 filas de historial.
- **Vacío:** empty-state en el editor: «Tu memoria está vacía. Lo que escribas acá, los agentes lo van a recordar al iniciar cada conversación nueva.» CTA «Escribí tu primera nota». Panel lateral: «Nada todavía». Historial: «Sin cambios registrados».
- **Error (validación al guardar):** la textarea pasa a `.is-invalid` + `.field-error` con **qué se detectó y por qué se rechaza**, p. ej.: «No se puede guardar: esto parece una contraseña (“clave=…”). La memoria no puede contener credenciales ni datos personales — se envía a un servicio de IA externo.» El texto del usuario **jamás se pierde** (§9.1). Variantes de regla: credencial/API key · dato personal (CI, teléfono, correo personal) · límite superado («te pasaste por ≈ 120 tokens — recortá antes de guardar», botón Guardar deshabilitado con motivo).
- **Éxito:** tras confirmar en el modal → toast `--ok` «Memoria guardada — versión 8. Se aplica desde tu próxima conversación.» El historial agrega la fila al instante.
- **Degradado:** si el validador remoto no responde, el guardado se bloquea (fail-closed: sin validación no hay escritura) con error-card «No pudimos validar tu memoria» + Reintentar. Decisión consciente: la validación es una función de seguridad (política §3.3), no un adorno.

### Interacciones y casos borde

- **Guardar = confirmación obligatoria** (modal): muestra resumen del cambio («+2 líneas, −1 línea · ≈ 412 → 446 tokens») y el aviso fijo: «**Se aplica desde tu próxima conversación.** Las conversaciones abiertas siguen usando la versión anterior de tu memoria.» Botones «Cancelar» / «Confirmar y guardar». Esc cancela.
- **Borrar todo:** botón danger separado (§6.2). Modal destructivo con escribir-para-confirmar: tipear `BORRAR`; el botón rojo se habilita solo con coincidencia exacta; Esc jamás confirma. El borrado queda en el historial y en Mi auditoría.
- **Contador en vivo:** al teclear, la barra y el número se actualizan; ≥90% pasa a warn; >100% a over y el guardado se deshabilita con el motivo al lado (§9.7: deshabilitar con motivo).
- **Navegación con cambios sin guardar:** aviso «Tenés cambios sin guardar» (confirm de salida).
- **Edición concurrente** (dos pestañas): al guardar, si la versión base ya no es la última → error-card «Tu memoria cambió en otra pestaña (versión 8). Revisá antes de pisar.» con «Ver diferencia» / «Recargar». Nunca merge silencioso.
- **Propuesta del agente pendiente** («¿guardo esto en tu memoria?» aceptada en el chat): aparece como una fila más del historial con origen «propuesta del agente (aceptada por vos)» — esta vista no gestiona la propuesta, solo la registra.
- El contenido de memoria se trata como **dato no confiable** (prompt injection): esta vista lo recuerda en el hint del editor («los agentes leen esto como información tuya, no como instrucciones»).

### Diferencias por rol

Ninguna. Misma vista, mismas capacidades para Admin/Técnico/Funcional (la memoria es personal). Único matiz: el hint de validación menciona «servicio de IA externo» en todos los roles — está redactado sin jerga, apto Funcional.

### Móvil

✅ Funcional completo: columnas apiladas (editor primero, «Qué sabe…» después), historial con scroll-x. Modales a ancho completo −16 px. Textarea con alto inicial mayor (10 líneas) para pulgar cómodo.

### Notas i18n

- Claves `espacio.memoria.*`. El aviso «se aplica desde tu próxima conversación» es una sola clave reutilizada en hint + modal + toast (consistencia terminológica).
- `BORRAR` como palabra de confirmación se traduce por glosario cerrado (pt-BR: `APAGAR`) — nunca hardcodear la comparación.
- Plural ICU en el resumen de diff («{n, plural, one {+# línea} other {+# líneas}}»).
- `≈` y «tok» no se traducen; «tokens» queda en minúscula tal cual en ambos idiomas.

---

## Vista 25 — Mi auditoría

### Propósito

Transparencia personal con simetría: la plataforma registra lo que hacés y vos podés verlo todo, solo lectura, con la garantía explícita de que **el registro es inmutable** (nadie lo edita, tampoco el Admin). Esto sostiene la confianza en HITL y en las liberaciones de cuota: cada firma que diste está acá, con fecha y contexto.

### Quién la ve (roles y capacidades)

Todos los roles, solo sobre **sus propios eventos**. Nadie ve eventos de otros desde esta vista (el audit log global consultable es de la consola Admin, UX-SPEC §9 — otra vista, otro módulo). Capacidad única: filtrar y leer. No hay exportación en v1 (el export CSV de auditoría es de Admin en consola).

### Layout (descripción + wireframe)

Una columna, máx. 1200 px: nota de inmutabilidad, fila de filtro, tabla paginada.

```
┌──────────────────────────────────────────────────────────────┐
│ MI ESPACIO — Mi auditoría        [tabs]                       │
│ 🔒 Este registro es inmutable: ni vos ni el Admin pueden      │
│    editarlo ni borrarlo.                                      │
├──────────────────────────────────────────────────────────────┤
│ Tipo: [Todos ▾]                            142 eventos        │
├──────────────────────────────────────────────────────────────┤
│ FECHA Y HORA      TIPO        DETALLE             CONTEXTO    │
│ 11/06/2026 14:02  APROBACIÓN  Aprobaste «…»       Comercial…  │
│ 11/06/2026 08:55  LOGIN       Inicio de sesión    Windows·…   │
│ …                                                             │
├──────────────────────────────────────────────────────────────┤
│ mostrando 1–10 de 142                    [‹ anterior][sig ›]  │
└──────────────────────────────────────────────────────────────┘
```

### Componentes usados

`.panel` (nota de inmutabilidad con ícono `lock`), `.select` (filtro de tipo), `.table` en `.panel--flush` con paginación clásica (§9.5: auditabilidad), `.tag` por tipo de evento, `.skeleton`, `.empty-state` (sin resultados de filtro), `.error-card`, `.kicker`.

### Datos que muestra (campos exactos)

Por evento:
- `fecha_hora` — `dd/mm/aaaa HH:mm`, mono, orden desc (los <24 h pueden mostrar relativo con absoluto en tooltip, §9.8)
- `tipo` — tag mono uppercase: `LOGIN` (neutral; intento fallido `--danger`) · `APROBACIÓN` (`--warn`; rechazo también `--warn` — es la misma familia HITL) · `MEMORIA` (`--info`) · `CUOTA` (`--accent`) · `ARCHIVO` (neutral) · `SEGURIDAD` (`--info`)
- `detalle` — frase humana completa y autosuficiente, p. ej.: «Aprobaste la escritura “Actualizar MV_CAMBIO” — riesgo medio» · «Editaste tu memoria (versión 6 → 7)» · «Solicitaste liberación de cuota diaria (USD 2,00) — concedida por el Admin» · «Subiste manual-activos.pdf (2,1 MB) a una conversación con DocAgent» · «Activaste la verificación en dos pasos (TOTP)» · «Intento de inicio de sesión fallido (contraseña incorrecta)»
- `contexto` — según tipo: LOGIN/SEGURIDAD → dispositivo + IP aproximada (`Windows · Chrome · 181.114.x.x`); APROBACIÓN → cliente final/ambiente (`Comercial Andina S.A. / TEST`); ARCHIVO → agente; MEMORIA/CUOTA → `—`

Catálogo de eventos registrados (mínimo v1): inicios de sesión (ok y fallidos), cierres de sesión remotos, aprobaciones/rechazos HITL dados, cambios de memoria (editar/borrar/aceptar propuesta), solicitudes de liberación y su resolución, archivos subidos, cambios de contraseña, TOTP activado/desactivado/códigos regenerados, aceptación del acuerdo de uso (primer login).

### Estados

- **Carga:** 5 filas skeleton con anchos variados; filtro deshabilitado mientras carga inicial.
- **Vacío (cuenta nueva):** empty-state: «Todavía no hay actividad registrada. Tus inicios de sesión, aprobaciones y cambios van a aparecer acá.» (sin CTA — no hay acción que crear actividad).
- **Vacío (filtro sin resultados):** «Sin eventos de tipo CUOTA en este período» + «Limpiar filtro».
- **Error:** error-card «No pudimos cargar tu registro» + por qué + «Reintentar».
- **Éxito / degradado:** no aplican acciones de escritura (vista 100% lectura). Si el origen de datos responde parcial (página incompleta), se muestra lo recibido + warn «registro parcialmente cargado — reintentá».

### Interacciones y casos borde

- **Filtro por tipo** (select): re-consulta y resetea a página 1; el total («142 eventos») refleja el filtro activo.
- **Paginación clásica** (no scroll infinito): «mostrando 1–10 de 142», anterior/siguiente; estado de página en la URL (compartible/recargable).
- **Sin acciones por fila**: nada navega, nada edita — refuerza la promesa de inmutabilidad. Única excepción: el evento APROBACIÓN enlaza a la tarjeta HITL resuelta (solo lectura) para ver payload y comentario.
- Caso borde — evento de un agente o cliente que ya no existe: el texto se conserva tal como se registró (el log es histórico, no se re-resuelven referencias).
- Caso borde — reloj del cliente distinto al del servidor: las horas son siempre del servidor con zona local del usuario indicada una vez en el pie («horas en GMT−4 · La Paz»).
- Volumen: usuarios HITL-intensivos pueden acumular miles de eventos — la paginación es server-side desde el día 1.

### Diferencias por rol

Ninguna en estructura ni capacidades. El Admin ve acá **solo sus propios eventos**, igual que cualquier usuario (su vista global vive en la consola). Diferencia de contenido natural: roles con HITL (Técnico/Admin) acumulan eventos APROBACIÓN; Funcional típicamente no los tiene.

### Móvil

✅ Lectura completa: tabla con scroll-x y sombra de affordance; en 380 px la columna CONTEXTO se funde dentro de DETALLE (segunda línea, `--ink-faint`) para evitar scroll excesivo. Filtro y paginación full-width, objetivos ≥44 px.

### Notas i18n

- Claves `espacio.auditoria.*`. Los **detalles de evento se generan por plantilla con placeholders nombrados** («{usuario} aprobó {accion}») — jamás concatenación; el texto registrado se renderiza desde datos estructurados, no strings congelados, para poder traducirse.
- Tags de tipo: se traducen como glosario cerrado (`APROBACIÓN` → pt-BR `APROVAÇÃO`); el valor canónico en datos es neutro (`approval`).
- Fechas/números por `Intl` con locale de instancia. La nota de zona horaria usa el nombre IANA de la instancia.
- Reservar +25%: «verificación en dos pasos» crece en pt-BR («verificação em duas etapas»).

---

## Vista 26 — Configuración personal

### Propósito

Concentrar las preferencias y la seguridad de la cuenta: idioma de interfaz (ES/PT-BR), tema (oscuro/claro/sistema — la única pieza de theming que es del usuario, design system §2.1), gestión de TOTP (activar con QR, regenerar códigos de respaldo, desactivar solo si el rol lo permite — para Admin es obligatorio), sesiones activas con cierre remoto, y cambio de contraseña.

### Quién la ve (roles y capacidades)

Todos los roles. Única divergencia: **Admin no puede desactivar TOTP** (obligatorio por política). Para Admin, la opción «Desactivar» **no se renderiza** — en su lugar una nota explica la obligatoriedad (§9.7: no es algo «temporalmente imposible», es algo que su rol no tiene; pero como el usuario podría buscarlo, la nota evita la sensación de bug). Funcional/Técnico pueden activar y desactivar TOTP libremente (recomendado activarlo; el producto lo sugiere sin forzar).

### Layout (descripción + wireframe)

Una columna de paneles apilados, máx. 760 px (formularios internos máx. 560 px §6.1); la tabla de sesiones puede extenderse al ancho del panel.

```
┌──────────────────────────────────────────────┐
│ MI ESPACIO — Configuración      [tabs]       │
├──────────────────────────────────────────────┤
│ PREFERENCIAS                                  │
│ Idioma  [Español (es-BO) ▾]                  │
│ Tema    (•) Oscuro ( ) Claro ( ) Sistema      │
│ [Guardar preferencias]                        │
├──────────────────────────────────────────────┤
│ VERIFICACIÓN EN DOS PASOS (TOTP)              │
│ ● ACTIVO desde 03/05/2026 · códigos: 7/10     │
│ [Regenerar códigos] [Desactivar TOTP]*        │
│  *no-Admin; Admin ve nota de obligatoriedad   │
├──────────────────────────────────────────────┤
│ SESIONES ACTIVAS                              │
│ dispositivo · inicio · última act. · acción   │
│ Windows·Chrome (ACTUAL)        —              │
│ Android·navegador        [Cerrar sesión]      │
│ [Cerrar todas las demás sesiones]             │
├──────────────────────────────────────────────┤
│ CONTRASEÑA                                    │
│ actual / nueva / repetir + requisitos         │
│ [Cambiar contraseña]                          │
└──────────────────────────────────────────────┘
```

### Componentes usados

`.panel`, `.field` + `.select` / `.input` (password), grupo de radios para tema (radios nativos estilizados, `fieldset`+`legend`), `.tag--money` (ACTIVO) / neutral (INACTIVO), `.btn--primary`/`--secondary`/`--danger`/`--ghost`, `.overlay`+`.modal` (códigos de respaldo; confirmación de desactivar TOTP; confirmación de cerrar todas), `.table` (sesiones activas), `.toast--ok`, `.error-card`, `.field-error`, QR placeholder SVG (composición local), `.kicker`.

### Datos que muestra (campos exactos)

**Preferencias:** `idioma` ∈ `es-BO` («Español (Bolivia)») · `pt-BR` («Português (Brasil)») — hint: «cambia la interfaz; los agentes responden en el idioma en que les escribas». `tema` ∈ oscuro · claro · sistema — hint: «el tema es tuyo; los colores de marca los define tu instancia».

**TOTP:**
- `estado` ∈ ACTIVO (tag `--money` + «desde dd/mm/aaaa») · INACTIVO (tag neutral + CTA «Activar»)
- `codigos_respaldo_restantes` — «Te quedan 7 de 10 códigos de respaldo»
- Flujo de activación: QR (otpauth URI) + clave manual mono (`RSLT AGNT K3PD 9XQ2 M84R TT01`) + campo «código de 6 dígitos» (input mono, `inputmode="numeric"`, autocomplete `one-time-code`) + botón «Verificar y activar»
- Códigos de respaldo (modal, post-activación o regeneración): 10 códigos mono (`4F7K-92QD` …), botones «Descargar .txt» / «Copiar» / «Listo», warn «se muestran una sola vez»

**Sesiones activas:** por sesión — `dispositivo` (SO + navegador, ícono `monitor`/`smartphone`), `inicio` (`dd/mm/aaaa HH:mm`), `ultima_actividad` (relativo <24 h), `ip_aproximada` + ciudad («181.114.x.x · Santa Cruz, BO»), `es_actual` (tag `--accent` ACTUAL, sin acción de cierre) — las demás con «Cerrar sesión».

**Contraseña:** `actual`, `nueva`, `repetir` + requisitos visibles siempre (mín. 12 caracteres · al menos 1 mayúscula, 1 minúscula y 1 número · distinta de las últimas 3). Nota fija: «Al cambiarla se cierran tus otras sesiones activas.»

### Estados

- **Carga:** skeletons por panel (la vista carga por zonas, §9.5).
- **Vacío:** no aplica (siempre hay preferencias y al menos la sesión actual). TOTP inactivo es el «vacío» de su panel: estado INACTIVO + CTA «Activar».
- **Error:** por panel, inline: contraseña actual incorrecta → `.is-invalid` + field-error en ese campo; código TOTP inválido → «Código incorrecto o vencido — los códigos duran 30 segundos»; cierre remoto fallido → toast `--danger` con reintento. El input del usuario nunca se pierde (§9.1).
- **Éxito:** toasts `--ok` por acción: «Preferencias guardadas» · «Verificación en dos pasos activada» · «Sesión de Android cerrada» · «Contraseña actualizada — cerramos tus otras sesiones». El cambio de tema aplica **al instante** (sin esperar guardado: feedback inmediato; persiste al guardar).
- **Degradado:** si el servicio de geolocalización de IP no responde, la columna muestra solo la IP («ubicación no disponible»). Si la lista de sesiones no carga, el resto de la vista sigue operable (paneles independientes).

### Interacciones y casos borde

- **Tema «Sistema»** sigue `prefers-color-scheme` y reacciona en vivo si el SO cambia.
- **Cambio de idioma:** aplica al guardar; recarga los catálogos de mensajes sin perder la ruta. Las conversaciones existentes no se «retraducen» (el contenido es del usuario y los agentes).
- **Activar TOTP:** secuencia escanear QR → ingresar código → ver códigos de respaldo (obligatorio pasar por el modal; «Listo» requiere scroll completo o confirmación de guardado). Si el usuario abandona a mitad, TOTP queda INACTIVO (la activación es atómica).
- **Regenerar códigos:** invalida TODOS los anteriores — el modal lo advierte antes («tus 7 códigos actuales dejan de servir») y muestra los 10 nuevos una sola vez. Queda en Mi auditoría.
- **Desactivar TOTP (no-Admin):** modal de confirmación que exige contraseña actual + un código TOTP vigente (anti-secuestro de sesión). Queda en auditoría.
- **Cerrar sesión remota:** efecto inmediato (revoca el token); la fila desaparece con fade. La sesión ACTUAL no ofrece cierre acá (para salir está el menú del avatar). «Cerrar todas las demás» pide confirmación simple e informa el total («vas a cerrar 2 sesiones»).
- **Cambio de contraseña:** al éxito revoca las demás sesiones (se informa antes y después). Validación inline al blur; revalidación al corregir; doble submit bloqueado.
- Caso borde — única sesión activa: «Cerrar todas las demás» no se renderiza.
- Caso borde — usuario sin TOTP que es promovido a Admin: en su próximo login el sistema fuerza la activación (flujo de login, fuera de esta vista); esta vista mostraría ACTIVO sin opción de desactivar.

### Diferencias por rol

| Elemento | Funcional | Técnico | Admin |
|---|---|---|---|
| Preferencias (idioma/tema) | ✅ | ✅ | ✅ |
| Activar TOTP / regenerar códigos | ✅ | ✅ | ✅ |
| Desactivar TOTP | ✅ | ✅ | ❌ no se renderiza; nota: «El TOTP es obligatorio para el rol Admin.» |
| Sesiones activas + cierre remoto | ✅ | ✅ | ✅ |
| Cambio de contraseña | ✅ | ✅ | ✅ |

### Móvil

✅ Funcional completo (cerrar sesiones remotas desde el celular es caso de uso real de seguridad). Paneles a una columna; tabla de sesiones → cards apiladas con botón full-width; QR centrado con clave manual debajo (copiable); modales a pantalla casi completa.

### Notas i18n

- Claves `espacio.config.*`. Los nombres de idioma se muestran **en su propio idioma** («Português (Brasil)») — no se traducen.
- Requisitos de contraseña como lista de claves separadas (cada requisito una clave, para checks individuales).
- «Verificación en dos pasos (TOTP)»: el término humano se traduce, la sigla `TOTP` no.
- Códigos de respaldo, claves manuales y nombres de dispositivo no se traducen ni localizan.
- Reservar +25% en botones largos («Cerrar todas las demás sesiones» → pt-BR «Encerrar todas as outras sessões»).

---

## Apéndice — Decisiones de diseño tomadas en este módulo

1. **Costo visible para Funcional solo en Mi consumo:** la cuota se define en USD (ADR-0007); ocultar la cifra dejaría la barra sin significado. La regla «cero costos» de Funcional sigue intacta en chat/catálogo.
2. **Telemetría de cache = capa exclusiva Admin** en esta vista (anillo + hit-rate), coherente con «Técnico NO ve telemetría»; Técnico conserva tokens (ya los ve en el chat).
3. **Memoria fail-closed:** sin validador disponible no se guarda — la validación anti-PII/credenciales es función de seguridad, no decoración.
4. **Auditoría sin acciones por fila** (salvo enlace a tarjeta HITL resuelta): refuerza la promesa de inmutabilidad.
5. **TOTP de Admin: opción de desactivar no renderizada + nota** — combinación de §9.7 (ocultar lo que el rol no tiene) con prevención de «sensación de bug».
