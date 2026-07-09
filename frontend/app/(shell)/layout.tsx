import type { ReactNode } from "react";
import { cookies } from "next/headers";
import { getTranslations } from "next-intl/server";
import { ShellFrame, type ShellFrameLabels } from "@/components/shell/shell-frame";
import type { Section } from "@/lib/capabilities";
import { GATEWAY_COOKIE, ROLE_COOKIE, resolveDevSession } from "@/lib/dev-session";
import { SessionProvider } from "@/lib/session-context";
import { THEME_COOKIE, resolveTheme } from "@/lib/theme";
import "../../styles/shell.css";

/**
 * Layout autenticado del shell (tareas 5.1–5.7, d10-design-system-shell).
 *
 * Server Component async: SOLO resuelve cookies -> sesión mock (tarea 5.1,
 * `lib/dev-session.ts`) y traducciones (`messages/es.json`, namespace
 * `Shell`), y delega todo el render/estado interactivo a
 * `components/shell/shell-frame.tsx` (presentacional, testeado aparte —
 * mismo patrón que `app/(shell)/page.tsx` + `home-content.tsx`, ver
 * README.md § Testing).
 *
 * Toda página dentro de `app/(shell)/*` queda envuelta por este shell
 * persistente (banner IA, sidebar, topbar) — la página raíz (antes en
 * `app/page.tsx`) vive ahora en `app/(shell)/page.tsx`.
 */
export default async function ShellLayout({ children }: { children: ReactNode }) {
  const cookieStore = await cookies();
  const session = resolveDevSession(
    cookieStore.get(ROLE_COOKIE)?.value,
    cookieStore.get(GATEWAY_COOKIE)?.value,
  );
  const theme = resolveTheme(cookieStore.get(THEME_COOKIE)?.value);

  const t = await getTranslations("Shell");
  const roleLabel = t(`topbar.roles.${session.user.role}`);

  const sectionLabels: Record<Section, string> = {
    catalogo: t("sidebar.sections.catalogo"),
    chat: t("sidebar.sections.chat"),
    workflows: t("sidebar.sections.workflows"),
    aprobaciones: t("sidebar.sections.aprobaciones"),
    "mi-espacio": t("sidebar.sections.miEspacio"),
    administracion: t("sidebar.sections.administracion"),
    construccion: t("sidebar.sections.construccion"),
  };

  const labels: ShellFrameLabels = {
    skipLink: t("skipLink"),
    banner: { full: t("banner.full"), short: t("banner.short") },
    sidebar: {
      instanceName: t("sidebar.instanceName"),
      sectionLabels,
      adminKicker: t("sidebar.adminKicker"),
      collapse: t("sidebar.collapse"),
      expand: t("sidebar.expand"),
      navLabel: t("sidebar.navLabel"),
      drawerLabel: t("sidebar.drawerLabel"),
      approvalsAriaLabel: t("sidebar.approvalsAriaLabel", { count: session.pendingApprovals }),
      drawerSearchPlaceholder: t("topbar.searchPlaceholder"),
    },
    topbar: {
      searchLabel: t("topbar.searchLabel"),
      searchPlaceholder: t("topbar.searchPlaceholder"),
      searchShortcutHint: t("topbar.searchShortcutHint"),
      openMenu: t("topbar.openMenu"),
      themeToLight: t("topbar.themeToLight"),
      themeToDark: t("topbar.themeToDark"),
      notifications: t("topbar.notifications"),
      notificationsEmpty: t("topbar.notificationsEmpty"),
      notificationsAriaLabel: t("topbar.notificationsAriaLabel", {
        count: session.unreadNotifications,
      }),
      userMenuLabel: t("topbar.userMenuLabel", { name: session.user.name, role: roleLabel }),
      myWorkspace: t("topbar.myWorkspace"),
      theme: t("topbar.theme"),
      logout: t("topbar.logout"),
      roleLabel,
    },
    gatewayError: {
      funcionalTitle: t("gatewayError.funcionalTitle"),
      funcionalWhy: t("gatewayError.funcionalWhy"),
      technicalTitle: t("gatewayError.technicalTitle"),
      technicalWhy: t("gatewayError.technicalWhy"),
      retry: t("gatewayError.retry"),
      retrying: t("gatewayError.retrying"),
    },
  };

  return (
    <SessionProvider value={session}>
      <ShellFrame theme={theme} labels={labels}>
        {children}
      </ShellFrame>
    </SessionProvider>
  );
}
