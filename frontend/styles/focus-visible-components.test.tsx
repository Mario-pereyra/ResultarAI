import userEvent from "@testing-library/user-event";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Dropdown } from "@/components/ui/dropdown";
import { Textarea } from "@/components/ui/textarea";

/**
 * Escenario "Foco visible en todo interactivo" (tarea 7.2,
 * d10-design-system-shell) — complemento de `styles/focus-visible.test.ts`
 * (que audita ESTÁTICAMENTE que cada familia define su regla CSS
 * `:focus-visible`). Esta suite verifica, para al menos un representante
 * por familia de componente, que la clase que lleva esa regla está
 * REALMENTE aplicada al elemento interactivo renderizado — el resto (que
 * el anillo se vea con el radio/color correctos) lo garantiza el CSS ya
 * portado + la inspección visual del styleguide (tarea 7.3); jsdom no
 * puede verificar el renderizado real de `outline`.
 *
 * Los componentes del shell (Sidebar/Topbar/etc.) ya cubren sus propias
 * clases (`.shell-sidebar__link`, `.shell-topbar__icon`, `.notif-bell`,
 * `.skip-link`) en sus tests dedicados — no se repiten acá.
 */
describe('Foco visible por familia de componente — representante(s) con la clase aplicada (tarea 7.2)', () => {
  it("Button: el <button> real lleva la clase .btn (regla :focus-visible)", () => {
    render(<Button>Aprobar escritura</Button>);
    const button = screen.getByRole("button", { name: "Aprobar escritura" });
    expect(button.className.split(" ")).toContain("btn");
  });

  it("Input: el <input> real lleva la clase .input (regla :focus-visible agrupada con select/textarea)", () => {
    render(<Input label="Nombre" />);
    const input = screen.getByLabelText("Nombre");
    expect(input.className.split(" ")).toContain("input");
  });

  it("Textarea: el <textarea> real lleva la clase .textarea (misma regla agrupada)", () => {
    render(<Textarea label="Comentario" />);
    const textarea = screen.getByLabelText("Comentario");
    expect(textarea.className.split(" ")).toContain("textarea");
  });

  it("Dropdown: el disparador lleva la clase .dropdown__trigger y los ítems .dropdown-menu__item", async () => {
    const user = userEvent.setup();
    render(
      <Dropdown
        triggerLabel="Cuenta"
        items={[{ id: "a", label: "Perfil", onSelect: vi.fn() }]}
      />,
    );

    const trigger = screen.getByRole("button", { name: "Cuenta" });
    expect(trigger.className.split(" ")).toContain("dropdown__trigger");

    await user.click(trigger);
    const item = screen.getByRole("menuitem", { name: "Perfil" });
    expect(item.className.split(" ")).toContain("dropdown-menu__item");
  });
});
