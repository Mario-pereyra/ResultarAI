"use client";

import { useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { Dropdown } from "@/components/ui/dropdown";
import { RoleBadge } from "@/components/ui/role-badge";
import { useSession } from "@/lib/session-context";
import type { Theme } from "@/lib/theme";
import { BellIcon, HamburgerIcon, MoonIcon, SearchIcon, SunIcon } from "./icons";

/**
 * Topbar (tarea 5.4, d10-design-system-shell).
 *
 * - Buscador visual (`role="search"` + input real, sin backend) con atajo
 *   `Ctrl/⌘+K` que lo enfoca desde cualquier vista del shell (listener
 *   global montado una vez, ya que Topbar vive en el layout persistente).
 * - Switcher de tema: ícono sol/luna en el topbar Y ítem "Tema" en el menú
 *   de usuario (Requirement "Selector de tema personal" /  "Identidad
 *   visible en el header" de specs/app-shell/spec.md piden ambos: el
 *   ASCII/JS de design/mockups/03-shell.html implementa el ícono dedicado,
 *   el texto de la Requirement pide el ítem del dropdown — se implementan
 *   los dos, reusando el mismo `handleToggleTheme`). Escribe la cookie
 *   `theme` vía `app/api/theme/route.ts` y refresca con `router.refresh()`
 *   (Server Components, incluido `app/layout.tsx`, se re-renderizan con el
 *   `data-theme` nuevo — sin recarga completa, sin FOUC).
 * - Campana `.notif-bell`: placeholder visual (backend real en `d12`).
 * - Menú de usuario: `Dropdown` con `triggerContent` (avatar + nombre +
 *   `RoleBadge`) — escenario "Badge de rol visible en el menú de usuario".
 */

export type TopbarLabels = {
  searchLabel: string;
  searchPlaceholder: string;
  searchShortcutHint: string;
  openMenu: string;
  themeToLight: string;
  themeToDark: string;
  notifications: string;
  notificationsEmpty: string;
  /** Ya interpolado server-side con nombre + rol (ver app/(shell)/layout.tsx). */
  userMenuLabel: string;
  myWorkspace: string;
  theme: string;
  logout: string;
  /** Texto visible del rol de la sesión actual (Admin/Técnico/Funcional). */
  roleLabel: string;
};

export type TopbarProps = {
  theme: Theme;
  labels: TopbarLabels;
  onOpenDrawer: () => void;
};

export function Topbar({ theme, labels, onOpenDrawer }: TopbarProps) {
  const { user } = useSession();
  const router = useRouter();
  const searchRef = useRef<HTMLInputElement | null>(null);

  useEffect(() => {
    function handleGlobalKeyDown(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        searchRef.current?.focus();
      }
    }
    document.addEventListener("keydown", handleGlobalKeyDown);
    return () => document.removeEventListener("keydown", handleGlobalKeyDown);
  }, []);

  async function handleToggleTheme() {
    await fetch("/api/theme", { method: "POST" });
    router.refresh();
  }

  return (
    <div className="shell-topbar">
      <button
        type="button"
        className="shell-topbar__icon shell-topbar__hamburger"
        aria-label={labels.openMenu}
        onClick={onOpenDrawer}
      >
        <HamburgerIcon />
      </button>

      <div className="shell-topbar__search" role="search">
        <SearchIcon />
        <input
          ref={searchRef}
          type="search"
          className="shell-topbar__search-input"
          placeholder={labels.searchPlaceholder}
          aria-label={labels.searchLabel}
        />
        <kbd className="shell-topbar__kbd">{labels.searchShortcutHint}</kbd>
      </div>

      <div className="shell-topbar__actions">
        <button
          type="button"
          className="shell-topbar__icon"
          aria-label={theme === "dark" ? labels.themeToLight : labels.themeToDark}
          onClick={handleToggleTheme}
        >
          {theme === "dark" ? <SunIcon /> : <MoonIcon />}
        </button>

        <Dropdown
          triggerLabel={labels.notifications}
          triggerIcon={<BellIcon />}
          triggerClassName="notif-bell"
          align="end"
          items={[
            {
              id: "empty",
              label: labels.notificationsEmpty,
              onSelect: () => {},
              disabled: true,
            },
          ]}
        />

        <Dropdown
          triggerLabel={labels.userMenuLabel}
          align="end"
          triggerContent={
            <span className="shell-topbar__user">
              <span className="shell-topbar__avatar">{initialsFromName(user.name)}</span>
              <span className="shell-topbar__user-name">{user.name}</span>
              <RoleBadge role={user.role} label={labels.roleLabel} />
            </span>
          }
          items={[
            { id: "workspace", label: labels.myWorkspace, onSelect: () => {} },
            { id: "theme", label: labels.theme, onSelect: handleToggleTheme },
            { id: "logout", label: labels.logout, onSelect: () => {}, danger: true },
          ]}
        />
      </div>
    </div>
  );
}

/** "lucia" -> "LU" (mismo criterio que design/mockups/03-shell.html). */
function initialsFromName(name: string): string {
  return name.slice(0, 2).toUpperCase();
}
