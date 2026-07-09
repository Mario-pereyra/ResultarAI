"use client";

import { createContext, useContext, type ReactNode } from "react";
import type { Section } from "./capabilities";

/**
 * SessionContext (tarea 5.1, d10-design-system-shell).
 *
 * CONTRATO TEMPORAL — Decision 6 de
 * openspec/changes/d10-design-system-shell/design.md: esta forma
 * (`{ user, gateway, pendingApprovals, capabilities }`) es la que
 * `d11-identidad-acceso` DEBE preservar cuando reemplace el provider de
 * desarrollo (`lib/dev-session.ts`, resuelto hoy desde cookies mock leídas
 * por `app/(shell)/layout.tsx`) por uno que lea la sesión real. Ningún
 * componente de `components/shell/*` debe cambiar cuando eso pase: solo
 * cambia el origen del `value` que recibe `<SessionProvider>`. Ver también
 * README.md de `frontend/` (sección "SessionContext y capabilities —
 * contrato temporal").
 */

export type Role = "admin" | "tecnico" | "funcional";
export type GatewayStatus = "ok" | "degradado" | "offline";

export type SessionContextValue = {
  user: { name: string; role: Role };
  gateway: { status: GatewayStatus };
  /** Aprobaciones pendientes visibles para el usuario (badge del sidebar). */
  pendingApprovals: number;
  /** Ya resuelto para el rol de `user` — ver `lib/capabilities.ts`. */
  capabilities: Section[];
};

const SessionContext = createContext<SessionContextValue | null>(null);

export function SessionProvider({
  value,
  children,
}: {
  value: SessionContextValue;
  children: ReactNode;
}) {
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): SessionContextValue {
  const value = useContext(SessionContext);
  if (!value) {
    throw new Error(
      "useSession() debe usarse dentro de <SessionProvider> (ver app/(shell)/layout.tsx).",
    );
  }
  return value;
}
