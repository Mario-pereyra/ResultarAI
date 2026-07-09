# 07 — Administración · Operación

> **Estado:** v1.0. Módulo solo-Admin de la consola de administración: operación diaria de la instancia.
> **Sistema de diseño:** [`../DESIGN-SYSTEM.md`](../DESIGN-SYSTEM.md) · tokens en [`../mockups/tokens.css`](../mockups/tokens.css).
> **Mockups de este módulo:**
> [`30-admin-dashboard.html`](../mockups/30-admin-dashboard.html) ·
> [`31-admin-usuarios.html`](../mockups/31-admin-usuarios.html) ·
> [`32-admin-grupos.html`](../mockups/32-admin-grupos.html) ·
> [`33-admin-cuotas.html`](../mockups/33-admin-cuotas.html) ·
> [`37-admin-audit.html`](../mockups/37-admin-audit.html) ·
> [`39-admin-salud.html`](../mockups/39-admin-salud.html)
> (la numeración salta porque 34-36 y 38 están reservados para builders y registro de prompts, especificados en otros módulos).

---

## 0. Convenciones del módulo (aplican a las 6 vistas)

1. **Solo Admin.** Ninguna de estas vistas existe para Técnico ni Funcional: no aparecen en la navegación, no se renderizan deshabilitadas (DESIGN-SYSTEM §9.7). Un deep-link de un rol sin permiso redirige al inicio del rol, sin toast ni mensaje que confirme la existencia de la ruta.
2. **Toda acción de administración escribe en el audit log** (alta/edición/desactivación de usuario, cambio de cuota, liberación, kill-switch, prueba de restore). El campo «nota de auditoría» de los formularios viaja en ese registro.
3. **Navegación:** sección «Consola admin» del sidebar (capa Admin). Orden: Tablero · Usuarios · Grupos · Cuotas · Registro de prompts (otro módulo) · Audit · Salud. Breadcrumb mono en cada vista: `Consola admin / <vista>`.
4. **Layout:** contenido a 1200 px máx. (tablas/admin, DESIGN-SYSTEM §6.1). Una vista = un h1 con kicker «Consola admin». Acciones primarias arriba a la derecha del encabezado.
5. **Formatos es-BO** (DESIGN-SYSTEM §9.8): `USD 1.284,50` agregados, `USD 0,0042` costos unitarios, `dd/mm/aaaa HH:mm`, `82%`, todo dato numérico en JetBrains Mono con `tabular-nums`.
6. **Datos siempre ficticios** en mockups y capturas: usuarios tipo `lucia`, clientes tipo «Comercial Andina S.A.», montos pequeños.
7. **TOTP obligatorio para Admin:** entrar a cualquier vista de consola exige sesión con TOTP verificado. Si un Admin aún no enroló TOTP, el shell lo fuerza a enrolar antes de mostrar la consola (flujo de login, fuera de este módulo).
8. **Paginación clásica** en todas las tablas admin (auditabilidad, DESIGN-SYSTEM §9.5); nunca scroll infinito.

---

## 1. Tablero de operación — `30-admin-dashboard.html`

### Propósito
Pantalla de aterrizaje de la consola: en un vistazo, ¿cuánto está costando la plataforma, el cache está protegiendo la economía (ADR-0001/0006), hay escalaciones anómalas, los servicios están vivos y los SLOs se cumplen? Es un tablero de **lectura + accesos directos**; no se edita nada acá.

### Quién la ve (roles y capacidades)
- **Admin:** todo. Es la home de la sección «Consola admin».
- **Técnico / Funcional:** no existe (convención 0.1).

### Layout
Grid de paneles a 1200 px. Desktop: fila de 4 KPI → fila de 2 paneles (costo por agente / top usuarios) → fila de 2 (top sesiones caras / columna salud+SLOs) → fila de accesos directos.

```
┌ kicker: CONSOLA ADMIN · h1: Tablero de operación · [rango: Hoy|7d] ┐
├──────────┬──────────┬──────────┬──────────┤
│ COSTO    │ COSTO    │ CACHE    │ ESCALAC. │   ← 4 KPI cards
│ HOY      │ SEMANA   │ HIT-RATE │ A PRO 7d │
├──────────┴──────────┼──────────┴──────────┤
│ Costo por agente    │ Top usuarios (7d)   │
│ (barras horiz.)     │ (tabla top 5)       │
├─────────────────────┼─────────────────────┤
│ Top sesiones caras  │ Salud resumida      │
│ (tabla)             │ SLOs (3 filas)      │
├─────────────────────┴─────────────────────┤
│ Accesos directos (chips-botón)            │
└───────────────────────────────────────────┘
```

### Componentes usados
`.panel`, `.kicker`, `.tag` (todas las variantes semánticas), `.table` + `.table-wrap`, `.live-dot` (+ `--warn`/`--danger`/`--off`), `.btn--ghost`/`--secondary`, `.skeleton`, `.error-card--warn` (degradado), mini-gráficos de barras hechos con divs y tokens (sin librerías), tooltips `[data-tip]`.

### Datos que muestra (campos exactos)
- **KPI Costo hoy:** monto USD del día (2 decimales) · delta vs ayer (`+12%` / `−8%`, con flecha) · tooltip «desde 00:00, hora de la instancia».
- **KPI Costo semana:** monto USD acumulado de la semana ISO · proyección de fin de mes (`proy. USD 96,40`) · % del presupuesto global mensual consumido.
- **KPI Hit-rate de cache global:** porcentaje 7 días · delta en puntos vs semana anterior · mini-gráfico de tendencia (7 barras, una por día, con valor en tooltip y tabla `sr-only` para lectores) · subtexto «ahorro estimado: USD n,nn esta semana».
- **KPI Escalaciones a Pro:** conteo 7 días · % de sesiones (`1,8% de sesiones`) · enlace «ver sesiones escaladas».
- **Costo por agente (7d):** por cada agente activo: nombre, barra proporcional, monto USD, % del total. Incluye fila «Workflows» separada (los workflows no son agentes del catálogo).
- **Top usuarios por costo (7d):** tabla 5 filas: `usuario` (mono) · `nombre` · `sesiones` · `costo USD` · `% del total`.
- **Top sesiones caras (7d):** tabla 5 filas: `sesión` (id mono corto) · `usuario` · `agente` · `modelo` (tag mono; tag `--warn` «modelo alterno» si hubo fallback) · `turnos` · `tokens` · `costo USD` · acción «Abrir» (traza en Langfuse).
- **Salud resumida:** por servicio: dot de estado + nombre + latencia + «hace n s». Servicios: Gateway LLM · PostgreSQL · Langfuse · Uptime Kuma · Bridges (agregado `2/3 conectados`). Enlace «Ver salud completa →» (vista 39).
- **SLOs (30 días):** 3 filas: `disponibilidad` (valor vs objetivo 99,5%) · `latencia p95` (valor vs ≤ 4,0 s) · `tasa de error` (valor vs ≤ 2,0%). Cada una con tag de estado: `OK` (`--money`) / `EN RIESGO` (`--warn`, a <10% del límite) / `INCUMPLIDO` (`--danger`).
- **Accesos directos:** botones-chip a Usuarios, Grupos, Cuotas (con contador de solicitudes pendientes), Audit, Salud, Registro de prompts, Langfuse (externo), Uptime Kuma (externo).

### Estados
- **Carga:** skeleton por zona (KPI = 4 cards con barras shimmer; tablas = 4 filas skeleton). Nunca pantalla en blanco; el shell y los títulos llegan primero (§9.5).
- **Vacío:** instancia recién instalada → KPIs en `USD 0,00` / `—` y empty-state en tablas («Todavía no hay sesiones esta semana»). No es error.
- **Error:** si la API de telemetría falla: error-card por zona («No se pudo cargar el costo por agente» + Reintentar); las zonas sanas siguen visibles.
- **Éxito:** datos en vivo; refresco automático cada 60 s sin parpadeo (transición suave de números).
- **Degradado:** Langfuse no responde → los montos llevan prefijo `~` y un error-card `--warn` global: «Telemetría diferida — los costos son estimados desde el gateway» (DESIGN-SYSTEM §8.12). El resto del tablero sigue operativo.

### Interacciones y casos borde
- Selector de rango `Hoy | 7 días` arriba a la derecha (afecta KPIs de costo y tablas; los SLOs son siempre 30 d y el hit-rate siempre 7 d — se etiqueta en cada panel para no mentir).
- Click en fila de «Top sesiones caras» → abre el detalle de la sesión (transcript + traza). La fila entera no es clickable: la acción es el enlace «Abrir» (§8.4).
- Click en un agente del panel de costo → filtra el tablero por ese agente (chips de filtro activo con cierre).
- Contador de solicitudes de liberación en el acceso directo a Cuotas (badge rojo) — es la vía rápida al trabajo pendiente.
- Caso borde: división por cero en deltas (ayer = USD 0,00) → mostrar `—` en vez de `+∞%`.
- Caso borde: un solo día de datos → el mini-gráfico muestra 1 barra y el delta queda `—`.
- Los montos del tablero **no** son facturación: tooltip en el título «costo de proveedor LLM estimado por el gateway; fuente: Langfuse».

### Diferencias por rol
Vista exclusiva de Admin. No hay versión reducida para otros roles: el Técnico tiene la ficha técnica por agente (otro módulo) y jamás telemetría agregada de usuarios (decisión de privacidad: ver consumo nominal de colegas es capacidad solo-Admin).

### Móvil
Lectura básica (DESIGN-SYSTEM §11): KPIs apilados en 1 columna, tablas con scroll-x, mini-gráfico intacto. Sin edición posible, así que no se degrada ninguna acción. Los accesos directos envuelven en 2 columnas.

### Notas i18n
- Claves de mensaje para todos los labels («Costo hoy», «hit-rate» se mantiene como término técnico en ES y PT-BR — glosario cerrado §12).
- Deltas con placeholders nombrados: `{delta} vs ayer` (las traducciones reordenan).
- Montos y fechas por `Intl` con locale de instancia; los nombres de modelo (`deepseek-v4-flash`) y códigos no se traducen.
- Reservar +25% de ancho en tags de estado de SLO (`EN RIESGO` → PT-BR `EM RISCO` cabe, pero «INCUMPLIDO» → `DESCUMPRIDO` es más largo).

---

## 2. Gestión de usuarios — `31-admin-usuarios.html`

### Propósito
Alta, edición y baja (desactivación) de cuentas. **No existe auto-registro** (decisión cerrada): toda cuenta nace acá, creada por un Admin, con contraseña temporal generada por el sistema. También se administra el requisito TOTP y el reset de credenciales.

### Quién la ve (roles y capacidades)
- **Admin:** CRUD completo de usuarios, con dos límites: no puede desactivarse a sí mismo, y no puede quitarse a sí mismo el rol Admin si es el último Admin activo de la instancia.
- **Técnico / Funcional:** no existe.

### Layout
```
┌ kicker · h1: Usuarios · [—————buscar————] [rol ▾] [estado ▾] [+ Crear usuario] ┐
├────────────────────────────────────────────────────────────────┤
│ USERNAME  NOMBRE       ROL        ESTADO   TOTP   ÚLT. ACCESO  ACCIONES │
│ lucia     Lucía F…     FUNCIONAL  ACTIVO   SÍ     hace 2 h     [Rol][Credenciales][Desactivar] │
│ …                                                              │
├────────────────────────────────────────────────────────────────┤
│ paginación « 1 2 3 »                       n usuarios · n activos │
└────────────────────────────────────────────────────────────────┘
Modals: Crear usuario · Editar rol · Desactivar (escribir-para-confirmar) · Reset de credenciales
```

### Componentes usados
`.table` + `.table-wrap`, `.badge-rol` (las 3 variantes), `.tag` (estado, TOTP), `.btn` (`--primary` solo «Crear usuario»; acciones de fila en `--ghost --sm`), `.input` + `.select` (filtros), `.overlay` + `.modal` (4 modals), `.field` completo, `.input--mono` (username, contraseña temporal), `.check-row`, `.toast--ok`, `.empty-state`, `.skeleton`, `.error-card`.

### Datos que muestra (campos exactos)
Tabla (orden por defecto: último acceso desc):
- `username` — mono, único, inmutable tras la creación.
- `nombre` — nombre y apellido para mostrar.
- `rol` — badge `ADMIN` / `TÉCNICO` / `FUNCIONAL`.
- `estado` — tag `ACTIVO` (`--money`) / `DESACTIVADO` (neutral; fila atenuada).
- `TOTP` — tag `SÍ` (`--money`) / `NO` (neutral) / `PENDIENTE` (`--warn`: requerido pero aún no enrolado — caso típico: Admin recién creado).
- `último acceso` — relativo (<24 h) con absoluto en tooltip; `nunca` si jamás inició sesión.
- `acciones` — Editar rol · Credenciales · Desactivar (o Reactivar).

Modal **Crear usuario**: `username` (mono, validación: minúsculas, sin espacios, único) · `nombre` · `rol` (select con descripción de cada rol en hint) · `contraseña temporal` (solo lectura, generada por el sistema, botones Copiar y Regenerar; nota «se muestra una sola vez») · checkbox `requerir TOTP en el primer acceso` (marcado y bloqueado si rol = Admin, con hint «obligatorio para Admin»).

Modal **Editar rol**: rol actual → rol nuevo + consecuencia en texto («Jorge pasa de Técnico a Admin: gana consola, telemetría y builders; se le exigirá TOTP») + nota de auditoría opcional.

Modal **Desactivar** (destructivo crítico, §9.2b): consecuencias listadas (no podrá iniciar sesión · **todas sus sesiones activas se revocan al confirmar** · su historial y su consumo se conservan para auditoría) + campo escribir-para-confirmar con el `username` exacto + botón danger deshabilitado hasta coincidencia.

Modal **Reset de credenciales**: regenera contraseña temporal (visible una vez + Copiar) · checkbox «invalidar TOTP enrolado» (para teléfono perdido) · consecuencia: revoca sesiones activas.

### Estados
- **Carga:** 5 filas skeleton dentro del wrapper de tabla.
- **Vacío:** solo posible por filtros («Sin resultados para “…”» + «Limpiar filtros»). Una instancia siempre tiene ≥1 Admin, así que el vacío absoluto no existe.
- **Error:** error-card en lugar del cuerpo de tabla («No se pudo cargar la lista» + Reintentar). Error de submit en modal: error-card sobre el pie, input intacto (§9.1).
- **Éxito:** toast `--ok` («Usuario creado», «Rol actualizado», «Usuario desactivado — sesiones revocadas»). La fila nueva/afectada se resalta 2 s con `--accent-soft`.
- **Degradado:** n/a (no depende de telemetría).

### Interacciones y casos borde
- Buscar filtra por username y nombre (debounce 300 ms); selects de rol y estado se combinan.
- **La contraseña temporal se muestra una sola vez**; al cerrar el modal no es recuperable (solo reset). El botón Copiar confirma con toast.
- Desactivar revoca sesiones **en el momento** (el usuario activo ve un error de sesión expirada en su próximo request).
- Reactivar restituye el acceso pero fuerza cambio de contraseña (se genera temporal nueva en el mismo flujo).
- Caso borde: el Admin intenta desactivarse a sí mismo → la acción no aparece en su propia fila (ocultar, no deshabilitar).
- Caso borde: degradar al último Admin activo → el submit falla con motivo claro («La instancia necesita al menos un Admin activo»).
- Caso borde: username duplicado → validación inline al blur, sin esperar al submit.
- Edición concurrente: si otro Admin modificó al usuario, el submit devuelve conflicto y la UI ofrece recargar los datos (sin pisar).
- Toda acción queda en el audit log con actor, antes/después y nota.

### Diferencias por rol
Solo Admin. Detalle interno: las acciones sobre la **propia cuenta** del Admin logueado se reducen (sin desactivar, sin auto-degradación si es el último Admin) — mismo principio de ocultar lo imposible.

### Móvil
Lectura y acciones puntuales: tabla con scroll-x; los modals toman ancho completo (−16 px). Crear usuario es posible pero está pensado para desktop; nada se bloquea.

### Notas i18n
- Roles: el badge muestra el nombre traducido del rol, pero la clave interna (`admin`/`tecnico`/`funcional`) es invariante.
- «Escribí el username para confirmar» usa placeholder nombrado: `Escribí {username} para confirmar`.
- Reservar ancho extra en encabezados de tabla (PT-BR «ÚLTIMO ACESSO»). El username jamás se traduce ni transforma.

---

## 3. Grupos y equipos — `32-admin-grupos.html`

### Propósito
Organizar usuarios en grupos/equipos con **cuota de grupo** (nivel intermedio de la cascada global→grupo→usuario→sesión, ADR-0007) y ver el consumo agregado por grupo. Los grupos son la unidad natural de presupuesto por equipo o por proyecto.

### Quién la ve (roles y capacidades)
- **Admin:** crear/editar grupos, asignar/quitar usuarios, fijar cuota de grupo, ver consumo.
- **Técnico / Funcional:** no existe (un usuario ve su propia cuota efectiva en su perfil, fuera de este módulo).

### Layout
Patrón maestro-detalle: lista de grupos a la izquierda (cards compactas), detalle del grupo seleccionado a la derecha.

```
┌ kicker · h1: Grupos · [+ Crear grupo] ┐
├───────────────┬───────────────────────────────┤
│ ▸ Consultoría │ Consultoría funcional         │
│   funcional   │ 12 miembros · creado 02/2026  │
│   12 mi · 54% │ [Editar] [Asignar usuarios]   │
│ ▸ Técnico     │ ── cuota del grupo ──         │
│   AdvPL       │ USD 64,20 / 120,00  [██░] 54% │
│   8 mi · 89%⚠ │ ── miembros ──                │
│ ▸ Proyecto    │ tabla: usuario · rol · consumo│
│   C. Andina   │        del mes · [Quitar]     │
│   6 mi · 100%✕│ ── consumo (30 d) ──          │
│               │ barras por agente             │
└───────────────┴───────────────────────────────┘
```

### Componentes usados
`.panel` (cards de grupo; seleccionada con borde `--accent`), `.quota-row` + `.quota-bar` (sana/`is-warn`/`is-over`), `.table`, `.badge-rol`, `.btn`, `.overlay` + `.modal` (crear/editar, asignar), `.select` (asignar usuario), `.chip` (miembros a asignar), `.empty-state`, `.skeleton`, `.toast`.

### Datos que muestra (campos exactos)
Card de grupo (lista): `nombre` · `slug` (mono) · `n miembros` · mini quota-bar con `% usado` de la cuota mensual.
Detalle:
- Encabezado: `nombre`, `descripción`, `slug`, `creado el`, acciones Editar / Asignar usuarios / Eliminar grupo (si está vacío).
- **Cuota del grupo:** `usado / límite mensual USD` + barra + `umbral de aviso` (%) + origen («override» o «default de grupo» — la edición fina vive en la vista Cuotas, acá hay enlace cruzado «Editar en Cuotas →»).
- **Miembros:** tabla: `username` · `nombre` · `rol` (badge) · `consumo del mes USD` · `% de la cuota de grupo` · acción Quitar. Un usuario puede estar en varios grupos; se indica con tag `+2 grupos` en tooltip.
- **Consumo por grupo (30 d):** barras por agente dentro del grupo + total.
Modal **Crear/editar grupo**: `nombre` · `slug` (auto, editable solo al crear) · `descripción` · `cuota mensual USD` (hint: «si queda vacía, hereda el default de grupo: USD 100,00») · `umbral de aviso %` (default 80).
Modal **Asignar usuarios:** buscador + lista con checkboxes de usuarios activos no-miembros; los seleccionados aparecen como chips; resumen «vas a agregar 3 usuarios».

### Estados
- **Carga:** lista = 3 cards skeleton; detalle = skeleton de título + barra + tabla.
- **Vacío:** sin grupos → empty-state con CTA «Crear el primer grupo» («Los grupos permiten presupuestar por equipo. Sin grupo, los usuarios solo tienen la cuota global y la individual.»).
- **Error:** error-card por zona + Reintentar.
- **Éxito:** toasts («Grupo creado», «3 usuarios asignados», «lucia quitada del grupo»).
- **Degradado:** si la telemetría está diferida, las columnas de consumo muestran `~` con tooltip (la membresía y cuotas siguen editables).

### Interacciones y casos borde
- Seleccionar card → carga el detalle (URL con slug: deep-linkeable).
- Quitar miembro pide confirmación simple (§9.2a) con consecuencia: «El consumo histórico del grupo no cambia; lucia conserva su cuota individual».
- Eliminar grupo: solo habilitado si no tiene miembros (de lo contrario la acción explica el porqué en tooltip — es un disabled legítimo §9.7); pide escribir-para-confirmar el slug.
- Caso borde: usuario en varios grupos → su consumo cuenta en cada grupo donde generó el gasto (el gasto se atribuye al grupo activo de la sesión; tooltip lo aclara).
- Caso borde: bajar la cuota por debajo del consumo ya hecho del mes → permitido con advertencia explícita («el grupo queda bloqueado hasta el próximo ciclo o hasta una liberación»).
- Cambios de cuota acá son atajos de la vista Cuotas: misma validación, misma nota de auditoría obligatoria.

### Diferencias por rol
Solo Admin. (El consumo nominal por miembro es dato sensible: jamás visible para Técnico.)

### Móvil
Lectura básica: lista y detalle se apilan (lista → tap → detalle a pantalla completa con volver). Edición posible pero recomendada en desktop.

### Notas i18n
- `slug` invariante (mono, sin traducción).
- Plurales ICU en «{n, plural, one {# miembro} other {# miembros}}».
- Descripciones de grupo son contenido del cliente, no se traducen.

---

## 4. Cuotas y liberaciones — `33-admin-cuotas.html`

### Propósito
Centro de control de la economía por consumo (ADR-0007/0010): cuotas por alcance (global → grupo → usuario → sesión) con defaults y overrides, umbral de aviso configurable, y el flujo completo de **solicitudes de liberación** (el botón «Solicitar liberación» que ve un usuario bloqueado al 100% desemboca acá).

### Quién la ve (roles y capacidades)
- **Admin:** editar cualquier cuota (con nota de auditoría obligatoria), aprobar/denegar liberaciones, ver historial.
- **Técnico / Funcional:** no existe. (Ellos ven su propia barra de cuota y el botón de solicitar liberación en su experiencia de chat.)

### Layout
Tres tabs: **Cuotas** · **Solicitudes (n)** · **Historial**.

```
┌ kicker · h1: Cuotas · tabs [ Cuotas | Solicitudes (2) | Historial ] ┐
│ TAB CUOTAS                                                  │
│ ALCANCE  ENTIDAD        LÍMITE/MES   ORIGEN    AVISO  USO ACTUAL    │
│ GLOBAL   — (instancia)  USD 600,00   default   80%    [███░] 69%  [Editar] │
│ GRUPO    — (default)    USD 100,00   default   80%    —           [Editar] │
│ GRUPO    tecnico-advpl  USD 160,00   override  80%    [███▉] 89%⚠ [Editar] │
│ USUARIO  — (default)    USD 25,00    default   80%    —           [Editar] │
│ USUARIO  jmendez        USD 40,00    override  90%    [██░ ] 62%  [Editar] │
│ SESIÓN   — (default)    USD 2,00     default   —      —           [Editar] │
├─────────────────────────────────────────────────────────────┤
│ TAB SOLICITUDES: cards (usuario · motivo · consumo · hace n min)    │
│   [Denegar…]  [Aprobar…]                                            │
│ TAB HISTORIAL: tabla de liberaciones resueltas                      │
└─────────────────────────────────────────────────────────────┘
```

### Componentes usados
`.tabs` (+ contador como `.tag--danger`), `.table`, `.tag` (`GLOBAL`/`GRUPO`/`USUARIO`/`SESIÓN` neutrales; `OVERRIDE` `--info`; `DEFAULT` `--outline`), `.quota-row` + `.quota-bar`, `.overlay` + `.modal` (editar cuota / aprobar / denegar), `.field` con `.is-invalid` (validación demostrada), `.textarea` (nota de auditoría, motivo), `.panel` (cards de solicitud), `.empty-state`, `.toast`, `.error-card`.

### Datos que muestra (campos exactos)
**Tab Cuotas** — tabla:
- `alcance` — tag mono `GLOBAL` / `GRUPO` / `USUARIO` / `SESIÓN`.
- `entidad` — `— (instancia)` para global, `— (default)` para defaults de alcance, o el slug/username concreto del override.
- `límite mensual` — USD (en SESIÓN el límite es por sesión, no mensual; la celda lo etiqueta `por sesión`).
- `origen` — tag `DEFAULT` / `OVERRIDE` (override muestra tooltip: quién lo creó y cuándo).
- `umbral de aviso` — % (default 80; editable por fila; `—` en sesión: la sesión no avisa, corta).
- `uso actual` — quota-bar + `usado / límite` (solo filas con entidad concreta o global; los defaults muestran `—`).
- acción `Editar`.

Modal **Editar cuota**: `límite` (number USD; validación: > 0; si < uso actual → warning bloqueante-consciente: requiere checkbox «entiendo que la entidad queda bloqueada») · `umbral de aviso %` (50–95) · `nota de auditoría` (**obligatoria**, textarea, mín. 10 caracteres) · resumen del cambio («USD 25,00 → USD 40,00 para jmendez»). Para un default: aviso del alcance del cambio («afecta a todos los usuarios sin override: 27 usuarios»).

**Tab Solicitudes** — card por solicitud pendiente:
- `usuario` (username + nombre) · `grupo` · `alcance bloqueado` (usuario o grupo) · `consumo actual` (barra al 100%, `USD 25,00 / 25,00`) · `motivo` (texto del usuario, citado) · `hace n min` + fecha absoluta.
- Acciones: **Aprobar…** (modal: `monto adicional USD` requerido con sugerencias rápidas +5/+10/+25, `válido hasta fin de mes` fijo en v1, nota opcional) · **Denegar…** (modal: `comentario` **obligatorio** — el usuario lo ve en su notificación).

**Tab Historial** — tabla: `fecha-hora` · `usuario` · `alcance` · `monto adicional` (o `DENEGADA` tag `--danger`) · `resuelta por` · `motivo del usuario` (truncado, tooltip) · `comentario del admin`.

### Estados
- **Carga:** tabla/cards skeleton por tab.
- **Vacío:** Solicitudes sin pendientes → empty-state «Estás al día. Cuando alguien llegue al 100% de su cuota y pida liberación, aparece acá.» Historial vacío → «Todavía no hubo liberaciones».
- **Error:** error-card + Reintentar por tab; error de submit en modal según §9.1.
- **Éxito:** toast («Cuota actualizada», «Liberación aprobada: +USD 10,00 para cquiroga», «Solicitud denegada») y la solicitud se mueve al Historial.
- **Degradado:** telemetría diferida → columnas de uso con `~`; editar cuotas sigue disponible (la cuota se evalúa en el gateway, no en Langfuse).

### Interacciones y casos borde
- El contador del tab Solicitudes es en vivo (badge rojo); la campana de notificaciones también recibe estas solicitudes.
- Aprobar una liberación **desbloquea al usuario al instante** (próximo mensaje pasa el check de cuota ANTES de llamar al LLM, regla dura de CLAUDE.md).
- Caso borde: dos Admin resuelven la misma solicitud → el segundo recibe conflicto («ya resuelta por mterceros hace 1 min») y la card se actualiza a resuelta.
- Caso borde: el usuario sigue consumiendo y agota también la liberación → puede volver a solicitar; la card nueva referencia la liberación anterior («2.ª solicitud del mes»).
- Caso borde: editar el default global por debajo de la suma de overrides → permitido (la cascada evalúa cada nivel por separado) pero el resumen lo advierte.
- El umbral de aviso dispara la notificación del usuario al cruzarlo (80% default); cambiarlo no re-notifica retroactivamente.
- Todo cambio de cuota y toda resolución de liberación → audit log (con nota).

### Diferencias por rol
Solo Admin. El lado del usuario (barra, aviso 80%, bloqueo 100%, botón «Solicitar liberación») está especificado en el módulo de chat; esta vista es el otro extremo del mismo flujo.

### Móvil
Tab Solicitudes es primera clase en móvil (aprobar una liberación desde el celular es caso real, como HITL): cards apiladas, botones full-width. Tabs Cuotas/Historial: lectura con scroll-x.

### Notas i18n
- `GLOBAL/GRUPO/USUARIO/SESIÓN` se traducen (son UI), pero las claves de alcance son invariantes.
- Mensajes con montos: placeholders nombrados (`Liberación aprobada: +{monto} para {usuario}`).
- El motivo del usuario y el comentario del admin son contenido, no se traducen.

---

## 5. Audit log global — `37-admin-audit.html`

### Propósito
Registro **append-only e inmutable** de toda acción auditable de la instancia: administración (usuarios, cuotas, prompts), seguridad (logins fallidos, TOTP), operación (HITL aprobadas/rechazadas, kill-switch, restores). Es la fuente de verdad forense; por eso no se edita, no se borra, y se exporta.

### Quién la ve (roles y capacidades)
- **Admin:** consulta, filtra, expande payloads, exporta CSV. **Nadie** edita ni borra — ni el Admin (el badge lo declara).
- **Técnico / Funcional:** no existe.

### Layout
```
┌ kicker · h1: Audit log · [🔒 APPEND-ONLY — INMUTABLE] · [Exportar CSV…] ┐
│ [actor ▾] [acción ▾] [entidad———] [desde 📅] [hasta 📅] [cliente/amb ▾] [Aplicar] [Limpiar] │
├────────────────────────────────────────────────────────────┤
│ FECHA-HORA       ACTOR      ACCIÓN              ENTIDAD        CLIENTE/AMB   ▾ │
│ 11/06 14:32:08   mterceros  QUOTA_RELEASE_APPR  usuario:cquir… —             ▸ │
│ ├─ payload JSON expandido (pre mono, copiable) ──────────────┤ │
│ 11/06 14:28:51   lucia      HITL_APPROVED       escritura:wr_… C.Andina/TEST ▸ │
│ …                                                            │
├────────────────────────────────────────────────────────────┤
│ « 1 2 3 … 42 »   ·   50 por página ▾   ·   2.084 registros  │
└────────────────────────────────────────────────────────────┘
```

### Componentes usados
`.table--dense` + `.table-wrap`, `.tag` (acción, mono; `--outline` con candado para el badge append-only), filtros con `.select`/`.input`/inputs `type="date"`, `.btn--secondary` (Exportar CSV con modal de rango), fila expandible (botón chevron con `aria-expanded` + fila de detalle), `pre` mono para payload (estilo `.hitl-card__payload`), paginación clásica (botones `.btn--ghost --sm`), `.empty-state`, `.skeleton`, `.error-card`, `.toast`.

### Datos que muestra (campos exactos)
Tabla (orden fijo: fecha-hora desc; el orden no es configurable — lectura forense):
- `fecha-hora` — `dd/mm/aaaa HH:mm:ss` mono (segundos incluidos: en auditoría importan).
- `actor` — username mono, o `sistema` (jobs, activaciones automáticas), o `anónimo` (login fallido pre-autenticación, con IP).
- `acción` — código mono invariante del catálogo: `USER_CREATED` · `USER_ROLE_CHANGED` · `USER_DEACTIVATED` · `CREDENTIALS_RESET` · `LOGIN_OK` · `LOGIN_FAILED` · `TOTP_ENROLLED` · `QUOTA_UPDATED` · `QUOTA_RELEASE_REQUESTED/_APPROVED/_DENIED` · `HITL_APPROVED/_REJECTED/_EXPIRED` · `PROMPT_ACTIVATED/_ROLLBACK` · `KILL_SWITCH_ON/_OFF` · `BACKUP_RESTORE_DRILL` · `GROUP_CREATED/_UPDATED` · `AGREEMENT_ACCEPTED` (checkbox de acuerdo de uso del primer login).
- `entidad` — tipo:id (`usuario:cquiroga`, `cuota:grupo/tecnico-advpl`, `prompt:docagent@13`, `escritura:wr_8f31`).
- `cliente/ambiente` — solo en eventos con contexto Protheus (HITL): `Comercial Andina S.A. / TEST`; `—` en el resto.
- `IP` — en la fila expandida (no como columna: ruido).
- **Fila expandida:** payload JSON formateado (mono, scroll-x, botón Copiar): incluye `before/after` en updates, `note` de auditoría, `user_agent`, `ip`, firmas en HITL de segunda aprobación.

Filtros: `actor` (select con buscador) · `acción` (select por catálogo, agrupado por categoría) · `entidad` (texto libre, matchea tipo:id) · `desde`/`hasta` (date) · `cliente/ambiente` (select, solo entidades con contexto).

**Exportar CSV:** modal con rango de fechas (pre-cargado con el filtro activo), aviso de volumen («≈ 2.084 registros — el export respeta los filtros activos») y nota: el CSV incluye el payload serializado. El export queda registrado en el propio audit (`AUDIT_EXPORTED`).

### Estados
- **Carga:** 8 filas skeleton densas.
- **Vacío:** solo por filtros («Ningún registro coincide con los filtros» + Limpiar). El log nunca está vacío en una instancia operativa (la propia creación de usuarios deja eventos).
- **Error:** error-card + Reintentar.
- **Éxito (export):** toast `--ok` «CSV generado — 2.084 registros» con enlace de descarga; export grande (>50k) corre en segundo plano y notifica por campana.
- **Degradado:** n/a — el audit se escribe en Postgres `app`, no depende de telemetría. Si el audit no puede escribirse, **la acción origen falla** (regla de integridad, documentada para el equipo de backend).

### Interacciones y casos borde
- Expandir fila: chevron al final, `aria-expanded`, la fila de payload es parte del flujo del documento (accesible). Una sola expandida a la vez no es regla: pueden abrirse varias.
- Paginación clásica con tamaño de página (25/50/100). El total siempre visible.
- Caso borde: payload muy grande (HITL con payload de escritura largo) → el JSON se muestra completo con scroll, jamás truncado silenciosamente (es auditoría); el CSV lo incluye entero.
- Caso borde: reloj — todos los timestamps en hora de la instancia con offset declarado en el pie («hora de la instancia: UTC−4»).
- Caso borde: rango de export > 12 meses → advertencia de tamaño + ejecución en segundo plano.
- Los registros de `LOGIN_FAILED` consecutivos del mismo origen se muestran individualmente (sin agrupar: forense).
- No hay acción de borrado ni edición en ninguna parte de la vista; el badge «APPEND-ONLY — INMUTABLE» es informativo y permanente.

### Diferencias por rol
Solo Admin. No existe un «audit reducido» para Técnico (decisión: el audit expone actividad nominal de todos los usuarios).

### Móvil
Lectura básica: filtros colapsan a un panel «Filtros (n)» plegable; tabla con scroll-x; el payload expandido ocupa el ancho completo. Export disponible.

### Notas i18n
- Los **códigos de acción no se traducen** (mono, invariantes); el select de filtro muestra código + descripción traducida («HITL_APPROVED — aprobación de escritura»).
- Encabezado CSV en claves invariantes (inglés técnico) para que el archivo sea estable entre locales.
- Fechas del export en ISO 8601 (no localizadas) — el archivo es para máquinas y planillas.

---

## 6. Salud del sistema — `39-admin-salud.html`

### Propósito
Estado operativo de la instancia: servicios (gateway, base de datos, observabilidad, bridges por dispositivo), backups con prueba de restore, jobs de retención, enlaces a Langfuse/Uptime Kuma, y el **kill-switch global** de la plataforma. Es la vista de guardia: la que se abre cuando «algo anda mal».

### Quién la ve (roles y capacidades)
- **Admin:** todo, incluido accionar el kill-switch y disparar la prueba de restore.
- **Técnico / Funcional:** no existe. (Los estados degradados que les afectan llegan como ErrorCards en su propia experiencia: `VPN_OFFLINE`, `GATEWAY_OFFLINE`…)

### Layout
```
┌ kicker · h1: Salud del sistema · [Langfuse ↗] [Uptime Kuma ↗] ┐
├──────────────────────────────┬──────────────────────────────┤
│ SERVICIOS                    │ BACKUPS                       │
│ ● Gateway LLM   38 ms  30 s  │ último OK: 11/06 03:15 1,8 GB │
│ ● PostgreSQL     4 ms  30 s  │ destino: NAS + S3 offsite     │
│ ◐ Langfuse    1.240 ms 30 s  │ último fallo: 02/06 (timeout) │
│ ● Uptime Kuma   12 ms  30 s  │ [Probar restore]              │
│ BRIDGES (por dispositivo)    │ último drill: OK 28/05 4m12s  │
│ ● SRV-INBOLSA    9 ms        ├──────────────────────────────┤
│ ● LAPTOP-LUCIA  21 ms        │ JOBS DE RETENCIÓN             │
│ ○ LAPTOP-JMEND  desc. 2 h    │ trazas 90d · último run OK    │
│                              │ mensajes 365d · último run OK │
├──────────────────────────────┴──────────────────────────────┤
│ ⚠ KILL-SWITCH — zona peligrosa (panel separado, borde danger)│
│ estado: CHAT ACTIVO · [Apagar el chat de la plataforma…]     │
└──────────────────────────────────────────────────────────────┘
```

### Componentes usados
`.live-dot` (+ variantes), `.panel` (+ panel danger local para el kill-switch, tokens `--danger`), `.table` (bridges, jobs), `.tag`, `.btn--secondary` (Probar restore), `.btn--danger` (kill-switch), `.overlay` + `.modal` destructiva con **escribir-para-confirmar** (§9.2b), banner de plataforma apagada (variante del `.ai-banner` con tokens danger), enlaces externos con ícono, `.error-card--warn` (degradado), `.skeleton`, `.toast`.

### Datos que muestra (campos exactos)
**Servicios** — por fila: `estado` (dot: OK verde / degradado ámbar / caído rojo / apagado gris) · `servicio` (Gateway LLM · PostgreSQL (app/langfuse/rag como sub-detalle) · Langfuse · Uptime Kuma) · `latencia` (ms, mono) · `último check` (`hace 30 s`) · `detalle` (texto corto del estado: «ingesta diferida», «—»).
**Bridges conectados (por dispositivo):** tabla: `dispositivo` (hostname mono) · `usuario` (dueño del bridge) · `versión` (`tat-mcp v0.4.2`) · `estado` (CONECTADO/DESCONECTADO) · `latencia` · `desde / visto por última vez`. Los bridges entran por WSS a `apps/platform` (`tat-mcp --connect`).
**Backups:** `último backup` (fecha-hora, resultado OK/FALLO, `tamaño`, `duración`) · `destino` (local + offsite con nombre del bucket) · `último fallo` (fecha + causa corta, `—` si no hubo en 90 d) · botón **Probar restore** · `último drill`: resultado (OK/FALLO), fecha, duración, alcance («restauró app+langfuse+rag en sandbox»).
**Jobs de retención:** por job: `job` (trazas Langfuse · mensajes de sesión) · `política` (`90 días` / `365 días`) · `último run` (fecha-hora + OK/FALLO) · `purgado` (`12.430 trazas`).
**Enlaces:** Langfuse (observabilidad completa) · Uptime Kuma (historial de uptime) — abren en pestaña nueva, ícono externo.
**Kill-switch:** estado actual (`CHAT ACTIVO` tag `--money` / `CHAT APAGADO` tag `--danger`) · quién y cuándo lo accionó por última vez · botón «Apagar el chat de la plataforma…».

### Estados
- **Carga:** skeletons por panel.
- **Vacío:** sin bridges registrados → empty-state en esa zona («Ningún dispositivo conectó su bridge todavía. El bridge tat-mcp se conecta con `tat-mcp --connect`.»). Sin drill de restore aún → «Nunca se probó un restore» con tag `--warn` (un backup no probado no es un backup).
- **Error:** si el endpoint de salud no responde, error-card global — y es información en sí misma («si esta vista no carga, revisá Uptime Kuma desde afuera»: el enlace externo se mantiene arriba).
- **Éxito:** todo verde; refresco cada 30 s.
- **Degradado:** dots ámbar con detalle textual (p. ej. Langfuse lento → «ingesta diferida; los costos del tablero son estimados»). Coincide con el estado `~` del tablero (vista 30).

### Interacciones y casos borde
- **Probar restore:** confirmación simple (no destructiva: restaura **en sandbox**, jamás sobre producción — el modal lo dice). Corre en segundo plano (minutos): botón pasa a loading con «drill en curso…», resultado por toast + se actualiza «último drill». Registra `BACKUP_RESTORE_DRILL` en audit.
- **Kill-switch (apagar):** modal destructivo crítico: lista de consecuencias (nadie puede enviar mensajes nuevos — todos los roles; las sesiones en stream se cortan al terminar el turno; las aprobaciones HITL pendientes **siguen visibles** pero no se pueden aprobar — no generan escrituras a ciegas; los Admin conservan la consola) + causa obligatoria (textarea, va al audit y al banner) + escribir `APAGAR` para habilitar el botón danger. Esc jamás confirma.
- **Estado apagado:** banner global permanente en todas las pantallas de todos los roles: «La plataforma está en pausa por mantenimiento — {causa}» (sin jerga, sin culpa). En esta vista, el panel kill-switch muestra quién/cuándo/causa + botón «Reactivar el chat» (confirmación simple).
- Caso borde: dos Admin accionan a la vez → el segundo recibe el estado ya cambiado (conflicto informado, sin doble registro).
- Caso borde: bridge que reconecta en loop (flapping) → estado `INESTABLE` (`--warn`) si tuvo >3 reconexiones en 10 min, con contador.
- Caso borde: backup OK pero offsite fallido → resultado `PARCIAL` (`--warn`): el detalle distingue destino local vs offsite.
- El kill-switch NO corta los servicios (gateway sigue arriba para los checks): corta el **chat** — la denominación en UI es siempre «apagar el chat de la plataforma», no «apagar el sistema».

### Diferencias por rol
Solo Admin. Cuando el kill-switch está activo, los demás roles ven el banner global y un empty-state en el chat («La plataforma está en pausa por mantenimiento») — especificado en el módulo de chat; acá solo se define el origen.

### Móvil
Funcional para guardia: paneles apilados, tablas con scroll-x. El kill-switch opera desde móvil (caso real de emergencia) — el modal de confirmación es full-width y el campo de confirmación exige teclado completo.

### Notas i18n
- Hostnames, versiones (`tat-mcp v0.4.2`), nombres de bucket: invariantes, mono.
- La causa del kill-switch es contenido del Admin: se muestra tal cual en el banner (sin traducir).
- «Probar restore» / «drill»: en el glosario cerrado, PT-BR usa «testar restauração»; reservar ancho.
- Estados (`CONECTADO`, `DESCONECTADO`, `INESTABLE`, `PARCIAL`) se traducen; los códigos internos no.
