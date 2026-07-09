# 03 — Catálogo de agentes

> **Estado:** v1.0 · Especificación de diseño del módulo «Catálogo de agentes».
> **Fuentes de decisión:** UX-SPEC §3 (ficha de catálogo), §1 (visibilidad configurable por Admin), §10 (la ficha es el onboarding); DESIGN-SYSTEM §6.1 (shell), §8.5 (cards), §9.7 (ocultar vs deshabilitar); ADR-0006 (modelos), ADR-0010 (workflows = sección propia, NO entran a este catálogo).
> **Mockups:** [`13-catalogo.html`](../mockups/13-catalogo.html) · [`14-ficha-agente.html`](../mockups/14-ficha-agente.html)
> **Regla de datos:** todos los datos de los mockups son ficticios. DocAgent / ValidationAgent / DevAgent son los agentes reales del roadmap; «Triage CST» (Beta) y «Consultas TDN v1» (Deprecado) son **datos de ejemplo** inventados solo para demostrar esos dos estados.

---

## Modelo de datos compartido (campos de la ficha)

Ambas vistas consumen el mismo objeto `agent` (publicado desde el registro de agentes + matriz de visibilidad agente×rol que administra el Admin):

| Campo | Tipo / formato | Ejemplo | Vista 13 | Vista 14 |
|---|---|---|---|---|
| `name` | string (no se traduce) | `DocAgent` | ✅ | ✅ |
| `slug` | string ruta | `docagent` | — (URL) | — (URL) |
| `type` | enum: `documental` · `validacion` · `desarrollo` · `experimental` | `documental` | ✅ kicker | ✅ kicker |
| `status` | enum: `activo` · `beta` · `proximamente` · `deprecado` | `activo` | ✅ tag | ✅ tag |
| `phase` | int — solo si `proximamente` | `2` | ✅ en tag | ✅ en tag |
| `description` | string ≤180 caracteres | «Responde consultas sobre Protheus citando TDN y CST…» | ✅ (2 líneas + ellipsis) | ✅ completa |
| `limits[]` | strings — qué NO hace | «Se abstiene si no encuentra evidencia» | — | ✅ |
| `use_cases[]` | strings (3–5) | «Parámetros MV_* de localización BOL» | ✅ máx. 3 | ✅ todos |
| `target_roles[]` | enum[]: roles objetivo | `[funcional, tecnico, admin]` | — | ✅ badges |
| `examples[3]` | strings — prompts clicables | «¿Qué parámetros MV_* afectan…?» | — | ✅ |
| `model_profile` | string mono (no se traduce) | `deepseek-v4-flash` | — | ✅ ficha técnica |
| `escalation_enabled` | bool — escalación manual a Pro | `true` | — | ✅ ficha técnica |
| `cost_estimate` | objeto: `avg_usd`, `cached_in {tok,usd}`, `fresh_in {tok,usd}`, `out {tok,usd}`, `cache_saving_pct`, `window_days` | `USD 0,0184` / 30 días | ✅ resumen (capa técnica) | ✅ desglose |
| `prompt_version` | string mono `agente@N` + `published_at` + `published_by` | `docagent@12` | ✅ (capa técnica) | ✅ + changelog |
| `evals` | objeto: `score_pct`, `cases`, `safety_pass` (`n/n`), `last_run_at`, `by_category[]` | `94% · 47 casos` | ✅ score (capa técnica) | ✅ desglose |
| `owner` | string usuario | `Mario Pereyra (mario)` | — | ✅ |
| `hitl_policy` | string | «No aplica — agente solo-lectura» | — | ✅ |
| `data_policy` | string | «N0–N2 permitidos · N3 bloqueado» | — | ✅ |
| `tools[]` | objetos: `name` (mono), `kind` (`lectura`/`escritura`), `scope` | `tdn_search · lectura` | — | ✅ tabla |
| `replacement` | ref a otro agente — solo si `deprecado` | → `docagent` | ✅ CTA «Ver reemplazo» | ✅ banner |

**Visibilidad (matriz agente×rol, UX-SPEC §1 y §3):** qué agente ve cada rol es **configuración de instancia administrada por el Admin**, no hardcode. Defaults recomendados de la instancia Resultar: `activo`/`beta` según matriz; `proximamente` visible para Admin+Técnico (expectativa para quien lo usará) y oculto para Funcional salvo habilitación explícita; `deprecado` visible solo para Admin. Lo que un rol no tiene **no se renderiza** (§9.7 — jamás deshabilitado como promesa).

**Semántica de estados (tags):**

| Estado | Composición visual | Racional |
|---|---|---|
| Activo | `.tag--money` + dot verde pulsante (`.live-dot` 6 px) + texto «ACTIVO» | verde = OK/éxito; el dot comunica «en servicio ahora» |
| Beta | `.tag--warn` «BETA» | advertencia honesta: publicado en prueba, calidad no garantizada (P5) |
| Próximamente | `.tag` neutral «PRÓXIMAMENTE · FASE N» | informativo, sin carga semántica de color |
| Deprecado | `.tag--outline` neutral «DEPRECADO» + card con borde punteado y texto en `--ink-dim` | NO es rojo (danger se reserva a peligro real, §5.1); se atenúa **sin** `opacity` global para no romper AA |

---

## Vista 13 — `13-catalogo.html` · Catálogo (grilla de fichas)

### Propósito

Interfaz de descubrimiento de agentes («un agente que nadie sabe que existe no se usa», UX-SPEC §3). Es la página de aterrizaje tras el login para todos los roles: muestra qué agentes tiene asignados el usuario, su estado operativo, y abre el chat o la ficha de detalle. Para Funcional es además la puerta del onboarding (de acá llega a los ejemplos clicables de la ficha).

### Quién la ve (roles y capacidades)

| Capacidad | Funcional | Técnico | Admin |
|---|---|---|---|
| Ver grilla filtrada por su matriz de visibilidad | ✅ | ✅ | ✅ (ve todo) |
| Buscar y filtrar por estado | ✅ | ✅ | ✅ |
| Capa técnica en cards (prompt-version · costo/sesión · evals) | ❌ no se renderiza | ✅ | ✅ |
| Ver agentes `proximamente` | solo si el Admin lo habilita | ✅ (default) | ✅ |
| Ver agentes `deprecado` | ❌ | ❌ | ✅ |
| Selector «Ver como rol» (previsualizar la grilla de otro rol) | ❌ | ❌ | ✅ |
| Editar el catálogo / la matriz de visibilidad | ❌ | ❌ | ✅ pero NO acá: se hace en la consola admin; este módulo es solo lectura |

### Layout

Shell estándar (DESIGN-SYSTEM §6.1): ai-banner permanente + sidebar 240 px + topbar + contenido máx. 1200 px. Sin taxímetro en topbar (solo existe dentro de una sesión de chat). Ítem «Catálogo» activo en sidebar.

```
┌──────────────────────────────────────────────────────────────────┐
│ ai-banner — Respuestas generadas por IA — verificá antes…        │
├──────────┬───────────────────────────────────────────────────────┤
│ sidebar  │ topbar:  Catálogo            [campana] [badge rol] u… │
│          ├───────────────────────────────────────────────────────┤
│  Chat    │ CATÁLOGO ·······························  (kicker)    │
│ ▸Catálogo│ Agentes                                   (h1)        │
│  Workflo…│ Elegí un agente para abrir un chat…       (lead)      │
│  Aprobac.│                                                       │
│  ────────│ [🔍 buscar…………………] [Estado ▾] [Ver como ▾*]  *Admin   │
│  Telemetr│ 5 agentes · mostrando 5            (contador, live)   │
│  Consola │ ┌──────────┐ ┌──────────┐ ┌──────────┐                │
│  (capas  │ │ card     │ │ card     │ │ card     │                │
│  de rol) │ └──────────┘ └──────────┘ └──────────┘                │
│          │ ┌──────────┐ ┌──────────┐                             │
│          │ │ card     │ │ card     │   grid auto-fill            │
│          │ └──────────┘ └──────────┘   minmax(280px, 1fr)        │
└──────────┴───────────────────────────────────────────────────────┘
```

Anatomía de la card (extiende `.panel`, §8.5):

```
┌────────────────────────────────┐
│ AGENTE · DOCUMENTAL   [●ACTIVO]│  kicker tipo + tag estado
│ DocAgent                       │  h3 (texto, no enlace)
│ Responde consultas sobre…      │  descripción, 2 líneas máx.
│ ▸ Parámetros MV_* de BOL       │  casos de uso (máx. 3,
│ ▸ Documentación de rutinas     │   fs-small, --ink-dim)
│ ▸ Errores con evidencia CST    │
│ ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄ │  ← capa técnica (Téc/Admin):
│ docagent@12 · USD 0,0184/ses · │     mono caption, borde sup.
│ evals 94%                      │
│ ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄ │
│ [Abrir chat]        Ver ficha →│  CTA secondary + enlace info
└────────────────────────────────┘
```

- El CTA de card es `.btn--secondary` (no primary): la regla «máx. 1 botón primario por zona» (§6.2) prohíbe una grilla de primarios. El primario vive en la ficha (vista 14).
- La card NO es 100% clickable: tiene dos destinos (chat y ficha). Navegación a la ficha por el enlace explícito «Ver ficha →» (`--info`, §5.2).

### Componentes usados

`.panel` (card) · `.tag` + `.tag--money/--warn/--outline` · `.live-dot` (6 px, dentro del tag ACTIVO) · `.kicker` / `.kicker--dim` · `.btn--secondary .btn--sm` · `.input` (búsqueda, con `<label>` oculto `.sr-only`) · `.select` (filtro estado; «Ver como» solo Admin) · `.badge-rol` (topbar) · `.notif-bell` · `.ai-banner` · `.empty-state` (2 variantes) · `.error-card` · `.skeleton` (cards de carga) · enlaces `--info`. Nuevo en este módulo (clases locales del mockup, anatomía documentada arriba): `agent-card__cases` (lista de casos), `agent-card__tech` (capa técnica), `agent-card__foot`.

### Datos que muestra (campos exactos)

Por card: `type` (kicker, mayúsculas vía CSS) · `status` (+ `phase` si próximamente) · `name` · `description` (truncada a 2 líneas con `-webkit-line-clamp`) · `use_cases[0..2]` · capa técnica solo Téc/Admin: `prompt_version` + `cost_estimate.avg_usd` (formato `USD 0,0184/ses`, §9.8) + `evals.score_pct` · CTA según estado (ver Interacciones). Encabezado de página: contador «{n} agentes · mostrando {m}» (mono, `aria-live="polite"`). Controles: query de búsqueda (matchea `name`, `description`, `use_cases`), filtro `status`, y «Ver como rol» (Admin).

### Estados

| Estado | Comportamiento |
|---|---|
| **Carga** | 3 cards skeleton con la silueta real (título 50%, 2 líneas, footer); `aria-busy="true"` en la grilla. Solo si la carga estimada >300 ms (§8.23). |
| **Vacío — rol sin agentes** | `.empty-state` con ícono `bot`: título «Tu rol todavía no tiene agentes asignados», hint «Hablá con el administrador para que te habilite el acceso a un agente.» Sin CTA (Funcional no puede resolverlo solo); el Admin recibe la señal por otra vía (consola). |
| **Vacío — búsqueda sin resultados** | «Sin resultados para “{query}”» + botón «Limpiar filtros» + enlace secundario «¿Buscabas un workflow? Están en su propia sección →» (los workflows NO viven en este catálogo, ADR-0010). |
| **Error de carga** | `.error-card` danger, código mono `CATALOG_OFFLINE` (plantilla §9.6): qué pasó («No se pudo cargar el catálogo»), por qué («El servidor no respondió a tiempo»), qué hacer (botón «Reintentar»). `role="alert"`. Para Funcional el código va en segundo plano («código para soporte: …»). |
| **Éxito** | Grilla renderizada; el contador anuncia el total por `aria-live`. |
| **Degradado** | Si la telemetría (Langfuse) no responde, la capa técnica de las cards muestra `~` antes del costo + tooltip «costo estimado, telemetría diferida» (convención del taxímetro §8.12). El catálogo NUNCA se bloquea por cuota: cuota 100% se manifiesta recién en el composer del chat. |

### Interacciones y casos borde

- **«Abrir chat»** (estado `activo`/`beta`): crea sesión nueva con ese agente y navega al chat. Beta no agrega fricción extra: el tag ya comunica la expectativa.
- **`proximamente`**: botón «Abrir chat» deshabilitado (atributo `disabled`, §9.7 — es «temporalmente imposible», no un permiso) + motivo visible al lado: «Disponible en Fase {n}». «Ver ficha →» sigue activo (la ficha genera expectativa correcta).
- **`deprecado`** (solo Admin): sin «Abrir chat»; CTA «Ver reemplazo →» navega a la ficha del agente que lo sustituye. Las sesiones históricas del agente siguen consultables desde el historial de chat, pero no se pueden iniciar nuevas.
- **Búsqueda**: filtra en cliente sobre `name`/`description`/`use_cases`; debounce 200 ms; el contador y la grilla se actualizan juntos; query vacía restaura todo.
- **Filtro estado**: select simple; combinable con búsqueda; «Limpiar filtros» resetea ambos.
- **«Ver como rol» (Admin)**: previsualiza la grilla exactamente como la ve otro rol (incluye ocultar la capa técnica si elige Funcional). Es solo preview visual — no cambia permisos ni registra nada.
- **Visibilidad cambia en caliente**: si el Admin quita un agente de la matriz mientras el usuario navega, el agente desaparece en la próxima carga; un deep-link a su ficha cae en el estado «no disponible» de la vista 14 (jamás un error de permisos crudo, §9.7).
- **Conteo**: cambios de resultado anunciados por `aria-live="polite"`; el foco no se mueve al filtrar.
- **Orden**: fijo por instancia (activos primero, luego beta, próximamente, deprecado; alfabético dentro de cada grupo). Sin ordenamiento por usuario en v1.

### Diferencias por rol

| Elemento | Funcional | Técnico | Admin |
|---|---|---|---|
| Cards visibles (instancia Resultar de ejemplo) | 2 — DocAgent, Triage CST | 4 — + ValidationAgent y DevAgent (próximamente) | 5 — + Consultas TDN v1 (deprecado) |
| Capa técnica de card | no existe | ✅ | ✅ |
| Selector «Ver como rol» | no existe | no existe | ✅ |
| Texto del error de carga | sin jerga, código en segundo plano | código mono visible y copiable | código mono visible y copiable |
| Sidebar | Chat · Catálogo · Workflows | + Aprobaciones | + Telemetría · Consola admin |

### Móvil (380 px)

Soporte ✅ completo (DESIGN-SYSTEM §11): grilla → 1 columna; sidebar → drawer (botón ≡ en topbar); buscador y filtros apilados a ancho completo; cards con CTA a ancho completo y objetivo táctil ≥44 px; el enlace «Ver ficha →» gana padding invisible para alcanzar 44 px.

### Notas i18n

- Todos los strings por claves de catálogo; reservar +25% para PT-BR (los CTA «Abrir chat» / «Ver ficha» caben holgados).
- Plural ICU para el contador: `{n, plural, one {# agente} other {# agentes}}`.
- NO se traducen: nombres de agente (`DocAgent`), versiones (`docagent@12`), nombres de modelo, códigos de error (`CATALOG_OFFLINE`).
- Tags en mayúsculas solo por CSS (texto fuente en sentence case — lectores de pantalla, §8.6).
- Números/moneda por `Intl` con locale de instancia (es-BO: `USD 0,0184`).

---

## Vista 14 — `14-ficha-agente.html` · Ficha de agente (detalle)

### Propósito

La ficha completa de un agente: qué hace, qué no hace, para quién es, y cómo empezar (3 ejemplos clicables = onboarding, UX-SPEC §10). Para Técnico y Admin agrega el **bloque ficha técnica**: la radiografía operativa del agente (tools, costo con desglose, versión de prompt, evals, owner, políticas HITL y de datos) — transparencia P2 sin contaminar la experiencia del Funcional.

### Quién la ve (roles y capacidades)

| Capacidad | Funcional | Técnico | Admin |
|---|---|---|---|
| Cabecera + descripción + límites + casos de uso + ejemplos | ✅ | ✅ | ✅ |
| Bloque ficha técnica (tabs Resumen/Tools/Prompt/Evals) | ❌ no se renderiza | ✅ | ✅ |
| Enlace «Abrir en registro de prompts» (dentro de tab Prompt) | — | ❌ (ve versión y changelog, no la consola) | ✅ |
| Acceso | solo a agentes de su matriz; deep-link fuera de matriz → estado «no disponible» | ídem | todos |

### Layout

Mismo shell que la vista 13. Contenido en columna única máx. 880 px (lectura), apilado: breadcrumb → cabecera → descripción/límites → casos de uso → primeros pasos → ficha técnica (si el rol la tiene).

```
┌──────────────────────────────────────────────────────────────┐
│ ai-banner                                                    │
├─────────┬────────────────────────────────────────────────────┤
│ sidebar │ topbar                                             │
│         ├────────────────────────────────────────────────────┤
│         │ ← Catálogo                          (breadcrumb)   │
│         │ AGENTE · DOCUMENTAL                 (kicker)       │
│         │ DocAgent  [● ACTIVO]            [Abrir chat]       │
│         │ Para: ADMIN · TÉCNICO · FUNCIONAL   (badges)       │
│         │ ┌────────────────────────────────────────────────┐ │
│         │ │ Qué hace (descripción) · Qué NO hace (límites) │ │
│         │ ├────────────────────────────────────────────────┤ │
│         │ │ Casos de uso ideales (lista)                   │ │
│         │ ├────────────────────────────────────────────────┤ │
│         │ │ Primeros pasos — 3 ejemplos clicables          │ │
│         │ ├────────────────────────────────────────────────┤ │
│         │ │ FICHA TÉCNICA (solo Téc/Admin)                 │ │
│         │ │ [Resumen][Tools][Prompt][Evals]   (tabs §8.7)  │ │
│         │ │  …contenido de la tab activa…                  │ │
│         │ └────────────────────────────────────────────────┘ │
└─────────┴────────────────────────────────────────────────────┘
```

### Componentes usados

`.panel` · `.tag` (estados, riesgo, categorías) · `.badge-rol` (roles objetivo) · `.btn--primary` («Abrir chat» — el ÚNICO primario de la vista) · `.btn--secondary` · `.tabs`/`.tab` (patrón WAI-ARIA tabs, §8.7) · `.table` (tools, desglose de costo, evals por categoría) · `.kicker` · `.live-dot` · `.empty-state` (variante «no disponible») · `.error-card--warn` (banner deprecado) · tooltip `[data-tip]` · `.ai-banner` · `.notif-bell`. Nuevo en este módulo: **botón-ejemplo** (`example-btn`): `<button>` con ícono `quote`, texto del prompt y affordance «usar →»; estados default/hover/focus/disabled.

### Datos que muestra (campos exactos)

**Cabecera (todos los roles):** `type` (kicker) · `name` (h1) · `status` (+`phase`) · `target_roles[]` (badges de rol) · CTA «Abrir chat».
**Cuerpo (todos los roles):** `description` completa · `limits[]` (lista «qué no hace» — para DocAgent incluye la abstención sin evidencia y que jamás escribe en Protheus) · `use_cases[]` completos · `examples[3]` clicables.
**Ficha técnica (Téc/Admin) por tab:**
- *Resumen:* `model_profile` (`deepseek-v4-flash`, mono) · `escalation_enabled` (tag «escalación a Pro: manual» + `deepseek-v4-pro`) · `owner` · fecha de publicación · `hitl_policy` · `data_policy` · `cost_estimate`: promedio `USD 0,0184/sesión` (ventana 30 días) con tabla de desglose — input cacheado `38,4k tok · USD 0,0031`, input nuevo `5,2k tok · USD 0,0083`, output `2,9k tok · USD 0,0070` — y fila «ahorro por cache ≈58%» en `--money`.
- *Tools:* tabla `name` (mono) · `kind` (tag `lectura`/`escritura`) · `scope` (1 línea). Nota fija: «Toolset completo y fijo por versión de agente (cache-first, ADR-0001).» Si hubiera tools de escritura (ValidationAgent), la fila las marca `tag--warn` y la nota remite a la política HITL.
- *Prompt:* `prompt_version` activa (`docagent@12` mono) · publicada por/cuándo · estado «evals verdes» · changelog corto de las últimas 2-3 versiones · (solo Admin) enlace «Abrir en registro de prompts →».
- *Evals:* `score_pct` protagonista (`--fs-display`, verde si ≥80, `--warn` si quedó debajo del gate) · `cases` · `safety_pass` («6/6 — hard-fail individual») · `last_run_at` · tabla por categoría (citas/abstención/formato/safety).

### Estados

| Estado | Comportamiento |
|---|---|
| **Carga** | Skeleton con la silueta (título, párrafos, bloque); `aria-busy`. |
| **Vacío / no disponible** | Deep-link a agente fuera de la matriz del rol (o slug inexistente): `.empty-state` «Este agente no está disponible» + hint «Puede que no exista o que tu rol no tenga acceso. Hablá con el administrador.» + CTA «Volver al catálogo». No se distingue “no existe” de “sin permiso” (no filtrar existencia). |
| **Error de carga** | `.error-card` con «Reintentar», mismo patrón que la vista 13. |
| **Éxito** | Ficha completa según rol. |
| **Degradado** | Telemetría caída → costos con `~` + tooltip «estimado, telemetría diferida». Evals sin corrida reciente (>7 días) → fecha en `--warn` con tooltip. Agente nuevo sin datos de costo → `—` («sin datos todavía», convención §8.12). Score <80% en agente activo → tag `--warn` «debajo del gate» en tab Evals (el bloqueo de publicación es del CI; acá solo transparencia). |

### Interacciones y casos borde

- **Ejemplo clicable** (`activo`/`beta`): abre una sesión nueva con el agente y deja el prompt **prellenado en el composer, sin enviar** — el usuario revisa y envía (control humano, coherente con P5). Anuncio `aria-live`: «ejemplo copiado al chat».
- **`proximamente`** (p. ej. ValidationAgent): CTA «Abrir chat» deshabilitado con motivo adyacente «Disponible en Fase 2»; los 3 ejemplos se muestran **deshabilitados** (`disabled` + `aria-disabled`, §9.7: temporalmente imposible para todos, no cuestión de permisos) — se leen igual porque son parte de la expectativa. Ficha técnica: campos sin valor en `—` (sin versión de prompt activa, sin evals); tools previstas sí se listan.
- **`deprecado`**: banner `--warn` arriba de la cabecera: «Este agente fue reemplazado por {replacement} →»; sin CTA «Abrir chat»; resto de la ficha en solo-lectura para auditoría (Admin).
- **«Abrir chat» con cuota 100%**: el catálogo no bloquea; al entrar al chat el composer muestra el flujo QUOTA estándar (aviso/bloqueo + «Solicitar liberación»). Nunca se intercepta acá.
- **Tabs**: roving focus con flechas ←→ (WAI-ARIA), `aria-selected`, panels `role="tabpanel"`; la tab activa persiste al navegar entre fichas en la misma sesión de navegación (preferencia efímera, no persistida).
- **Breadcrumb «← Catálogo»**: conserva búsqueda/filtros activos de la vista 13 (volver no resetea).
- **Owner ausente** (usuario dado de baja): se muestra el último owner con tag `--warn` «sin owner activo» — señal para el Admin.

### Diferencias por rol

| Elemento | Funcional | Técnico | Admin |
|---|---|---|---|
| Bloque ficha técnica completo | no existe (ni siquiera colapsado) | ✅ | ✅ |
| Enlace al registro de prompts (tab Prompt) | — | ❌ | ✅ |
| Banner/ficha de agentes deprecados | no llega (no los ve en la grilla; deep-link → «no disponible») | ídem | ✅ |
| Texto de límites | idéntico para todos — sin jerga técnica en la zona común («No inventa respuestas: si no encuentra evidencia, te lo dice») | + la ficha técnica puede usar jerga (`tokens`, `cache`) | ídem |

### Móvil (380 px)

Soporte ⚠️ lectura completa (la ficha técnica es de consulta): columna única; CTA «Abrir chat» a ancho completo bajo la cabecera; badges envuelven; tabs con scroll-x sin wrap (§8.7); tablas (tools, desglose) con scroll-x y sombra de affordance; botones-ejemplo a ancho completo con alto táctil ≥44 px.

### Notas i18n

- Claves externalizadas; +25% de reserva — crítico en labels de la ficha técnica («Versión de prompt activa» crece en PT-BR).
- NO se traducen: `model_profile`, nombres de tools (`tdn_search`), versiones (`docagent@12`), parámetros del dominio en ejemplos (`MV_PAISLOC`, `SX6`, `MATA010`), códigos de error.
- Los textos de `examples[]` y `use_cases[]` son contenido del registro de agentes (datos de instancia): se traducen en el registro, no en el catálogo de mensajes de la UI.
- Plantillas con placeholders nombrados: «Disponible en Fase {fase}», «Este agente fue reemplazado por {agente}» (las traducciones reordenan).
- Fechas `dd/mm/aaaa HH:mm` por `Intl` es-BO; el formato no se hardcodea.
