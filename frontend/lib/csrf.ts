/**
 * Helper compartido para el patrón CSRF de doble envío
 * (`resultarai/app/identity/csrf.py`): toda mutación (POST/PUT/PATCH/DELETE)
 * exige el header `X-CSRF-Token` con el mismo valor que la cookie
 * `resultarai_csrf` (no `HttpOnly` a propósito, para que el cliente pueda
 * leerla y reenviarla).
 *
 * Mismo patrón ya usado en `app/(shell)/notificaciones/page.tsx` y
 * `components/shell/notification-panel.tsx`; se extrae acá para no
 * duplicarlo en el código nuevo de chat (`lib/chat/*`,
 * `app/(shell)/chat/*`) — ver `openspec/BACKLOG-DESCUBRIMIENTOS.md` para la
 * nota de unificar también esos dos usos preexistentes.
 */

const CSRF_COOKIE = "resultarai_csrf";
const CSRF_HEADER = "X-CSRF-Token";

/** Lee el token CSRF vigente de la cookie no-HttpOnly. `null` sin sesión o en SSR. */
export function readCsrfToken(): string | null {
  if (typeof document === "undefined") return null;
  const match = document.cookie.split("; ").find((row) => row.startsWith(`${CSRF_COOKIE}=`));
  return match ? match.slice(CSRF_COOKIE.length + 1) : null;
}

/** Headers listos para spread en `fetch(url, { headers: { ...csrfHeaders() } })`. */
export function csrfHeaders(): Record<string, string> {
  const token = readCsrfToken();
  return token ? { [CSRF_HEADER]: token } : {};
}
