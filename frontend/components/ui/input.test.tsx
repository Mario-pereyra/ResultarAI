import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Input } from "./input";

describe("Input", () => {
  it("asocia el label con el control mediante htmlFor/id (generado con useId)", () => {
    render(<Input label="Nombre del cliente final" />);

    const input = screen.getByLabelText("Nombre del cliente final");
    const label = screen.getByText("Nombre del cliente final");

    expect(input.id).toBeTruthy();
    expect(label.getAttribute("for")).toBe(input.id);
  });

  it("usa el id explícito si se provee, en vez del generado", () => {
    render(<Input label="Parámetro" id="f2" />);

    const input = screen.getByLabelText("Parámetro");
    expect(input.id).toBe("f2");
  });

  it("expone el hint mediante aria-describedby cuando no hay error", () => {
    render(<Input label="Nombre" hint="Como figura en el contrato." />);

    const input = screen.getByLabelText("Nombre");
    const hint = screen.getByText("Como figura en el contrato.");

    expect(input.getAttribute("aria-describedby")).toBe(hint.id);
    expect(input.hasAttribute("aria-invalid")).toBe(false);
  });

  it("marca aria-invalid y anuncia el error vía aria-describedby cuando hay error", () => {
    render(<Input label="Correo" error="Ingresá un correo válido." />);

    const input = screen.getByLabelText("Correo");
    const error = screen.getByText("Ingresá un correo válido.");

    expect(input.getAttribute("aria-invalid")).toBe("true");
    expect(input.getAttribute("aria-describedby")).toBe(error.id);
    expect(input.className).toContain("is-invalid");
  });

  it("el hint no desaparece cuando aparece el error: se apilan ambos en aria-describedby", () => {
    render(
      <Input
        label="Parámetro"
        hint="Estado focus simulado."
        error="Valor inválido para este ambiente."
      />,
    );

    const input = screen.getByLabelText("Parámetro");
    const hint = screen.getByText("Estado focus simulado.");
    const error = screen.getByText("Valor inválido para este ambiente.");

    expect(input.getAttribute("aria-describedby")).toBe(`${hint.id} ${error.id}`);
  });

  it("marca el asterisco de requerido con aria-hidden (el atributo required va en el control)", () => {
    render(<Input label="Nombre del cliente final" required />);

    // El texto del label queda "Nombre del cliente final *" (asterisco
    // inyectado): se matchea por regex en vez de string exacto.
    const input = screen.getByLabelText(/Nombre del cliente final/);
    expect(input.hasAttribute("required")).toBe(true);

    const req = screen.getByText("*");
    expect(req.getAttribute("aria-hidden")).toBe("true");
  });

  it("aplica input--mono cuando mono=true", () => {
    render(<Input label="Parámetro" mono defaultValue="MV_PAISLOC" />);

    const input = screen.getByLabelText("Parámetro");
    expect(input.className).toContain("input--mono");
  });
});
