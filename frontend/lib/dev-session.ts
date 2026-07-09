import { capabilitiesForRole } from "./capabilities";
import type { GatewayStatus, Role, SessionContextValue } from "./session-context";

/**
 * Provider de desarrollo del SessionContext (tarea 5.1, d10-design-system-shell).
 *
 * CONTRATO TEMPORAL — Decision 6 de design.md: esta función (junto con
 * `proxy.ts`, que traduce `?role=`/`?gateway=` a las cookies que lee acá)
 * es lo único que `d11-identidad-acceso` necesita reemplazar por sesión
 * real; ningún componente de `components/shell/*` importa esto
 * directamente, todos reciben `SessionContextValue` ya resuelto vía
 * `<SessionProvider>` en `app/(shell)/layout.tsx`.
 *
 * Los usuarios/aprobaciones mock de abajo calzan 1:1 con las 3 miniaturas
 * de rol de design/mockups/03-shell.html (mismos nombres, iniciales y
 * contadores de aprobaciones que el mockup) para máxima fidelidad visual.
 */

export const ROLE_COOKIE = "role";
export const GATEWAY_COOKIE = "gateway";

const VALID_ROLES: readonly Role[] = ["admin", "tecnico", "funcional"];
const VALID_GATEWAY_STATUSES: readonly GatewayStatus[] = ["ok", "degradado", "offline"];

/** Nombre del usuario mock por rol (design/mockups/03-shell.html). */
const MOCK_USER_NAME: Record<Role, string> = {
  funcional: "lucia",
  tecnico: "dario",
  admin: "marcos",
};

/** Aprobaciones pendientes mock por rol (mismos valores que el mockup). */
const MOCK_PENDING_APPROVALS: Record<Role, number> = {
  funcional: 0,
  tecnico: 1,
  admin: 3,
};

/** Rol por defecto cuando no hay cookie/query param: el de menor privilegio. */
export function parseRole(value: string | undefined): Role {
  return (VALID_ROLES as readonly string[]).includes(value ?? "") ? (value as Role) : "funcional";
}

export function parseGatewayStatus(value: string | undefined): GatewayStatus {
  return (VALID_GATEWAY_STATUSES as readonly string[]).includes(value ?? "")
    ? (value as GatewayStatus)
    : "ok";
}

export function resolveDevSession(
  roleCookieValue: string | undefined,
  gatewayCookieValue: string | undefined,
): SessionContextValue {
  const role = parseRole(roleCookieValue);
  const gatewayStatus = parseGatewayStatus(gatewayCookieValue);

  return {
    user: { name: MOCK_USER_NAME[role], role },
    gateway: { status: gatewayStatus },
    pendingApprovals: MOCK_PENDING_APPROVALS[role],
    capabilities: capabilitiesForRole(role),
  };
}
