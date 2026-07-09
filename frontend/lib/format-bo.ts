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
 * Los 6 helpers de abajo cubren las filas de la tabla §9.8 que el producto
 * consume hoy (fecha, fecha-hora, costo LLM, monto agregado, porcentaje,
 * tokens abreviados); "relativo" y "duración" no tienen consumidor real
 * todavía (taxímetro/HITL llegan en changes posteriores) y se agregan
 * cuando haga falta, no especulativamente.
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
 * Abreviado k/M, 1 decimal — fila "Tokens" (ej. `12,4k tok`). El CLDR de
 * es-BO agrega un espacio antes de la unidad compacta ("12,4 k"); se quita
 * acá porque el formato del design no lo lleva.
 */
export function formatTokensBO(count: number): string {
  const abbreviated = new Intl.NumberFormat(INSTANCE_LOCALE, {
    notation: "compact",
    compactDisplay: "short",
    maximumFractionDigits: 1,
  }).format(count);
  return `${abbreviated.replace(/\s+/g, "")} tok`;
}
