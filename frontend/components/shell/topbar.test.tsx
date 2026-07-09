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
  userMenuLabel: "Menú de usuario: lucia, rol Funcional",
  myWorkspace: "Mi espacio",
  theme: "Tema",
  logout: "Cerrar sesión",
  roleLabel: "Funcional",
};

function sessionFor(role: SessionContextValue["user"]["role"], name: string): SessionContextValue {
  return {
    user: { name, role },
    gateway: { status: "ok" },
    pendingApprovals: 0,
    capabilities: capabilitiesForRole(role),
  };
}

function renderTopbar(role: SessionContextValue["user"]["role"] = "funcional", name = "lucia") {
  return render(
    <SessionProvider value={sessionFor(role, name)}>
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
});
