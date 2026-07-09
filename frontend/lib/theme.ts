/**
 * Contrato de tema (tarea 3.4, extraído en la tarea 5.4 de
 * d10-design-system-shell).
 *
 * Antes vivía inline en `app/layout.tsx`. Se extrae acá para que
 * `app/api/theme/route.ts` (el route handler que escribe la cookie cuando
 * el usuario alterna el tema, tarea 5.4) y `app/layout.tsx` (que la lee en
 * el Server Component raíz) usen EXACTAMENTE la misma cookie y la misma
 * regla de resolución — nunca reimplementarla en dos lugares.
 */
export const THEME_COOKIE = "theme";
export type Theme = "dark" | "light";

/** Sin cookie -> "dark" (default de instancia). */
export function resolveTheme(value: string | undefined): Theme {
  return value === "light" ? "light" : "dark";
}

export function nextTheme(current: Theme): Theme {
  return current === "light" ? "dark" : "light";
}
