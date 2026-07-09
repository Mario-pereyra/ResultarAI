import { NextResponse, type NextRequest } from "next/server";
import { GATEWAY_COOKIE, ROLE_COOKIE, parseGatewayStatus, parseRole } from "./lib/dev-session";

/**
 * Alternancia de rol/gateway por query param, leída en el server (tarea
 * 5.1 y 5.6, d10-design-system-shell).
 *
 * CONTRATO TEMPORAL: `d11-identidad-acceso` reemplaza esto por sesión real
 * (cookie de sesión firmada — docs/06-seguridad-gobernanza.md); hasta
 * entonces, visitar cualquier URL con `?role=funcional|tecnico|admin` fija
 * la cookie `role` que `app/(shell)/layout.tsx` resuelve vía
 * `lib/dev-session.ts` (Decision 6, design.md). `?gateway=ok|degradado|offline`
 * hace lo mismo con la cookie `gateway`, solo para poder verificar el
 * estado `GATEWAY_OFFLINE` (tarea 5.6) sin backend real.
 *
 * Nota Next.js 16: el archivo de middleware se renombró de `middleware.ts`
 * a `proxy.ts` (`export function middleware` -> `export function proxy`);
 * `middleware.ts` sigue funcionando pero está deprecado (ver guía de
 * actualización oficial). Se usa acá el nombre/convención nuevos.
 */

export function proxy(request: NextRequest) {
  const { searchParams } = request.nextUrl;
  const roleParam = searchParams.get("role");
  const gatewayParam = searchParams.get("gateway");

  if (!roleParam && !gatewayParam) {
    return NextResponse.next();
  }

  const response = NextResponse.next();
  const oneYear = 60 * 60 * 24 * 365;

  if (roleParam) {
    response.cookies.set(ROLE_COOKIE, parseRole(roleParam), { path: "/", maxAge: oneYear });
  }
  if (gatewayParam) {
    response.cookies.set(GATEWAY_COOKIE, parseGatewayStatus(gatewayParam), {
      path: "/",
      maxAge: oneYear,
    });
  }

  return response;
}

export const config = {
  matcher: ["/((?!_next/static|_next/image|favicon.ico|api/).*)"],
};
