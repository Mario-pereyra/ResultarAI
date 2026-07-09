"use client";

import { useEffect, useState, type ReactNode } from "react";
import { useSession } from "@/lib/session-context";
import type { Theme } from "@/lib/theme";
import { AiBanner } from "./ai-banner";
import { GatewayError, type GatewayErrorLabels } from "./gateway-error";
import { Sidebar, type SidebarLabels } from "./sidebar";
import { SkipLink } from "./skip-link";
import { Topbar, type TopbarLabels } from "./topbar";

/**
 * ShellFrame (tareas 5.3–5.7, d10-design-system-shell).
 *
 * Componente presentacional (no async) que compone el shell completo:
 * skip-link, banner IA, sidebar (+ drawer móvil) y topbar alrededor del
 * slot de contenido. `app/(shell)/layout.tsx` (Server Component async) solo
 * resuelve cookies/sesión/traducciones y renderiza este componente — mismo
 * patrón que `app/home-content.tsx` (README.md § Testing): los Server
 * Components async no se testean directamente con Testing Library, así que
 * toda la lógica testeable vive acá.
 *
 * Dueño del estado de UI del shell (colapso de sidebar, drawer móvil):
 * `Sidebar`/`Topbar` son controlados, no manejan su propio estado.
 */

export const MAIN_CONTENT_ID = "shell-main";

/**
 * 5.3: colapso persistido POR USUARIO. Decisión: localStorage, no cookie.
 * A diferencia del tema (que cambia el color de fondo entero y por eso
 * exige resolución 100% server-side para evitar un flash de color
 * incorrecto — FOUC), el ancho del sidebar es un cambio de layout menor;
 * se acepta un frame de diferencia en la carga siguiente a cambio de no
 * sumar otro route handler + cookie solo para esto (la tarea permite
 * explícitamente "cookie o localStorage"). Ver README.md.
 */
const SIDEBAR_COLLAPSED_KEY = "resultarai:sidebar-collapsed";

export type ShellFrameLabels = {
  skipLink: string;
  banner: { full: string; short: string };
  sidebar: SidebarLabels;
  topbar: TopbarLabels;
  gatewayError: GatewayErrorLabels;
};

export type ShellFrameProps = {
  theme: Theme;
  labels: ShellFrameLabels;
  children: ReactNode;
};

export function ShellFrame({ theme, labels, children }: ShellFrameProps) {
  const session = useSession();
  const [collapsed, setCollapsed] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);

  useEffect(() => {
    // localStorage no existe durante el SSR: leerlo recién acá (post-montaje)
    // es intencional — evita un mismatch de hidratación entre el HTML del
    // servidor (siempre "expandido") y el valor persistido del cliente. Ver
    // README.md "5.3: colapso persistido POR USUARIO" para la decisión.
    const stored = window.localStorage.getItem(SIDEBAR_COLLAPSED_KEY);
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (stored !== null) setCollapsed(stored === "true");
  }, []);

  function toggleCollapse() {
    setCollapsed((previous) => {
      const next = !previous;
      window.localStorage.setItem(SIDEBAR_COLLAPSED_KEY, String(next));
      return next;
    });
  }

  return (
    <div className="shell-frame">
      <SkipLink label={labels.skipLink} targetId={MAIN_CONTENT_ID} />
      <AiBanner textFull={labels.banner.full} textShort={labels.banner.short} />
      <div className="shell-body">
        <Sidebar
          labels={labels.sidebar}
          collapsed={collapsed}
          onToggleCollapse={toggleCollapse}
          drawerOpen={drawerOpen}
          onCloseDrawer={() => setDrawerOpen(false)}
        />
        <div className="shell-main">
          <Topbar theme={theme} labels={labels.topbar} onOpenDrawer={() => setDrawerOpen(true)} />
          <main id={MAIN_CONTENT_ID} className="shell-content" tabIndex={-1}>
            {session.gateway.status === "offline" ? (
              <GatewayError role={session.user.role} labels={labels.gatewayError} />
            ) : null}
            {children}
          </main>
        </div>
      </div>
    </div>
  );
}
