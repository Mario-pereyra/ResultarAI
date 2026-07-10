/**
 * Formato de hora de turno (`design/DESIGN-SYSTEM.md` §9.8: relativo <24 h,
 * con absoluto en tooltip; `dd/mm/aaaa HH:mm` a partir de las 24 h).
 * Implementación mínima propia (sin `Intl.RelativeTimeFormat` para evitar
 * la granularidad "hace 0 minutos" en los primeros segundos): la vista 05
 * solo necesita minutos/horas/fecha, no segundos.
 */

const MINUTE_MS = 60_000;
const HOUR_MS = 60 * MINUTE_MS;
const DAY_MS = 24 * HOUR_MS;

/** Texto corto relativo (`"hace 2 min"`, `"hace 3 h"`, o `dd/mm/aaaa` pasadas 24 h). */
export function formatRelativeTime(isoDate: string, now: Date = new Date()): string {
  const date = new Date(isoDate);
  if (Number.isNaN(date.getTime())) return "";

  const diffMs = now.getTime() - date.getTime();
  if (diffMs < MINUTE_MS) return "hace un momento";
  if (diffMs < HOUR_MS) return `hace ${Math.floor(diffMs / MINUTE_MS)} min`;
  if (diffMs < DAY_MS) return `hace ${Math.floor(diffMs / HOUR_MS)} h`;

  const day = String(date.getDate()).padStart(2, "0");
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const year = date.getFullYear();
  return `${day}/${month}/${year}`;
}

/** Fecha/hora absoluta completa (`dd/mm/aaaa HH:mm`), para el tooltip. */
export function formatAbsoluteTime(isoDate: string): string {
  const date = new Date(isoDate);
  if (Number.isNaN(date.getTime())) return "";

  const day = String(date.getDate()).padStart(2, "0");
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const year = date.getFullYear();
  const hours = String(date.getHours()).padStart(2, "0");
  const minutes = String(date.getMinutes()).padStart(2, "0");
  return `${day}/${month}/${year} ${hours}:${minutes}`;
}
