import userEvent from "@testing-library/user-event";
import { render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { SessionProvider, type SessionContextValue } from "@/lib/session-context";
import { capabilitiesForRole } from "@/lib/capabilities";
import { Topbar, type TopbarLabels } from "./topbar";

const refresh = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ refresh }),
}));

const labels: TopbarLabels = {
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
};

function sessionFor(
  role: SessionContextValue["user"]["role"],
  name: string,
  unreadNotifications = 0,
): SessionContextValue {
  return {
    user: { name, role },
    gateway: { status: "ok" },
    pendingApprovals: 0,
    unreadNotifications,
    capabilities: capabilitiesForRole(role),
  };
}

function renderTopbar(
  role: SessionContextValue["user"]["role"] = "funcional",
  name = "lucia",
  unreadNotifications = 0,
) {
  return render(
    <SessionProvider value={sessionFor(role, name, unreadNotifications)}>
      <Topbar theme="dark" labels={{ ...labels, roleLabel: "Funcional" }} onOpenDrawer={vi.fn()} />
    </SessionProvider>,
  );
}

describe("Topbar", () => {
  beforeEach(() => {
    refresh.mockClear();
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(JSON.stringify({ theme: "light" }))),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it('escenario "Badge de rol visible en el menú de usuario": el badge-rol del menú coincide con el rol de la sesión', () => {
    const { container } = renderTopbar("funcional");

    const badge = container.querySelector(".badge-rol--funcional");
    expect(badge).not.toBeNull();
    expect(badge?.textContent).toBe("Funcional");
  });

  it("el trigger del menú de usuario expone el nombre accesible con nombre y rol", () => {
    renderTopbar("funcional");

    expect(
      screen.getByRole("button", { name: "Menú de usuario: lucia, rol Funcional" }),
    ).not.toBeNull();
  });

  it('escenario "Alternar tema persiste entre sesiones": el ícono de tema llama a POST /api/theme y refresca la ruta', async () => {
    const user = userEvent.setup();
    renderTopbar("funcional");

    const themeButton = screen.getByRole("button", { name: "Cambiar a tema claro" });
    await user.click(themeButton);

    expect(fetch).toHaveBeenCalledWith("/api/theme", { method: "POST" });
    expect(refresh).toHaveBeenCalledOnce();
  });

  it('el ítem "Tema" del menú de usuario alterna el mismo endpoint de tema', async () => {
    const user = userEvent.setup();
    renderTopbar("funcional");

    await user.click(screen.getByRole("button", { name: "Menú de usuario: lucia, rol Funcional" }));
    await user.click(screen.getByRole("menuitem", { name: "Tema" }));

    expect(fetch).toHaveBeenCalledWith("/api/theme", { method: "POST" });
    expect(refresh).toHaveBeenCalledOnce();
  });

  describe('escenario "Botón con texto 25% más largo no rompe el layout" (tarea 6.2)', () => {
    it("un nombre de usuario un 25% más largo se renderiza completo en .shell-topbar__user-name", () => {
      const original = "lucia";
      const inflated = `${original}${"~".repeat(Math.ceil(original.length * 0.25))}`;

      const { container } = renderTopbar("funcional", inflated);

      const nameEl = container.querySelector(".shell-topbar__user-name");
      expect(nameEl?.textContent).toBe(inflated);
    });
  });

  describe('escenario "Contador de notificaciones no leídas": plural ICU en la campana (tarea 6.3)', () => {
    it("sin no leídas: el botón usa el nombre accesible interpolado en 0 y no muestra badge visible", () => {
      const { container } = renderTopbar("funcional", "lucia", 0);

      expect(
        screen.getByRole("button", { name: "Notificaciones, sin novedades" }),
      ).not.toBeNull();
      expect(container.querySelector(".notif-bell__count")).toBeNull();
    });

    it("con 1 no leída: el nombre accesible interpolado en singular y el badge muestra 1", () => {
      const { container } = render(
        <SessionProvider
          value={{
            user: { name: "dario", role: "tecnico" },
            gateway: { status: "ok" },
            pendingApprovals: 0,
            unreadNotifications: 1,
            capabilities: capabilitiesForRole("tecnico"),
          }}
        >
          <Topbar
            theme="dark"
            labels={{
              ...labels,
              roleLabel: "Técnico",
              notificationsAriaLabel: "Notificaciones, 1 no leída",
            }}
            onOpenDrawer={vi.fn()}
          />
        </SessionProvider>,
      );

      expect(screen.getByRole("button", { name: "Notificaciones, 1 no leída" })).not.toBeNull();
      expect(container.querySelector(".notif-bell__count")?.textContent).toBe("1");
    });

    it("con N no leídas: el nombre accesible interpolado en plural y el badge muestra el número", () => {
      const { container } = render(
        <SessionProvider
          value={{
            user: { name: "marcos", role: "admin" },
            gateway: { status: "ok" },
            pendingApprovals: 0,
            unreadNotifications: 4,
            capabilities: capabilitiesForRole("admin"),
          }}
        >
          <Topbar
            theme="dark"
            labels={{
              ...labels,
              roleLabel: "Admin",
              notificationsAriaLabel: "Notificaciones, 4 no leídas",
            }}
            onOpenDrawer={vi.fn()}
          />
        </SessionProvider>,
      );

      expect(screen.getByRole("button", { name: "Notificaciones, 4 no leídas" })).not.toBeNull();
      expect(container.querySelector(".notif-bell__count")?.textContent).toBe("4");
    });
  });
});
