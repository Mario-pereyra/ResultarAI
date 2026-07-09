import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Button } from "./button";

describe("Button", () => {
  it("renderiza un <button> real con la variante primary por defecto", () => {
    render(<Button>Aprobar escritura</Button>);

    const button = screen.getByRole("button", { name: "Aprobar escritura" });
    expect(button.tagName).toBe("BUTTON");
    expect(button.className.split(" ")).toEqual(
      expect.arrayContaining(["btn", "btn--primary"]),
    );
    expect(button.getAttribute("type")).toBe("button");
  });

  it("aplica la clase de cada variante (secondary/danger/ghost)", () => {
    render(
      <>
        <Button variant="secondary">Ver evidencia</Button>
        <Button variant="danger">Eliminar usuario</Button>
        <Button variant="ghost">Cancelar</Button>
      </>,
    );

    expect(
      screen.getByRole("button", { name: "Ver evidencia" }).className,
    ).toContain("btn--secondary");
    expect(
      screen.getByRole("button", { name: "Eliminar usuario" }).className,
    ).toContain("btn--danger");
    expect(
      screen.getByRole("button", { name: "Cancelar" }).className,
    ).toContain("btn--ghost");
  });

  it("aplica las clases de tamaño sm/lg y block", () => {
    render(
      <>
        <Button size="sm">Pequeño</Button>
        <Button size="lg">Grande</Button>
        <Button block>Ancho completo</Button>
      </>,
    );

    expect(screen.getByRole("button", { name: "Pequeño" }).className).toContain(
      "btn--sm",
    );
    expect(screen.getByRole("button", { name: "Grande" }).className).toContain(
      "btn--lg",
    );
    expect(
      screen.getByRole("button", { name: "Ancho completo" }).className,
    ).toContain("btn--block");
  });

  // Escenario "Botón primario con estado de carga" —
  // openspec/changes/d10-design-system-shell/specs/design-system/spec.md
  it('escenario "Botón primario con estado de carga": aria-busy, spinner y texto disponible para lectores', () => {
    render(<Button loading>Aprobar escritura</Button>);

    const button = screen.getByRole("button", { name: "Aprobar escritura" });
    expect(button.getAttribute("aria-busy")).toBe("true");
    expect(button.className).toContain("btn--loading");
    // El texto NUNCA se elimina del DOM en loading (queda transparente vía CSS).
    expect(button.textContent).toBe("Aprobar escritura");
    // "deshabilita interacción": atributo disabled real, no solo la clase.
    expect(button.hasAttribute("disabled")).toBe(true);
  });

  it("loading deshabilita la interacción: el click no dispara el handler", async () => {
    const user = userEvent.setup();
    const onClick = vi.fn();
    render(
      <Button loading onClick={onClick}>
        Aprobar escritura
      </Button>,
    );

    await user.click(screen.getByRole("button", { name: "Aprobar escritura" }));
    expect(onClick).not.toHaveBeenCalled();
  });

  it("disabled explícito deshabilita el botón aunque no esté loading", () => {
    render(<Button disabled>Cancelar</Button>);

    const button = screen.getByRole("button", { name: "Cancelar" });
    expect(button.hasAttribute("disabled")).toBe(true);
    expect(button.hasAttribute("aria-busy")).toBe(false);
  });
});
