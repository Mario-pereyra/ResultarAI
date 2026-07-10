import userEvent from "@testing-library/user-event";
import { render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { SessionProvider, type SessionContextValue } from "@/lib/session-context";
import { capabilitiesForRole } from "@/lib/capabilities";
import { ShellFrame, type ShellFrameLabels } from "./shell-frame";

vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh: vi.fn() }),
}));

const labels: ShellFrameLabels = {
  skipLink: "Saltar al contenido",
  banner: {
    full: "Respuestas generadas por IA — verificá antes de aplicar en cliente",
    short: "Respuestas generadas por IA — verificá antes de aplicar",
  },
  sidebar: {
    instanceName: "Resultar Bolivia",
    sectionLabels: {
      catalogo: "Catálogo",
      chat: "Chat",
      workflows: "Workflows",
      aprobaciones: "Aprobaciones",
      "mi-espacio": "Mi espacio",
      administracion: "Administración",
      construccion: "Construcción",
    },
    adminKicker: "Admin",
    collapse: "Colapsar",
    expand: "Expandir",
    navLabel: "Principal",
    drawerLabel: "Menú principal",
    approvalsAriaLabel: "Aprobaciones, pendientes",
    drawerSearchPlaceholder: "Buscar…",
  },
  topbar: {
    searchLabel: "Buscar agentes, sesiones, docs…",
    searchPlaceholder: "Buscar agentes, sesiones, docs…",
    searchShortcutHint: "Ctrl K",
    openMenu: "Abrir menú",
    themeToLight: "Cambiar a tema claro",
    themeToDark: "Cambiar a tema oscuro",
    notifications: "Notificaciones",
    notificationsEmpty: "Sin novedades por ahora",
    notificationsAriaLabel: "Notificaciones, sin novedades",
    userMenuLabel: "Menú de usuario: lucia, rol Funcional",
    myWorkspace: "Mi espacio",
    theme: "Tema",
    logout: "Cerrar sesión",
    roleLabel: "Funcional",
    notificationsEmptyHint: "Acá vas a ver aprobaciones, avisos de cuota y novedades del sistema.",
    notificationsError: "No se pudieron cargar las notificaciones",
    notificationsRetry: "Reintentar",
    notificationsMarkAllRead: "Marcar leídas",
    notificationsViewAll: "Ver todas",
    notificationsView: "Ver",
    notificationsClose: "Cerrar notificaciones",
    notificationsKickerCuotas: "Cuotas",
    notificationsKickerSistema: "Sistema",
    notificationsKickerAprobaciones: "Aprobaciones",
  },
  gatewayError: {
    funcionalTitle: "El asistente no está disponible",
    funcionalWhy: "Intentá de nuevo en unos minutos.",
    technicalTitle: "El servicio de IA no está disponible",
    technicalWhy: "El gateway del modelo no está respondiendo.",
    retry: "Reintentar",
    retrying: "Reintentando…",
  },
};

function sessionFor(
  role: SessionContextValue["user"]["role"],
  gatewayStatus: SessionContextValue["gateway"]["status"],
): SessionContextValue {
  return {
    user: { name: "lucia", role },
    gateway: { status: gatewayStatus },
    pendingApprovals: 0,
    unreadNotifications: 0,
    capabilities: capabilitiesForRole(role),
  };
}

function renderFrame(session: SessionContextValue) {
  return render(
    <SessionProvider value={session}>
      <ShellFrame theme="dark" labels={labels}>
        <p>Contenido de la página</p>
      </ShellFrame>
    </SessionProvider>,
  );
}

beforeEach(() => {
  window.localStorage.clear();
});

describe('ShellFrame — escenario "Gateway caído no bloquea el shell"', () => {
  it("con gateway offline, sidebar/topbar siguen operativos y el contenido de la página sigue presente", () => {
    renderFrame(sessionFor("tecnico", "offline"));

    // Sidebar operativo.
    expect(screen.getByRole("navigation", { name: "Principal" })).not.toBeNull();
    expect(screen.getByText("Catálogo")).not.toBeNull();

    // Topbar operativo (buscador, menú de usuario).
    expect(screen.getByRole("search")).not.toBeNull();
    expect(screen.getByRole("button", { name: "Menú de usuario: lucia, rol Funcional" })).not.toBeNull();

    // Error-card presente para el contenido afectado.
    expect(screen.getByRole("alert")).not.toBeNull();

    // El contenido de la página sigue renderizando (no bloquea la navegación).
    expect(screen.getByText("Contenido de la página")).not.toBeNull();
  });

  it("con gateway ok, no aparece ningún error-card", () => {
    renderFrame(sessionFor("tecnico", "ok"));
    expect(screen.queryByRole("alert")).toBeNull();
  });
});

describe('ShellFrame — escenario "Skip-link es el primer foco"', () => {
  it("Tab desde la carga de la página enfoca primero el skip-link", async () => {
    const user = userEvent.setup();
    renderFrame(sessionFor("funcional", "ok"));

    await user.tab();

    expect(document.activeElement?.textContent).toBe("Saltar al contenido");
    expect((document.activeElement as HTMLElement).className).toContain("skip-link");
  });

  it("el skip-link apunta al id del <main> del shell", () => {
    const { container } = renderFrame(sessionFor("funcional", "ok"));
    const skipLink = container.querySelector(".skip-link") as HTMLAnchorElement;
    const main = container.querySelector("main");

    expect(skipLink.getAttribute("href")).toBe(`#${main?.id}`);
  });
});

describe("ShellFrame — colapso del sidebar persistido por usuario (tarea 5.3, hallazgo H1 del review)", () => {
  it("round-trip: colapsar escribe localStorage y un montaje nuevo restaura el estado colapsado", async () => {
    const user = userEvent.setup();

    // Primer montaje: sidebar expandido, se colapsa con el botón.
    const first = renderFrame(sessionFor("funcional", "ok"));
    await user.click(screen.getByRole("button", { name: "Colapsar" }));
    expect(window.localStorage.getItem("resultarai:sidebar-collapsed")).toBe("true");
    first.unmount();

    // Segundo montaje (sesión nueva del mismo usuario): restaura desde localStorage.
    renderFrame(sessionFor("funcional", "ok"));
    const toggle = screen.getByRole("button", { name: "Expandir" });
    expect(toggle.getAttribute("aria-pressed")).toBe("true");

    // Expandir de vuelta también persiste.
    await user.click(toggle);
    expect(window.localStorage.getItem("resultarai:sidebar-collapsed")).toBe("false");
  });
});
