import { NextResponse, type NextRequest } from "next/server";
import { THEME_COOKIE, nextTheme, resolveTheme } from "@/lib/theme";

/**
 * Route handler de alternancia de tema (tarea 5.4, d10-design-system-shell).
 *
 * Decisión: route handler (no Server Action). Motivo: la lógica de
 * escritura de cookie queda testeable directamente en Vitest llamando a
 * `POST()` con un `NextRequest` real — un Server Action, en cambio, depende
 * del contexto async de request de `next/headers` que solo existe dentro
 * del runtime de Next.js (mismo motivo por el que este repo no testea
 * Server Components async directamente, ver README.md § Testing).
 *
 * El switcher del topbar (ícono sol/luna) y el ítem "Tema" del menú de
 * usuario (`components/shell/topbar.tsx`) llaman a este mismo endpoint con
 * `fetch` y después `router.refresh()`: el refresh vuelve a pasar por el
 * Server Component raíz (`app/layout.tsx`), que resuelve `data-theme` desde
 * la cookie ya actualizada — sin flash de tema incorrecto, sin recarga
 * completa de página, sin `useEffect` de theming en el cliente.
 */
export async function POST(request: NextRequest) {
  const current = resolveTheme(request.cookies.get(THEME_COOKIE)?.value);
  const next = nextTheme(current);

  const response = NextResponse.json({ theme: next });
  response.cookies.set(THEME_COOKIE, next, {
    path: "/",
    maxAge: 60 * 60 * 24 * 365,
    sameSite: "lax",
  });
  return response;
}
