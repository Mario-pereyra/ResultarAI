import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Panel } from "./panel";

describe("Panel", () => {
  it("renderiza la variante default solo con la clase base .panel", () => {
    render(<Panel>Contenido</Panel>);

    const panel = screen.getByText("Contenido");
    expect(panel.className.trim()).toBe("panel");
  });

  it("la variante flush agrega .panel--flush", () => {
    render(<Panel variant="flush">Tabla embebida</Panel>);

    const panel = screen.getByText("Tabla embebida");
    expect(panel.className.split(" ")).toEqual(
      expect.arrayContaining(["panel", "panel--flush"]),
    );
  });

  it("la variante raised agrega .panel--raised", () => {
    render(<Panel variant="raised">Ficha destacada</Panel>);

    const panel = screen.getByText("Ficha destacada");
    expect(panel.className.split(" ")).toEqual(
      expect.arrayContaining(["panel", "panel--raised"]),
    );
  });
});
