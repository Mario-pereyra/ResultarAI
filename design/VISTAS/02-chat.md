# 02 — Chat y conversación

> **Estado:** v1.0 — especificación de diseño del módulo de chat.
> **Mockups:** [`05-chat-funcional.html`](../mockups/05-chat-funcional.html) · [`06-chat-admin.html`](../mockups/06-chat-admin.html) · [`07-composer-attachments.html`](../mockups/07-composer-attachments.html) · [`08-escalacion.html`](../mockups/08-escalacion.html) · [`09-branching.html`](../mockups/09-branching.html) · [`10-errores.html`](../mockups/10-errores.html) · [`11-citas.html`](../mockups/11-citas.html) · [`12-historial.html`](../mockups/12-historial.html)
> **Relación:** [DESIGN-SYSTEM.md](../DESIGN-SYSTEM.md) (componentes §8, patrones §9, formatos §9.8) · [ANEXO-ATTACHMENTS.md](../ANEXO-ATTACHMENTS.md) (pipeline de adjuntos) · ADR-0001/0006 (cache-first, modelos) · ADR-0007/0010 (cuotas, memoria) · UX-SPEC.
> Todos los datos de los mockups son **ficticios** (Comercial Andina S.A., usuaria «lucia», montos de ejemplo).

---

## 0. Alcance y reglas transversales del módulo

El chat es la superficie principal del producto: una conversación con un agente del catálogo (DocAgent, ValidationAgent, DevAgent), en **una sola UI compartida** donde las capacidades se agregan por capa de rol (DS §1-P3). Lo que un rol no tiene, **no se renderiza** (DS §9.7).

### 0.1 Anatomía común (shell de chat)

```
┌──────────────────────────────────────────────────────────────┐
│ ai-banner — "Respuestas generadas por IA — verificá antes…"  │  permanente, todos los roles
├──────────────────────────────────────────────────────────────┤
│ chat-top: [avatar] Nombre del agente      [taxímetro*] [⋯]   │  * solo Técnico/Admin
│           descripción en 1 línea                             │
├──────────────────────────────────────────────────────────────┤
│                                                              │
│        columna de mensajes — máx. 760 px centrada            │
│        msg usuario (derecha) / msg agente (izquierda)        │
│        metadatos por turno según rol (§0.3)                  │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│ composer: [clip] textarea autosize            [enviar/stop]  │
│ hint: Enter envía · Shift+Enter salto · estado de espacio    │
└──────────────────────────────────────────────────────────────┘
```

### 0.2 Reglas duras heredadas (no negociables en ninguna vista)

1. **Append-only / branch-never-rewrite:** editar un mensaje o regenerar una respuesta crea una **versión nueva** navegable con `.branch-sel` («versión 1/2»). La historia jamás se reescribe (vista 09).
2. **Stickiness de modelo:** una sesión vive en un solo `model_profile`. Cambiar de modelo (escalación a Pro) = **conversación/rama nueva** (vista 08).
3. **El marcador `<<<NEEDS_PRO>>>` nunca se muestra:** el stream lo intercepta y lo reemplaza por la tarjeta de escalación. Un marcador llegado dentro de un adjunto no dispara nada (ANEXO §4.3).
4. **Banner IA permanente** (`.ai-banner`) en todos los roles, todas las vistas de chat.
5. **Etiqueta «modelo alterno» para TODOS los roles** cuando hubo fallback de modelo (transparencia, DS §1-P2). Funcional ve la etiqueta con explicación simple; Técnico/Admin ven además el nombre del modelo.
6. **Cuotas evaluadas antes de cada llamada:** aviso al 80% (warn no bloqueante), bloqueo al 100% (ErrorCard `QUOTA` + composer deshabilitado, vista 10).
7. **Tool-calls como líneas de actividad plegadas** («consultando TDN…»); args/latencia solo Técnico/Admin (DS §9.4).
8. **Jerga prohibida en Funcional:** nada de "LLM", "tokens", "cache", "prefix". Los códigos de error existen pero en segundo plano («código para soporte: …»).

### 0.3 Metadatos por turno del agente × rol

| Dato | Funcional | Técnico | Admin |
|---|---|---|---|
| Hora (relativa, tooltip absoluta) | ✅ | ✅ | ✅ |
| Acciones: copiar · regenerar · 👍/👎 | ✅ | ✅ | ✅ |
| Tag «modelo alterno» (si hubo fallback) | ✅ | ✅ | ✅ |
| Latencia (`3,2 s`) | — | ✅ | ✅ |
| Perfil LLM (`deepseek-v4-flash`) | — | ✅ | ✅ |
| Chips cache `HIT/MISS/WRITE` + tokens | — | ✅ | ✅ |
| Costo del turno (`USD 0,0042`) | — | ✅ | ✅ |
| Enlace «ver traza» (Langfuse) | — | — | ✅ |
| Taxímetro de sesión (header) | — | ✅ | ✅ |

### 0.4 Streaming (DS §9.4)

Texto en stream con **cursor de bloque parpadeante** al final; auto-scroll solo si el usuario está abajo (si scrolleó: botón flotante «↓ Nuevos mensajes»); botón **«Detener»** visible durante todo el stream (reemplaza al de enviar); al completar el turno aparecen los metadatos. Región `aria-live` anuncia al **completar** el turno, no token por token.

### 0.5 Formatos

Todos los números/fechas según DS §9.8: `USD 0,0042` (4 decimales LLM), `12,4k tok`, `dd/mm/aaaa HH:mm`, relativo <24 h con absoluto en tooltip. Siempre `--font-mono` + `tabular-nums`.

---

## 1. Vista 05 — Chat (rol Funcional)

**Mockup:** [`mockups/05-chat-funcional.html`](../mockups/05-chat-funcional.html)

### Propósito
La experiencia base de conversación: limpia, tipo ChatGPT, sin un solo dato técnico. Es la vista que define el "piso" del chat; las demás capas (telemetría, ficha) se agregan encima sin alterar esta anatomía.

### Quién la ve (roles y capacidades)
- **Funcional:** exactamente lo que muestra el mockup. Cero costos, cero chips de cache, cero nombres de modelo, cero jerga.
- **Técnico/Admin:** ven esta misma vista **más** la capa de telemetría (vista 06). La anatomía no cambia: misma columna, mismos mensajes, mismos controles.

### Layout

```
┌────────────────────────────────────────────────┐
│ ai-banner                                      │
│ [🤖] DocAgent — Buscá respuestas en la         │
│      documentación TOTVS con fuentes citadas   │
├────────────────────────────────────────────────┤
│  NUEVA SESIÓN:        ┌───────────┐            │
│  saludo corto +       │sugerencia │ ×3-4       │
│  sugerencias clicables└───────────┘            │
│  ──────────── o ────────────                   │
│                      ┌────────────────┐        │
│                      │ mensaje usuario│ (der.) │
│ [🤖] respuesta del agente en markdown          │
│      hace 2 min · [copiar][regenerar][👍][👎] │
│ [🤖] respuesta en streaming ▌  [Detener]       │
├────────────────────────────────────────────────┤
│ [📎] Escribile a DocAgent…            [enviar] │
│ Enter envía · Shift+Enter salto de línea       │
└────────────────────────────────────────────────┘
```

Columna de mensajes máx. **760 px** centrada (constante en desktop, DS §11). Mensaje de usuario: burbuja `--bg-raised` alineada a la derecha, máx. 85% del ancho. Mensaje del agente: avatar 30 px + cuerpo a ancho completo de la columna (sin burbuja: el contenido largo con markdown respira mejor).

### Componentes usados
`.ai-banner` · `.tag` (modelo alterno: `tag--warn`) · `.btn` (`--primary` enviar, `--secondary` detener) · botones-ícono de turno (ghost 26 px) · `.branch-sel` (si hay regeneraciones) · sugerencias de inicio (cards-botón locales sobre `.panel`) · popover de comentario de feedback (panel local) · `.toast--ok` (feedback enviado) · skeleton (carga de sesión).

### Datos que muestra (campos exactos)
- **Header:** `agent.icon`, `agent.display_name`, `agent.short_description` (1 línea, la misma del catálogo).
- **Sugerencias de inicio:** `agent.starter_prompts[]` (3-4 strings configurados por agente en el catálogo). Click = inserta el texto en el composer y enfoca (no envía solo).
- **Mensaje usuario:** `content` (texto plano con saltos), chips de adjuntos si los hay (vista 07).
- **Mensaje agente:** `content` renderizado markdown (negritas, listas, tablas, bloques de código con lenguaje), hora relativa.
- **Acciones por turno del agente:** copiar (copia el markdown fuente) · regenerar · 👍 · 👎.
- **Feedback:** al pulsar 👍/👎 el ícono queda activo y aparece popover «¿Querés agregar un comentario? (opcional)» con textarea + «Enviar» + «Omitir». El feedback va a Langfuse como score del turno.
- **Tag «modelo alterno»:** junto a la hora. Tooltip Funcional: «Esta respuesta la generó un modelo alternativo porque el habitual no estaba disponible. La calidad puede variar.»

### Estados
- **Carga (sesión existente):** skeleton de 2-3 turnos en la silueta real (avatar + líneas 100/80/90%), `aria-busy`.
- **Vacío (sesión nueva):** saludo de 1 línea + grid de sugerencias clicables. El foco inicial va al composer.
- **Streaming:** cursor de bloque ámbar parpadeante; «Detener» visible; acciones del turno ocultas hasta completar. Línea de actividad de tools plegada: «consultando TDN…» (spinner pequeño), sin detalle técnico.
- **Error:** ErrorCards de la vista 10 **dentro del flujo de mensajes** (en el lugar donde habría ido la respuesta). El texto del usuario nunca se pierde: queda en el historial y «Reintentar» lo re-envía.
- **Éxito:** turno completo con metadatos y acciones.
- **Degradado:** tag «modelo alterno» en el turno afectado. No es error: la conversación sigue.

### Interacciones y casos borde
- **Enter envía / Shift+Enter** salto de línea; el hint lo dice siempre debajo del composer.
- **Enviar deshabilitado** con composer vacío o con adjuntos aún procesando (motivo en tooltip, DS §9.7).
- **Detener:** corta el stream; lo recibido queda como respuesta parcial marcada «detenida por vos» (caption); regenerar disponible.
- **Regenerar:** crea **versión nueva de la respuesta** (append-only): aparece `.branch-sel` «respuesta 1/2» en el turno. Jamás sobreescribe.
- **Scroll:** auto-scroll solo si el usuario está en el fondo; si subió, botón flotante «↓ Nuevos mensajes».
- **Doble envío:** bloqueado durante el round-trip (composer en estado enviando).
- **Mensaje larguísimo del usuario (>20 líneas):** se colapsa a 10 líneas con «Ver mensaje completo».
- **Sesión en otra pestaña:** el stream continúa server-side; al volver, la vista se reconcilia (no se duplica el turno).
- **Caso borde feedback:** cambiar de 👍 a 👎 reemplaza el score anterior; el popover de comentario reaparece.

### Diferencias por rol
Esta vista ES el rol Funcional. Técnico/Admin parten de aquí y agregan §0.3. Nada de lo Funcional se quita en roles superiores (las capas suman, nunca restan).

### Móvil
✅ Completo (DS §11). Sidebar → drawer; columna a ancho completo con gutter 16 px; burbuja usuario máx. 90%; acciones de turno con objetivo táctil ≥44 px (padding invisible); sugerencias en 1 columna; composer fijo abajo con `safe-area`.

### Notas i18n
- Claves: `chat.composer.placeholder` («Escribile a {agent}…»), `chat.hint.enter`, `chat.actions.copy/regenerate/like/dislike`, `chat.feedback.prompt`, `chat.tag.alt_model`, `chat.stream.stop`, `chat.stream.new_messages`.
- El saludo y las sugerencias vienen de la config del agente (contenido, no UI) — se traducen como datos de catálogo.
- Reservar +25% en botones («Detener» → «Interromper»); el tag «modelo alterno» en PT-BR («modelo alternativo») crece: el tag no debe truncar.

---

## 2. Vista 06 — Chat con capa de telemetría (Técnico/Admin)

**Mockup:** [`mockups/06-chat-admin.html`](../mockups/06-chat-admin.html)

### Propósito
La **misma conversación** de la vista 05 con la capa de transparencia económica encima: cuánto costó cada turno, qué sirvió el cache, qué modelo respondió y (Admin) la traza completa. Materializa el principio P2: hacer visible el costo crea la cultura que sostiene el cache-first.

### Quién la ve (roles y capacidades)
- **Técnico:** taxímetro, chips de cache, costo/latencia/perfil por turno. **NO** ve «ver traza» (la traza vive en telemetría, que es solo Admin).
- **Admin:** todo lo anterior + enlace «ver traza» por turno (abre la traza Langfuse en la consola) + tooltip de desglose del taxímetro.
- **Funcional:** esta capa **no existe** para él — ni oculta ni deshabilitada (DS §9.7, §8.12).

### Layout

```
┌──────────────────────────────────────────────────────┐
│ ai-banner                                            │
│ [🤖] DocAgent — …       [SESIÓN USD 0,0214 · 48,1k] │ ← taxímetro
├──────────────────────────────────────────────────────┤
│                          ┌─────────────────┐         │
│                          │ mensaje usuario │         │
│ [🤖] respuesta…                                      │
│  hace 2 min · 3,2 s · deepseek-v4-flash ·            │
│  [HIT · 41,2k][MISS · 1,8k] · USD 0,0042 · ver traza │ ← fila de telemetría
├──────────────────────────────────────────────────────┤
│ composer (idéntico a 05)                             │
└──────────────────────────────────────────────────────┘
```

La fila de telemetría se agrega **a la misma fila de metadatos** del turno (no es un panel aparte): mono 11 px, `--ink-faint`, separadores `·`.

### Componentes usados
Todo lo de la vista 05 + `.taximeter` (compacto, en header) · `.chip-cache` (`--hit/--miss/--write`) · `.tag--outline` mono para el perfil LLM · enlace `--info` «ver traza» con ícono externo · tooltip de desglose del taxímetro.

### Datos que muestra (campos exactos)
- **Taxímetro:** `session.cost_usd` acumulado (mono verde, 4 decimales), `session.total_tokens` (`48,1k tok`). Tooltip/desglose (Admin): input cacheado / input no cacheado / output / % ahorro por cache.
- **Por turno del agente:** `latency_s` (`3,2 s`) · `model_profile` (`deepseek-v4-flash`) · `cache.hit_tokens` / `cache.miss_tokens` (chips `HIT · 41,2k` / `MISS · 1,8k`; `WRITE` cuando aplique) · `turn.cost_usd` (`USD 0,0042`, verde) · `trace_url` (Admin).
- **Fallback:** si hubo, el tag «modelo alterno» convive con el perfil real usado: `kimi-k2.6` + tooltip «fallback desde deepseek-v4-flash: proveedor caído 14:31».

### Estados
- **Carga:** el taxímetro muestra `—` hasta el primer dato; chips ausentes hasta completar el turno (nunca skeleton de chips: llegan con el turno).
- **Vacío:** sesión nueva = taxímetro en `USD 0,0000`.
- **Error:** igual que 05; un turno fallido no suma costo y no muestra chips.
- **Éxito:** fila completa de telemetría al cerrar cada turno; el taxímetro incrementa con transición suave (sin parpadeo).
- **Degradado (Langfuse caído):** taxímetro con `~` antes del monto + tooltip «costo estimado, telemetría diferida»; «ver traza» deshabilitado con motivo; banner warn de la vista 10 (solo Admin).

### Interacciones y casos borde
- **«ver traza»** abre la traza en la consola admin (nueva pestaña); requiere sesión admin activa — jamás URL pública de Langfuse.
- **Tooltip de chips:** `HIT` → «prefijo servido desde cache: ahorro ~90% en esos tokens»; `MISS` → «tokens procesados sin cache (primera vez)»; `WRITE` → «prefijo escrito al cache para los próximos turnos».
- **Turno con miss inesperadamente alto** (regresión de cache): sin alarma en chat — eso vive en telemetría; el chat solo muestra el dato honesto.
- **Respuestas regeneradas:** cada versión tiene su propia fila de telemetría; el taxímetro suma todas (también las descartadas — se pagaron).
- **Taxímetro congelado** al archivar la sesión.

### Diferencias por rol
| Elemento | Técnico | Admin |
|---|---|---|
| Taxímetro compacto | ✅ | ✅ |
| Desglose del taxímetro (tooltip/sheet) | resumen | completo + % ahorro |
| Chips cache + costo/turno | ✅ | ✅ |
| «ver traza» | — | ✅ |

### Móvil
✅ Chat completo; el **taxímetro sale del header** y vive en el menú de sesión (⋯) (DS §8.12). La fila de telemetría envuelve a 2 líneas; «ver traza» se mantiene al final.

### Notas i18n
- No se traducen: nombres de modelo, `HIT/MISS/WRITE`, códigos. Sí: `chat.meta.view_trace` («ver traza»), labels del taxímetro (`SESIÓN`).
- El desglose usa plantillas con placeholders («{pct} de ahorro por cache»), formato `Intl` es-BO.

---

## 3. Vista 07 — Composer con adjuntos

**Mockup:** [`mockups/07-composer-attachments.html`](../mockups/07-composer-attachments.html)

### Propósito
Adjuntar archivos con **transparencia total** del pipeline (ANEXO-ATTACHMENTS): el usuario ve el estado de cada archivo, **exactamente qué verá el agente** (vista previa de extracción), cuánto espacio consume, y las advertencias de nivel de datos (N2/N3) **antes** de enviar. Diferencial frente a ChatGPT/Claude: nada se trunca ni descarta en silencio.

### Quién la ve (roles y capacidades)
Todos los roles adjuntan igual. Diferencia única: el costo en el chip se expresa en **tokens** para Técnico/Admin (`≈3,1k tok`) y como **% de espacio** para Funcional («usa 34% del espacio del mensaje»). La vista previa de extracción existe para todos (es comprensible, no jerga).

### Layout

```
┌──────────────────────────────────────────────────────┐
│ Acepta: .pdf .xlsx .csv .docx .txt .log .prw … ·     │ ← límites visibles (popover del clip)
│ máx. 5 archivos · hasta 30 MB según tipo             │
├──────────────────────────────────────────────────────┤
│ [chip ⏳ subiendo 45%] [chip ⚙ procesando…]          │
│ [chip ✓ listo · tabla 120 filas × 8 col · ≈3,1k tok] │
│ [chip ⚠ revisá antes de enviar] [chip ✕ error]      │
├──────────────────────────────────────────────────────┤
│ ▼ vista previa de extracción (expandible)            │
│   "Esto es exactamente lo que recibirá el agente"    │
│   inventario · esquema · tabla MD · marcadores […]   │
├──────────────────────────────────────────────────────┤
│ ⚠ advertencia N2: posibles datos personales          │
│   ☐ Confirmo que son datos de prueba   [Cancelar]    │
├──────────────────────────────────────────────────────┤
│ [📎] textarea                              [enviar]  │
└──────────────────────────────────────────────────────┘
```

Los chips viven **arriba del textarea**, dentro del borde del composer; envuelven a máx. 2 líneas y «+N más».

### Componentes usados
`.chip` (+ `.is-loading`, `.is-error`) · `.tag--warn` («truncado», «revisá») · `.error-card` / `.error-card--warn` (N3 bloqueado, N2 advertencia) · `.checkbox` + `.check-row` (confirmación N2 auditada) · panel de vista previa (panel local `--flush` con head/body mono) · popover de límites del clip · `.btn` enviar.

### Datos que muestra (campos exactos)
- **Límites por agente** (popover del clip + texto al arrastrar): `agent.attachments.accepted_extensions[]`, `max_files_per_message` (5), `max_size_by_type` (matriz ANEXO §9).
- **Chip por archivo:** ícono por tipo · `original_name` (ellipsis) · meta según estado:
  - `subiendo`: `Subiendo… 45%` (progreso real).
  - `extracting`: `Procesando contenido…` / OCR: `Leyendo texto de las páginas escaneadas… (puede tardar)`.
  - `ready`: resumen de extracción legible — hoja de cálculo: `el agente verá: tabla 120 filas × 8 col` · PDF: `el agente verá: texto de 34 páginas` · DOCX: `el agente verá: documento con 12 secciones` + costo (`≈3,1k tok` | `usa 34% del espacio`).
  - `ready+truncado`: tag warn `truncado` + `incluye el 62% del archivo`.
  - `blocked` (N3): `Bloqueado — contiene credenciales`.
  - `error`: `No se pudo procesar` + tooltip con causa específica (tipo no soportado, tamaño, falsificado, dañado — textos exactos en ANEXO §10).
- **Vista previa de extracción** («Ver lo que verá el agente»): título «Esto es exactamente lo que recibirá el agente» · cuerpo mono con la `inserted_text` real (inventario de hojas, esquema, tabla, marcadores `[… N filas omitidas …]`) · pie permanente «Contenido extraído automáticamente — puede diferir del documento original.» · si hay tablas PDF: aviso de pérdida de estructura.
- **Advertencia N2:** qué se detectó y dónde («2 emails, 1 número de carnet — fila 14 de “Personal”») + checkbox «Confirmo que son datos de prueba» (auditado) + «Cancelar» (quita el adjunto).
- **Bloqueo N3:** qué y dónde («“Password=” en la línea 23») — sin checkbox: no se puede enviar hasta subir un archivo limpio.

### Estados
- **Carga:** chip `is-loading` con % real (subida) o spinner (extracción). El envío queda deshabilitado mientras algún chip no esté `ready` (tooltip con el motivo).
- **Vacío:** composer sin chips = vista 05; el clip siempre visible.
- **Error:** chip `is-error` persistente hasta que el usuario lo quite; nunca desaparece solo (anti-patrón Copilot, ANEXO P7).
- **Éxito:** todos los chips `ready` → enviar habilitado; al enviar, los chips se congelan dentro del mensaje del usuario.
- **Degradado:** extracción con advertencia (truncado, OCR `[OCR]`, instrucción embebida detectada) = enviable pero marcado; la advertencia viaja como flag a la traza.

### Interacciones y casos borde
- **Vías de entrada:** botón clip · drag&drop sobre el chat (overlay «Soltá los archivos acá») · pegar desde portapapeles (texto largo >2.000 caracteres ofrece convertirse en adjunto `.txt`).
- **Quitar chip:** ✕ con `aria-label` con nombre del archivo; pide confirmación solo si la extracción ya costó OCR.
- **Duplicado (mismo sha256):** se reutiliza extracción al instante (chip pasa directo a `ready`).
- **6.º archivo:** rechazo inmediato con texto «Máximo 5 archivos por mensaje…».
- **Excede presupuesto del mensaje (24k tok):** el último chip queda `error` con «Este adjunto excede el espacio disponible del mensaje»; sugerencia de enviar en dos mensajes.
- **Imagen (V1):** rechazo accionable: «Este agente todavía no puede ver imágenes…» (ANEXO §10).
- **PDF escaneado:** oferta OCR opt-in en el chip (dos botones: «Intentar OCR» / «Cancelar»); resultado siempre con vista previa antes de poder enviar.
- **N2 sin confirmar:** enviar deshabilitado; el motivo al lado del botón.
- **Editar mensaje con adjuntos (rama):** la rama nueva **reutiliza** `attachment_id` + `inserted_text` (byte-idéntica, ANEXO §7.4) — los chips no se re-procesan.

### Diferencias por rol
- Funcional: costo como «% del espacio»; sin conteo de tokens; mismos estados y vista previa.
- Técnico/Admin: tokens explícitos en chip y vista previa (`≈3,1k tok · 62% del archivo`).
- Admin: además ve `scan_result` (flags N2/N3/inyección) en telemetría — fuera de esta vista.

### Móvil
✅ Chips envuelven (máx. 2 líneas + «+N más»); vista previa = bottom-sheet a pantalla completa; drag&drop no aplica (file picker nativo); objetivo del ✕ ≥44 px.

### Notas i18n
- Textos canónicos de estados/errores en ANEXO §10 — son la fuente; claves `attachments.state.*`, `attachments.error.*`.
- No traducir extensiones ni patrones (`Password=`); sí los resúmenes («tabla {rows} filas × {cols} col» con plurales ICU).
- PT-BR: «Anexar arquivo» más largo que «Adjuntar» — el popover de límites no debe asumir ancho.

---

## 4. Vista 08 — Escalación a Pro

**Mockup:** [`mockups/08-escalacion.html`](../mockups/08-escalacion.html)

### Propósito
Cuando el modelo Flash emite `<<<NEEDS_PRO>>>`, ofrecer la escalación **manual, de un clic, jamás automática** (ADR-0006). La tarjeta explica costo (~3×) y consecuencia (se abre una conversación nueva — stickiness de modelo) y deja elegir.

### Quién la ve (roles y capacidades)
- **Todos los roles** ven la tarjeta si el agente tiene escalación habilitada (configurable por agente).
- **Admin** ve además la **estimación de costo** del turno en Pro.
- **Agente con escalación deshabilitada:** la tarjeta **no aparece nunca** — el marcador se suprime del stream y el agente continúa con su mejor respuesta Flash. No hay tarjeta "deshabilitada": lo que no está disponible no se muestra (DS §9.7). El mockup lo documenta con una nota, no con UI.

### Layout

```
│ [🤖] …respuesta parcial del agente…                 │
│ ┌──────────────────────────────────────────────┐    │
│ │ ⚡ Este caso amerita el modelo Pro            │    │
│ │ Tu consulta cruza varias localizaciones y     │    │
│ │ amerita el modelo avanzado (~3× costo).       │    │
│ │ Se abre una conversación nueva con el         │    │
│ │ contexto de esta.                             │    │
│ │ [deepseek-v4-pro]  ← tag mono                 │    │
│ │ (Admin: estimado USD 0,018/turno vs 0,006)    │    │
│ │ [Escalar a Pro]  [Seguir con Flash]           │    │
│ └──────────────────────────────────────────────┘    │
```

La tarjeta entra como **contenido del stream** (en el flujo, tras la respuesta parcial), no como modal: no roba foco (DS §8.15).

### Componentes usados
`.escalate-card` (ícono `zap`, `--accent-alt`) · `.btn--primary` («Escalar a Pro») · `.btn--ghost` («Seguir con Flash») · `.tag--outline` mono (`deepseek-v4-pro`) · nota-enlace post-escalación (con ícono rama) · `.error-card--warn` embebida (variante bloqueada por cuota) · `.btn--loading`.

### Datos que muestra (campos exactos)
- `escalation.reason` (1-2 líneas generadas por el agente antes del marcador — por qué amerita Pro).
- `target_model_profile` (`deepseek-v4-pro`) y multiplicador aproximado («~3× costo») — el multiplicador viene de config, no hardcodeado.
- **Admin:** `estimated_cost_per_turn_pro` vs `current_cost_per_turn` (`USD 0,018 vs USD 0,006`, mono).
- Consecuencia explícita: «se abre una conversación nueva» (la nueva sesión hereda un resumen del contexto, no el historial literal — el prefijo Pro nace limpio y cacheable).

### Estados
- **Reposo:** tarjeta con ambas acciones.
- **Loading:** «Escalar a Pro» en `.btn--loading` mientras se crea la rama/sesión Pro.
- **Escalada:** la tarjeta se reemplaza por nota-enlace «Continuaste esta consulta en Pro — abrir conversación» (la tarjeta no puede re-usarse: idempotencia).
- **Descartada («Seguir con Flash»):** la tarjeta colapsa a una línea atenuada «Decidiste seguir con Flash» y el agente continúa; re-escalable solo si el agente vuelve a emitir el marcador.
- **Bloqueada por cuota:** botón primario deshabilitado + motivo inline («Escalar a Pro excede tu cuota mensual») + «Solicitar liberación».
- **Deshabilitada por agente:** **no se renderiza** (ver arriba).

### Interacciones y casos borde
- Un clic en «Escalar a Pro» = crear sesión nueva con perfil Pro y navegar a ella; la sesión original queda intacta con la nota-enlace (navegable en ambos sentidos).
- La tarjeta **no expira** dentro de la sesión, pero queda inerte si la conversación siguió 3+ turnos (estado descartado implícito con línea atenuada).
- Doble clic / doble pestaña: idempotente — la segunda activación navega a la rama ya creada.
- El marcador dentro de un **adjunto** no dispara la tarjeta (ANEXO §4.3 — flag de inyección).
- Cuota evaluada **antes** de crear la sesión Pro (ADR-0007); si bloquea, variante bloqueada.

### Diferencias por rol
- Funcional/Técnico: tarjeta sin estimación de costo (Funcional ni siquiera ve «~3×»? — **sí lo ve**: el multiplicador es lenguaje de consecuencia, no telemetría; lo que no ve son montos USD).
- Admin: + estimación USD por turno.
- Técnico: + tag del perfil destino visible (también lo ve Funcional: el nombre del modelo en esta tarjeta es informativo y aparece 1 vez — decisión deliberada de transparencia, coherente con la etiqueta «modelo alterno»).

### Móvil
✅ Botones apilados a ancho completo, primario abajo (zona del pulgar).

### Notas i18n
- Claves `escalation.title`, `escalation.body`, `escalation.cta`, `escalation.dismiss`, `escalation.done_link`, `escalation.quota_blocked`.
- «Escalar a Pro» en PT-BR («Escalar para o Pro») +20% — botón flexible.
- No traducir nombres de perfil. El multiplicador «~3×» se formatea por locale (×/vezes).

---

## 5. Vista 09 — Edición y ramas

**Mockup:** [`mockups/09-branching.html`](../mockups/09-branching.html)

### Propósito
Materializar **branch-never-rewrite**: editar un mensaje crea una rama nueva; las versiones coexisten y se navegan con «versión 1/2». El usuario nunca pierde nada y entiende el costo de ramificar lejos.

### Quién la ve (roles y capacidades)
Todos los roles igual. Técnico/Admin ven además la telemetría de los turnos re-procesados (cada rama paga su costo). Solo el **autor** del mensaje puede editarlo.

### Layout

```
│            ┌────────────────────────────┐ [✎ Editar] │ ← hover/focus
│            │ ¿Cómo configuro MV_AGENTE? │            │
│            └────────────────────────────┘            │
│  EDITANDO:                                           │
│            ┌────────────────────────────┐            │
│            │ textarea con el texto      │            │
│            │ ⚠ crear una rama acá       │            │
│            │   reprocesa 6 mensajes     │            │
│            │ [Cancelar] [Crear rama]    │            │
│            └────────────────────────────┘            │
│  DESPUÉS:                                            │
│            ‹ 2/2 › ┌──────────────────┐              │
│                    │ texto editado    │              │
│ [🤖] respuesta de la rama 2 (re-renderizada, fade)   │
```

El selector `.branch-sel` se ancla **junto al mensaje ramificado** (debajo, alineado al borde de la burbuja).

### Componentes usados
`.branch-sel` (‹ n/m ›) · botón-ícono «Editar» (lápiz, aparece en hover **y** focus del mensaje propio) · textarea de edición inline (mismo `.textarea`) · aviso de re-proceso (caption `--warn` con ícono) · `.btn--secondary` Cancelar / `.btn--primary` «Crear rama» · tag «modelo alterno» (si una rama corre en otro modelo) · fade de re-render (`--dur-2`).

### Datos que muestra (campos exactos)
- Por mensaje de usuario con versiones: `versions.current` / `versions.total` («2/2»), flechas ‹ › (disabled en extremos).
- En edición: `reprocess_count` — N mensajes posteriores al punto de edición («crear una rama acá reprocesa 6 mensajes»). Aparece solo si N ≥ 3 (editar el último mensaje no lo necesita).
- Las respuestas regeneradas usan el mismo selector en el turno del agente («respuesta 1/2»).
- El árbol completo (sesión → ramas) es navegable también desde el historial (vista 12: una sesión con ramas muestra contador de ramas).

### Estados
- **Reposo:** mensajes sin controles visibles; «Editar» aparece en hover/focus (en móvil: menú contextual del mensaje).
- **Editando:** burbuja → textarea con el texto original precargado; Esc cancela; el resto del hilo se atenúa (`opacity .55`) para señalar el punto de corte.
- **Creando rama (loading):** «Crear rama» en loading; los mensajes posteriores se atenúan.
- **Rama nueva activa:** selector «2/2»; los mensajes posteriores re-renderizados con fade; la versión 1 intacta a un ‹ de distancia.
- **Error al crear rama:** error-card inline; el texto editado **no se pierde** (el textarea persiste).
- **Vacío/carga:** no aplica estados propios (hereda de la vista 05).

### Interacciones y casos borde
- **Cambiar de versión** re-renderiza todo lo posterior al punto de ramificación (fade `--dur-2`); el scroll se mantiene anclado al mensaje ramificado.
- **Ramas anidadas:** una rama puede ramificarse a su vez; cada punto tiene su propio selector (el breadcrumb del árbol completo se difiere a una vista de árbol futura; v1 = selectores locales).
- **Editar mensaje con adjuntos:** los adjuntos se conservan referenciados (no se re-suben ni re-procesan, ANEXO §7.4); se pueden quitar pero no agregar nuevos retroactivamente (un adjunto nuevo = mensaje nuevo).
- **Edición concurrente (dos pestañas):** la segunda creación de rama es válida — son dos ramas hermanas (3/3).
- **Stickiness:** las ramas heredan el `model_profile` de la sesión; si una rama vive en otro modelo (post-fallback), lleva tag «modelo alterno» permanente junto al selector.
- **Cuota:** crear rama re-procesa mensajes = costo; la cuota se evalúa antes (si bloquea → ErrorCard QUOTA en lugar de la rama).
- **Compaction:** si la sesión ya compactó (80%), el aviso de re-proceso cuenta desde el resumen, no desde el origen.

### Diferencias por rol
Funcional ve el aviso de re-proceso sin costos («reprocesa 6 mensajes»); Técnico/Admin ven además estimación («≈ USD 0,01»). El resto idéntico.

### Móvil
✅ «Editar» vía long-press/menú del mensaje (hover no existe); flechas del selector con objetivo ≥44 px (DS §8.20); textarea de edición a pantalla del composer.

### Notas i18n
- `branch.version_label` con ICU («versión {n} de {m}») para `aria-label`; visual «n/m» no se traduce.
- `branch.reprocess_warning`: plural ICU («reprocesa {n, plural, one {# mensaje} other {# mensajes}}»).
- «Crear rama» es terminología fija del glosario (DS §4.2); PT-BR «Criar ramificação» +60% — el botón debe crecer.

---

## 6. Vista 10 — Estados de error

**Mockup:** [`mockups/10-errores.html`](../mockups/10-errores.html)

### Propósito
Catálogo operativo de los 4 errores accionables del chat + el degradado de telemetría. Cada tarjeta cumple la anatomía obligatoria **qué pasó / por qué / qué hacer** (DS §8.16, §9.6). Los errores aparecen **dentro del flujo de mensajes**, en el lugar de la respuesta fallida.

### Quién la ve (roles y capacidades)
Todos ven los 4 errores; cambia la **redacción del porqué** y la visibilidad del código: Técnico/Admin ven el código mono arriba (`VPN_OFFLINE`), Funcional lo ve en segundo plano («código para soporte: VPN_OFFLINE») y sin jerga. El degradado Langfuse es **solo Admin**.

### Layout

```
│ ┌─ error-card ──────────────────────────────┐ │
│ │ ⛔ CODIGO_MONO                             │ │
│ │ Qué pasó (título humano)                  │ │
│ │ Por qué (1 línea honesta, --ink-dim)      │ │
│ │ [Acción primaria] [Acción secundaria]     │ │
│ └───────────────────────────────────────────┘ │
```

### Componentes usados
`.error-card` (danger) · `.error-card--warn` (degradado) · `.btn--secondary`/`--ghost` (acciones) · `.btn--loading` (reintentando) · `.tag--money` («solicitud enviada») · `.live-dot--danger/--warn` (estado del bridge) · countdown mono (micro-demo JS trivial).

### Datos que muestra (campos exactos — catálogo)

| Código | Qué pasó | Por qué (Técnico) | Qué hacer |
|---|---|---|---|
| `QUOTA` | «Alcanzaste tu cuota mensual» | «Tu límite de uso ({used}/{limit}) se alcanzó el {fecha}» | **Solicitar liberación** (primaria) · Ver consumo |
| `VPN_OFFLINE` | «Sin conexión al ambiente del cliente» | «No hay túnel activo hacia {cliente}/{ambiente}» | Pasos numerados: 1. abrí el cliente VPN 2. conectá al perfil {perfil} 3. **Reintentar** · Guía de VPN |
| `BRIDGE_OFFLINE` | «El conector local no responde» | «Último latido del bridge: {hace n min}» + live-dot | **Reintentar** · Estado del bridge |
| `GATEWAY_OFFLINE` | «El servicio de IA no está disponible» | «El proveedor no responde; reintento automático» | countdown «reintentando en {n} s» + **Reintentar ahora** |

- **QUOTA estado 2:** tras solicitar, botón → deshabilitado + tag verde «solicitud enviada» + «te avisamos cuando un admin la resuelva».
- **Degradado Langfuse (solo Admin):** banner `--warn` persistente sobre el chat: «Langfuse caído: el chat funciona, telemetría pausada» + «los costos se estiman localmente y se reconcilian al volver».
- Redacción Funcional del porqué: QUOTA «Alcanzaste tu límite de uso de este mes» · VPN «No hay conexión con el sistema del cliente» · BRIDGE «El conector de tu equipo no responde» · GATEWAY «El asistente no está disponible en este momento». Código al pie: «código para soporte: X» (copiable).

### Estados
- **Estática:** tarjeta recién aparecida (`role="alert"`).
- **Reintentando:** botón en loading; la tarjeta no se duplica (un solo reintento en vuelo).
- **Resuelta:** la tarjeta se retira con fade y el turno continúa (la respuesta entra debajo).
- **QUOTA → solicitud enviada** (estado intermedio persistente).
- **GATEWAY:** countdown decreciente; al llegar a 0 reintenta solo; backoff visible (5→15→60 s).
- **Degradado:** banner warn arriba; no bloquea nada.

### Interacciones y casos borde
- El **mensaje del usuario nunca se pierde**: queda en el hilo; «Reintentar» re-envía el mismo contenido (mismo `message_id` lógico, sin duplicar).
- `QUOTA` además **deshabilita el composer** con el motivo inline (es bloqueo, no solo error de turno).
- «Ver consumo»: Funcional → su barra de cuota personal; Admin → consola de cuotas.
- «Estado del bridge» (Técnico/Admin): popover con hostname, último heartbeat, versión de tat-mcp.
- Dos errores simultáneos (VPN + cuota 80%): el bloqueante gana la posición de respuesta; los avisos warn van como banner.
- El código de error siempre **seleccionable/copiable** (botón copiar al lado).
- Offline del navegador ≠ GATEWAY_OFFLINE: detección local («Sin conexión a internet») sin código de plataforma.

### Diferencias por rol
- Código visible arriba (Técnico/Admin) vs al pie (Funcional).
- Porqué técnico vs porqué simple (tabla arriba).
- «Estado del bridge» con detalle solo Técnico/Admin; Funcional ve «Avisale a tu administrador» como acción alternativa.
- Banner Langfuse: **solo Admin** (Funcional/Técnico ni se enteran — el chat les funciona normal).

### Móvil
✅ Tarjetas a ancho completo; botones apilados, primario abajo; los pasos de VPN como lista numerada táctil.

### Notas i18n
- Códigos **jamás** se traducen (`VPN_OFFLINE`). Claves: `errors.quota.title/why/why_funcional/...` por código × rol.
- Countdown con ICU («reintentando en {n, plural, one {# segundo} other {# segundos}}»).
- Pasos de VPN son contenido de instancia (cada consultora documenta su perfil VPN) — string configurable, no hardcodeado.

---

## 7. Vista 11 — Citas y evidencia (DocAgent)

**Mockup:** [`mockups/11-citas.html`](../mockups/11-citas.html)

### Propósito
La promesa central de DocAgent: **toda afirmación lleva evidencia o no se afirma**. Citas numeradas inline, panel de fuentes verificable y el estado de abstención honesta cuando no hay evidencia suficiente (P5).

### Quién la ve (roles y capacidades)
Todos los roles idéntico — la evidencia no es telemetría, es parte de la respuesta. Técnico/Admin ven además los metadatos de turno habituales (§0.3). El nivel de confianza lo ven todos (es señal de calidad, no jerga).

### Layout

```
┌─────────────────────────────────┬──────────────────────┐
│ [🤖] El parámetro MV_PAISLOC    │ FUENTES              │
│ define la localización [1].     │ ┌──────────────────┐ │
│ Para Bolivia debe valer "BOL"   │ │[1] TDN · MATA010 │ │
│ [1][2]. El CST recomienda…[3]   │ │ §Parámetros …    │ │
│                                 │ │ 14/03/2026       │ │
│ (desktop: panel lateral 300px   │ │ [VIGENTE][ALTA]  │ │
│  sticky · móvil: panel inferior │ │ Abrir documento ↗│ │
│  colapsable bajo la respuesta)  │ └──────────────────┘ │
└─────────────────────────────────┴──────────────────────┘

ABSTENCIÓN:
│ [🤖] ┌─ empty-state ──────────────────────────┐
│      │ No encontré evidencia suficiente para  │
│      │ responder con seguridad.               │
│      │ Qué busqué: "MV_XYZ", "parámetro XYZ   │
│      │ localización BOL" en TDN y CST         │
│      │ Sugerencias: [reformular] [acotar      │
│      │ módulo] [consultar a CST]              │
│      └────────────────────────────────────────┘
```

### Componentes usados
Marcas de cita inline `[1]` (enlace-superíndice, `--info`, objetivo ≥24 px) · `.cite` (bloque de fuente con borde `--info`) · `.tag--money` `VIGENTE` / `.tag--warn` `DESACTUALIZADO` / `.tag--warn` «fuente no disponible» · tags de confianza (`ALTA` `--money` · `MEDIA` `--warn` · `BAJA` `--danger` — siempre con palabra) · enlace «Abrir documento» con ícono externo · `.empty-state` (abstención) · botones-sugerencia (como las sugerencias de inicio).

### Datos que muestra (campos exactos)
- **Inline:** `citation.index` ([1], [2]…) en la oración exacta que sustenta; click → resalta la fuente en el panel (scroll + flash `--accent-soft`).
- **Por fuente:** `source.index` · `source.repo` (`TDN` | `CST`) · `source.title` («MATA010 — Parámetros de localización») · `source.section` («§ Parámetros de localización Bolivia») · `source.doc_date` (`14/03/2026` — fecha del documento, no del acceso) · `source.freshness` (`VIGENTE` si ≤18 meses y sin versión superior detectada; `DESACTUALIZADO` con motivo en tooltip: «existe una versión más nueva del documento» / «documento de más de 18 meses») · `source.confidence` (ALTA/MEDIA/BAJA — score de recuperación bucketizado) · `source.url` («Abrir documento», nueva pestaña) · `source.quote` (fragmento citado, cursiva).
- **Abstención:** mensaje fijo («No encontré evidencia suficiente en TDN/CST para responder esto con confianza») · `searched_queries[]` (las consultas reales ejecutadas) · `searched_repos[]` · sugerencias accionables: reformular (precarga el composer) · acotar módulo · «consultar a CST» (enlace a la guía interna).

### Estados
- **Éxito con citas:** respuesta + panel; cada afirmación factual lleva al menos una marca.
- **Fuente inaccesible:** la cita se conserva con tag warn «fuente no disponible» (el enlace puede estar caído; la evidencia textual sigue).
- **Fuente desactualizada:** tag `DESACTUALIZADO` — la respuesta lo advierte también en texto («según documentación de 2023…»).
- **Abstención:** empty-state — **jamás** texto inventado sin marca. Es un estado de éxito del sistema (el agente cumplió su regla), no un error.
- **Carga:** las fuentes llegan con el stream (las marcas inline aparecen al citarse; el panel se va poblando).
- **Degradado:** si el repositorio de búsqueda no respondió, la respuesta lo declara y se comporta como abstención parcial.

### Interacciones y casos borde
- Click en `[n]` ↔ click en fuente: navegación bidireccional con resaltado.
- Panel lateral **sticky** en desktop (sigue el scroll de la respuesta); colapsable; recuerda su estado por usuario.
- Respuesta con 8+ fuentes: panel con scroll propio; las marcas inline nunca se renumeran entre versiones (regenerar = numeración nueva en la versión nueva).
- Copiar la respuesta copia el markdown **con** las referencias al pie (formato `[1]: TDN MATA010 §… (14/03/2026) — url`).
- Una afirmación sin cita posible → el agente la reformula como hipótesis explícita («no encontré confirmación de esto en la documentación») — regla de prompt, la UI no la maquilla.
- Mezcla de frescuras: el tag va por fuente; si la fuente principal está desactualizada, advertencia en cabecera del panel.

### Diferencias por rol
Ninguna en la evidencia. Técnico/Admin suman su fila de telemetría de turno (§0.3); Admin puede saltar de la traza a los documentos recuperados (en consola, fuera de esta vista).

### Móvil
✅ El panel lateral pasa a **sección inferior colapsable** («Fuentes (3)») bajo la respuesta; las marcas `[n]` hacen scroll al panel expandido; objetivos táctiles ≥44 px.

### Notas i18n
- `VIGENTE/DESACTUALIZADO` se traducen (no son códigos); `TDN`/`CST` no.
- El texto de abstención es clave i18n fija (`docagent.abstention.title/body`) — el agente no lo redacta libre (consistencia).
- Fechas por `Intl` es-BO; los títulos de documentos TDN llegan en su idioma original (frecuentemente PT) y **no se traducen** — marcar `lang="pt"` en el atributo del elemento.

---

## 8. Vista 12 — Historial de sesiones

**Mockup:** [`mockups/12-historial.html`](../mockups/12-historial.html)

### Propósito
Encontrar y retomar conversaciones propias: lista de sesiones con título automático, agente, actividad y acciones de retomar/archivar. Para Admin agrega el costo por sesión (su lente económica de siempre).

### Quién la ve (roles y capacidades)
- Todos los roles: **sus propias sesiones** (privacidad por defecto; la visibilidad cruzada es configuración de instancia fuera de esta vista).
- Admin: columna de costo + total del período. (La vista de sesiones de *otros* usuarios vive en la consola admin, no aquí.)

### Layout

```
┌────────────────────────────────────────────────────────┐
│ Historial                              [Nueva consulta] │
│ [🔍 Buscar en tus conversaciones…] [Agente ▾]           │
│ ┌ tabs: Activas (12) · Archivadas (3) ┐                 │
├────────────────────────────────────────────────────────┤
│ [🤖] Parametrización MV_PAISLOC Bolivia    hace 2 h     │
│ DocAgent · 14 mensajes · ⑂2     (USD 0,021*) [↻][🗄]   │
│ ────────────────────────────────────────────────────── │
│ [🤖] Checklist contable Comercial Andina   ayer        │
│ ValidationAgent · 32 mensajes   (USD 0,084*) [↻][🗄]   │
└────────────────────────────────────────────────────────┘
                                          * solo Admin
```

Lista (no tabla) a máx. 760 px: cada fila es un enlace completo a la sesión; las acciones secundarias (retomar, archivar) a la derecha.

### Componentes usados
`.input` con ícono búsqueda · `.select` (filtro por agente) · `.tabs` (Activas/Archivadas con contador) · filas-card (panel local, hover `--line-strong`) · `.tag--outline` (agente) · ícono rama + contador (`⑂ 2` si la sesión tiene ramas) · `.empty-state` (2 variantes) · `.toast--ok` (archivada, con «Deshacer») · skeleton de filas.

### Datos que muestra (campos exactos)
- Por sesión: `agent.icon` + `agent.display_name` · `session.auto_title` (generado del primer intercambio; editable con lápiz) · `last_activity` (relativo <24 h, después `dd/mm/aaaa`; tooltip absoluto) · `message_count` (`14 mensajes`) · `branch_count` (si >1: `⑂ 2 ramas`) · tag «modelo alterno» si la sesión vive en fallback · **Admin:** `session.cost_usd` (`USD 0,021`, mono verde) y total del período sobre la lista («Este mes: USD 1,84»).
- Búsqueda: por título y contenido de mensajes (server-side); el término se resalta en resultados.
- Orden: última actividad desc (fijo en v1).

### Estados
- **Carga:** 4-5 filas skeleton.
- **Vacío (primera vez):** empty-state «Todavía no tenés conversaciones. Elegí un agente del catálogo para empezar.» + CTA «Ir al catálogo».
- **Vacío (sin resultados):** «Sin resultados para “{q}”» + «Limpiar búsqueda».
- **Vacío (archivadas):** «No archivaste ninguna conversación.»
- **Error:** error-card en lugar de la lista («No pudimos cargar tu historial» + Reintentar).
- **Éxito:** lista paginada por scroll (ventanas de 25).

### Interacciones y casos borde
- **Click en fila / Retomar:** abre la sesión en su última rama activa, scroll al final.
- **Archivar:** mueve a Archivadas (no borra; append-only también aquí) + toast con «Deshacer» (8 s). Desarchivar desde la tab Archivadas.
- **No hay borrado** de sesiones en v1 (auditabilidad); si llega, será acción admin con confirmación destructiva.
- Sesión **bloqueada por cuota**: retomar abre con el ErrorCard QUOTA visible.
- Sesión cuyo **agente fue desactivado**: fila con tag warn «agente inactivo»; se puede leer pero no continuar (composer deshabilitado con motivo).
- Título auto editado por el usuario nunca se regenera.
- Búsqueda con 0 caracteres = lista completa; debounce 300 ms.
- Las **ramas no aparecen como filas separadas**: una sesión = una fila; el contador ⑂ indica el árbol y se navega adentro.

### Diferencias por rol
- Admin: columna costo + total del período. Resto idéntico.
- Técnico: sin costo (el costo de sesión propio lo ve en el taxímetro al entrar — decisión: la lista se mantiene limpia; ver DS §8.12 que limita el taxímetro a la sesión activa). *Nota de diseño: si en validación los Técnicos piden costo en la lista, es un agregado compatible.*

### Móvil
✅ Filas a ancho completo, acciones en menú ⋯ (long-press); búsqueda colapsada a ícono que expande; tabs scrolleables.

### Notas i18n
- Claves `history.title`, `history.search.placeholder`, `history.tabs.active/archived`, `history.empty.*`, `history.actions.resume/archive/undo`.
- Plurales ICU para mensajes/ramas. Fechas por `Intl`.
- PT-BR: «Arquivar/Arquivadas» similar; «Retomar» idéntico — sin riesgo de desborde.

---

## Apéndice — Trazabilidad de decisiones

| Decisión de esta spec | Fuente |
|---|---|
| Regenerar = versión nueva con selector (no sobrescribe) | CLAUDE.md regla 3 (append-only), DS §8.20 |
| Marcador NEEDS_PRO interceptado, jamás visible | ADR-0006, ANEXO §4.3 |
| «modelo alterno» visible para todos; nombre del modelo solo T/A (salvo tarjeta de escalación) | Contexto de producto (transparencia), DS §1-P2 |
| «ver traza» solo Admin (Técnico no ve telemetría) | Modelo de roles (memoria), DS §8.12-13 |
| Chips de adjunto: tokens (T/A) vs % de espacio (Funcional) | ANEXO §3.4 |
| Errores con doble redacción por rol y código copiable | DS §9.6 |
| Abstención = empty-state de éxito, texto fijo i18n | DS §8.18, P5 |
| Archivar sin borrar; sin borrado en v1 | Append-only + auditabilidad |
