/**
 * Formatos es-BO (tarea 6.3, d10-design-system-shell).
 *
 * design/DESIGN-SYSTEM.md §9.8 pide que fecha/hora/moneda/número se
 * formateen vía `Intl.NumberFormat`/`Intl.DateTimeFormat` con el LOCALE DE
 * INSTANCIA (es-BO por defecto) — un concepto distinto del locale de
 * next-intl (`i18n/request.ts`, fijo en `"es"` genérico: el idioma de los
 * TEXTOS de catálogo, preparado para pt-BR en la Etapa P, ver
 * `messages/es.json`). El formato de fecha/número es responsabilidad de la
 * INSTANCIA (Bolivia hoy, otro país mañana), no del idioma de la UI, así
 * que este módulo usa el objeto `Intl` nativo del runtime con el locale
 * `"es-BO"` hardcodeado a propósito — decisión documentada del escenario
 * "Formato de fecha en es-BO" (specs/i18n-foundation/spec.md) — en vez de
 * derivarlo del locale que resuelve `next-intl`/`useFormatter()`. Cuando
 * una instancia futura configure otro país (Etapa P), este locale pasa a
 * ser configuración de instancia real, no next-intl.
 *
 * Los helpers de abajo cubren las filas de la tabla §9.8 que el producto
 * consume hoy (fecha, fecha-hora, costo LLM, monto agregado, porcentaje,
 * tokens abreviados); "relativo" ya tiene consumidor propio
 * (`lib/chat/format-time.ts`, fuera de este módulo). "Duración" llega acá
 * recién con `formatLatencySecondsBO` (d13-chat-conversacion, tareas
 * 4.2/4.3: latencia de turno de la vista 06, `3,2 s`) -- no se agregó
 * especulativamente antes por no tener consumidor real.
 */

const INSTANCE_LOCALE = "es-BO";

/** `dd/mm/aaaa` — fila "Fecha" (ej. `11/06/2026`). */
export function formatDateBO(date: Date): string {
  return new Intl.DateTimeFormat(INSTANCE_LOCALE, {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
  }).format(date);
}

/** `dd/mm/aaaa HH:mm` (24 h) — fila "Fecha-hora" (ej. `11/06/2026 14:32`). */
export function formatDateTimeBO(date: Date): string {
  const time = new Intl.DateTimeFormat(INSTANCE_LOCALE, {
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).format(date);
  return `${formatDateBO(date)} ${time}`;
}

/** `USD` + 4 decimales, coma decimal — fila "Costo LLM" (ej. `USD 0,0042`). */
export function formatLlmCostBO(amountUsd: number): string {
  const number = new Intl.NumberFormat(INSTANCE_LOCALE, {
    minimumFractionDigits: 4,
    maximumFractionDigits: 4,
  }).format(amountUsd);
  return `USD ${number}`;
}

/**
 * `USD` + 2 decimales, separador de miles "." — fila "Montos agregados"
 * (ej. `USD 1.284,50`).
 */
export function formatAggregatedAmountBO(amountUsd: number): string {
  const number = new Intl.NumberFormat(INSTANCE_LOCALE, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(amountUsd);
  return `USD ${number}`;
}

/** Sin espacio antes de "%" — fila "Porcentaje" (ej. `82%`). `ratio` es 0–1. */
export function formatPercentBO(ratio: number): string {
  return new Intl.NumberFormat(INSTANCE_LOCALE, {
    style: "percent",
    maximumFractionDigits: 0,
  }).format(ratio);
}

/**
 * Número abreviado k/M, 1 decimal, SIN unidad (ej. `41,2k`) — pieza
 * compartida por `formatTokensBO` (que le agrega "tok") y los chips de
 * cache `HIT`/`MISS`/`WRITE` de la vista 06 (`HIT · 41,2k`): el chip ya es
 * de tokens por contexto, repetir "tok" ahí sería ruido (d13-chat-conversacion,
 * tareas 4.2/4.3). El CLDR de es-BO agrega un espacio antes de la unidad
 * compacta ("41,2 k"); se quita acá porque el formato del design no lo lleva.
 *
 * DESVÍO documentado: el CLDR de `Intl` para `es` usa mayúscula ("K") para
 * el escalón de millar (1.000-9.999, ej. `1,8 K`) pero minúscula ("k") para
 * el escalón de decena de millar en adelante (10.000+, ej. `41,2 k`) —
 * inconsistencia real de los datos CLDR, no un bug de esta función. El
 * design (`design/DESIGN-SYSTEM.md` §9.8) pide SIEMPRE minúscula
 * (`12,4k tok`), así que se normaliza acá con `toLowerCase()` -- sin efecto
 * sobre los dígitos/coma decimal, que nunca llevan mayúsculas.
 */
export function formatCompactNumberBO(count: number): string {
  const abbreviated = new Intl.NumberFormat(INSTANCE_LOCALE, {
    notation: "compact",
    compactDisplay: "short",
    maximumFractionDigits: 1,
  }).format(count);
  return abbreviated.replace(/\s+/g, "").toLowerCase();
}

/** Abreviado k/M, 1 decimal, con unidad — fila "Tokens" (ej. `12,4k tok`). */
export function formatTokensBO(count: number): string {
  return `${formatCompactNumberBO(count)} tok`;
}

/**
 * Entero agrupado, SIN abreviar ni unidad (ej. `8.200`) — chip de adjunto
 * "listo" para Técnico/Admin (d14-attachments, tarea 8.2,
 * `Chat.attachments.states.readyTechAdmin`: `"Listo · {tokens} tokens"`).
 * A diferencia de `formatTokensBO` (compacto + "tok", fila "Tokens" del
 * taxímetro de turno, DESIGN-SYSTEM.md §9.8), el texto §10 del chip escribe
 * la palabra completa "tokens" como sufijo literal de la plantilla — un
 * número también abreviado ("8,2k tokens") leería inconsistente mezclando
 * abreviación con unidad completa, así que acá se usa el separador de miles
 * de es-BO sin abreviar (ANEXO-ATTACHMENTS.md §10: "Listo · 8.200 tokens").
 */
export function formatTokenCountBO(count: number): string {
  return new Intl.NumberFormat(INSTANCE_LOCALE).format(count);
}

/**
 * Segundos con 1 decimal, coma decimal — latencia de turno de la vista 06
 * (ej. `3,2 s`, a partir de `telemetry.latency_ms` en milisegundos).
 */
export function formatLatencySecondsBO(milliseconds: number): string {
  const number = new Intl.NumberFormat(INSTANCE_LOCALE, {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  }).format(milliseconds / 1000);
  return `${number} s`;
}
