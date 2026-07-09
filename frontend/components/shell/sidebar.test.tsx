import userEvent from "@testing-library/user-event";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { useState } from "react";
import { SessionProvider, type SessionContextValue } from "@/lib/session-context";
import { capabilitiesForRole } from "@/lib/capabilities";
import { Sidebar, type SidebarLabels } from "./sidebar";

const labels: SidebarLabels = {
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
};

function sessionFor(role: SessionContextValue["user"]["role"]): SessionContextValue {
  return {
    user: { name: "test", role },
    gateway: { status: "ok" },
    pendingApprovals: 0,
    unreadNotifications: 0,
    capabilities: capabilitiesForRole(role),
  };
}

function renderSidebar(
  role: SessionContextValue["user"]["role"],
  props: Partial<Parameters<typeof Sidebar>[0]> = {},
) {
  return render(
    <SessionProvider value={sessionFor(role)}>
      <Sidebar
        labels={labels}
        collapsed={false}
        onToggleCollapse={vi.fn()}
        drawerOpen={false}
        onCloseDrawer={vi.fn()}
        {...props}
      />
    </SessionProvider>,
  );
}

describe("Sidebar — filtrado por capacidades del rol (tarea 5.3)", () => {
  it("escenario: Rol Funcional no ve secciones de Admin", () => {
    renderSidebar("funcional");

    expect(screen.getByText("Catálogo")).not.toBeNull();
    expect(screen.getByText("Chat")).not.toBeNull();
    expect(screen.getByText("Workflows")).not.toBeNull();
    expect(screen.getByText("Aprobaciones")).not.toBeNull();
    expect(screen.getByText("Mi espacio")).not.toBeNull();

    expect(screen.queryByText("Administración")).toBeNull();
    expect(screen.queryByText("Construcción")).toBeNull();
    expect(screen.queryByText("Admin")).toBeNull();
  });

  it("escenario: Rol Admin ve todas las secciones", () => {
    renderSidebar("admin");

    expect(screen.getByText("Catálogo")).not.toBeNull();
    expect(screen.getByText("Chat")).not.toBeNull();
    expect(screen.getByText("Workflows")).not.toBeNull();
    expect(screen.getByText("Aprobaciones")).not.toBeNull();
    expect(screen.getByText("Mi espacio")).not.toBeNull();
    expect(screen.getByText("Administración")).not.toBeNull();
    expect(screen.getByText("Construcción")).not.toBeNull();
    expect(screen.getByText("Admin")).not.toBeNull();
  });

  it("Técnico ve las mismas 5 secciones que Funcional, sin Admin/Construcción", () => {
    renderSidebar("tecnico");

    expect(screen.getByText("Aprobaciones")).not.toBeNull();
    expect(screen.queryByText("Administración")).toBeNull();
    expect(screen.queryByText("Construcción")).toBeNull();
  });
});

describe("Sidebar — drawer móvil con trampa de foco (tarea 5.7)", () => {
  it('escenario "Drawer con trampa de foco en móvil": aria-modal, foco inicial dentro y Tab cicla', async () => {
    const user = userEvent.setup();
    renderSidebar("admin", { drawerOpen: true });

    const dialog = screen.getByRole("dialog", { name: "Menú principal" });
    expect(dialog.getAttribute("aria-modal")).toBe("true");

    // Foco inicial: primer elemento enfocable dentro del drawer (el buscador).
    expect(dialog.contains(document.activeElement)).toBe(true);

    // Tab repetido nunca escapa el drawer (trampa de foco).
    for (let i = 0; i < 15; i++) {
      await user.tab();
      expect(dialog.contains(document.activeElement)).toBe(true);
    }
  });

  it("Esc cierra el drawer y devuelve el foco al disparador", async () => {
    const user = userEvent.setup();
    const onCloseDrawer = vi.fn();

    // Harness con estado real: al cerrar, el drawer se desmonta de verdad y la
    // trampa de foco (use-focus-trap) debe devolver el foco al disparador
    // (hallazgo H5 del review final: aseverar el retorno de foco, no solo el callback).
    function Harness() {
      const [open, setOpen] = useState(false);
      return (
        <div>
          <button onClick={() => setOpen(true)}>abrir</button>
          <SessionProvider value={sessionFor("funcional")}>
            <Sidebar
              labels={labels}
              collapsed={false}
              onToggleCollapse={vi.fn()}
              drawerOpen={open}
              onCloseDrawer={() => {
                onCloseDrawer();
                setOpen(false);
              }}
            />
          </SessionProvider>
        </div>
      );
    }

    render(<Harness />);
    const trigger = screen.getByRole("button", { name: "abrir" });
    await user.click(trigger);
    expect(document.querySelector('[aria-modal="true"]')).not.toBeNull();

    await user.keyboard("{Escape}");

    expect(onCloseDrawer).toHaveBeenCalledOnce();
    expect(document.querySelector('[aria-modal="true"]')).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });

  it("click en el scrim cierra el drawer", async () => {
    const user = userEvent.setup();
    const onCloseDrawer = vi.fn();
    const { container } = renderSidebar("funcional", { drawerOpen: true, onCloseDrawer });

    const scrim = container.querySelector(".shell-drawer-scrim");
    expect(scrim).not.toBeNull();
    await user.click(scrim as Element);

    expect(onCloseDrawer).toHaveBeenCalledOnce();
  });
});

describe('Sidebar — escenario "Botón con texto 25% más largo no rompe el layout" (tarea 6.2)', () => {
  it("un label de sección un 25% más largo se renderiza completo dentro de .shell-sidebar__label, sin recorte", () => {
    const original = "Aprobaciones";
    const inflated = `${original}${"~".repeat(Math.ceil(original.length * 0.25))}`;

    render(
      <SessionProvider value={sessionFor("funcional")}>
        <Sidebar
          labels={{ ...labels, sectionLabels: { ...labels.sectionLabels, aprobaciones: inflated } }}
          collapsed={false}
          onToggleCollapse={vi.fn()}
          drawerOpen={false}
          onCloseDrawer={vi.fn()}
        />
      </SessionProvider>,
    );

    const label = screen.getByText(inflated);
    expect(label.textContent).toBe(inflated);
    expect(label.className).toBe("shell-sidebar__label");
    // .shell-sidebar__label no tiene declaración propia en styles/shell.css
    // (ver styles/text-expansion.test.ts): no hereda ningún ancho fijo del
    // <a> contenedor tampoco — `.shell-sidebar__link` crece con flex, no
    // trunca (mismo contrato verificado ahí a nivel CSS).
  });
});

describe("Sidebar — colapso persistente (tarea 5.3)", () => {
  it('el botón de colapso alterna aria-pressed y llama a onToggleCollapse', async () => {
    const user = userEvent.setup();
    const onToggleCollapse = vi.fn();
    renderSidebar("funcional", { collapsed: false, onToggleCollapse });

    const button = screen.getByRole("button", { name: "Colapsar" });
    expect(button.getAttribute("aria-pressed")).toBe("false");

    await user.click(button);
    expect(onToggleCollapse).toHaveBeenCalledOnce();
  });
});
