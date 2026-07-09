import userEvent from "@testing-library/user-event";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Dropdown, type DropdownItem } from "./dropdown";

function buildItems(onSelect: (id: string) => void): DropdownItem[] {
  return [
    { id: "profile", label: "Perfil", onSelect: () => onSelect("profile") },
    { id: "settings", label: "Configuración", onSelect: () => onSelect("settings") },
    { id: "logout", label: "Cerrar sesión", onSelect: () => onSelect("logout"), danger: true },
  ];
}

describe("Dropdown", () => {
  it("expone aria-haspopup/aria-expanded y abre el menú con click, enfocando el primer ítem", async () => {
    const user = userEvent.setup();
    render(<Dropdown triggerLabel="Cuenta" items={buildItems(vi.fn())} />);

    const trigger = screen.getByRole("button", { name: "Cuenta" });
    expect(trigger.getAttribute("aria-haspopup")).toBe("menu");
    expect(trigger.getAttribute("aria-expanded")).toBe("false");
    expect(screen.queryByRole("menu")).toBeNull();

    await user.click(trigger);

    expect(trigger.getAttribute("aria-expanded")).toBe("true");
    expect(screen.getByRole("menu")).not.toBeNull();
    expect(document.activeElement).toBe(screen.getByRole("menuitem", { name: "Perfil" }));
  });

  it("ArrowDown/ArrowUp mueven el foco entre ítems y hacen wrap en los extremos", async () => {
    const user = userEvent.setup();
    render(<Dropdown triggerLabel="Cuenta" items={buildItems(vi.fn())} />);

    await user.click(screen.getByRole("button", { name: "Cuenta" }));

    await user.keyboard("{ArrowDown}");
    expect(document.activeElement).toBe(screen.getByRole("menuitem", { name: "Configuración" }));

    await user.keyboard("{ArrowDown}");
    expect(document.activeElement).toBe(screen.getByRole("menuitem", { name: "Cerrar sesión" }));

    // Wrap: del último vuelve al primero.
    await user.keyboard("{ArrowDown}");
    expect(document.activeElement).toBe(screen.getByRole("menuitem", { name: "Perfil" }));

    // Wrap inverso: del primero, ArrowUp va al último.
    await user.keyboard("{ArrowUp}");
    expect(document.activeElement).toBe(screen.getByRole("menuitem", { name: "Cerrar sesión" }));
  });

  it("Home/End mueven el foco al primer/último ítem", async () => {
    const user = userEvent.setup();
    render(<Dropdown triggerLabel="Cuenta" items={buildItems(vi.fn())} />);

    await user.click(screen.getByRole("button", { name: "Cuenta" }));

    await user.keyboard("{End}");
    expect(document.activeElement).toBe(screen.getByRole("menuitem", { name: "Cerrar sesión" }));

    await user.keyboard("{Home}");
    expect(document.activeElement).toBe(screen.getByRole("menuitem", { name: "Perfil" }));
  });

  it("Esc cierra el menú y devuelve el foco al disparador", async () => {
    const user = userEvent.setup();
    render(<Dropdown triggerLabel="Cuenta" items={buildItems(vi.fn())} />);

    const trigger = screen.getByRole("button", { name: "Cuenta" });
    await user.click(trigger);
    await user.keyboard("{Escape}");

    expect(trigger.getAttribute("aria-expanded")).toBe("false");
    expect(document.activeElement).toBe(trigger);
    expect(screen.queryByRole("menu")).toBeNull();
  });

  it("un click fuera del dropdown lo cierra", async () => {
    const user = userEvent.setup();
    render(
      <div>
        <Dropdown triggerLabel="Cuenta" items={buildItems(vi.fn())} />
        <button>fuera</button>
      </div>,
    );

    await user.click(screen.getByRole("button", { name: "Cuenta" }));
    expect(screen.getByRole("menu")).not.toBeNull();

    await user.click(screen.getByRole("button", { name: "fuera" }));
    expect(screen.queryByRole("menu")).toBeNull();
  });

  it("seleccionar un ítem lo ejecuta, cierra el menú y devuelve el foco al disparador", async () => {
    const onSelect = vi.fn();
    const user = userEvent.setup();
    render(<Dropdown triggerLabel="Cuenta" items={buildItems(onSelect)} />);

    const trigger = screen.getByRole("button", { name: "Cuenta" });
    await user.click(trigger);
    await user.click(screen.getByRole("menuitem", { name: "Perfil" }));

    expect(onSelect).toHaveBeenCalledWith("profile");
    expect(screen.queryByRole("menu")).toBeNull();
    expect(document.activeElement).toBe(trigger);
  });

  it("los ítems disabled se saltan durante la navegación con flechas", async () => {
    const user = userEvent.setup();
    render(
      <Dropdown
        triggerLabel="Cuenta"
        items={[
          { id: "a", label: "A", onSelect: vi.fn() },
          { id: "b", label: "B", onSelect: vi.fn(), disabled: true },
          { id: "c", label: "C", onSelect: vi.fn() },
        ]}
      />,
    );

    await user.click(screen.getByRole("button", { name: "Cuenta" }));
    expect(document.activeElement).toBe(screen.getByRole("menuitem", { name: "A" }));

    await user.keyboard("{ArrowDown}");
    expect(document.activeElement).toBe(screen.getByRole("menuitem", { name: "C" }));
  });
});
