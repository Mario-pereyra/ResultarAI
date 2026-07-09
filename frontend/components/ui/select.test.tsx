import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Select } from "./select";

describe("Select", () => {
  it("asocia el label con el <select> mediante htmlFor/id y renderiza las opciones recibidas", () => {
    render(
      <Select label="Ambiente" required>
        <option value="">Seleccioná un ambiente…</option>
        <option value="prod">PROD</option>
        <option value="homolog">Homologación</option>
      </Select>,
    );

    const select = screen.getByLabelText(/Ambiente/) as HTMLSelectElement;
    expect(select.tagName).toBe("SELECT");
    expect(select.className).toContain("select");

    const options = screen.getAllByRole("option");
    expect(options.map((o) => o.textContent)).toEqual([
      "Seleccioná un ambiente…",
      "PROD",
      "Homologación",
    ]);
  });

  it("marca aria-invalid y aria-describedby cuando hay error", () => {
    render(
      <Select label="Ambiente" error="Elegí un ambiente válido.">
        <option value="prod">PROD</option>
      </Select>,
    );

    const select = screen.getByLabelText("Ambiente");
    const error = screen.getByText("Elegí un ambiente válido.");

    expect(select.getAttribute("aria-invalid")).toBe("true");
    expect(select.getAttribute("aria-describedby")).toBe(error.id);
    expect(select.className).toContain("is-invalid");
  });

  it("el ícono del chevron es decorativo (aria-hidden) y no interfiere con el control accesible", () => {
    const { container } = render(
      <Select label="Ambiente">
        <option value="prod">PROD</option>
      </Select>,
    );

    const chevron = container.querySelector("svg.select-chevron");
    expect(chevron).not.toBeNull();
    expect(chevron?.getAttribute("aria-hidden")).toBe("true");
  });
});
