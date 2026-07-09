import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Tag } from "./tag";

describe("Tag", () => {
  it("la variante neutral por defecto solo agrega la clase base .tag", () => {
    render(<Tag>v1.3.0</Tag>);

    const tag = screen.getByText("v1.3.0");
    expect(tag.tagName).toBe("SPAN");
    expect(tag.className.trim()).toBe("tag");
  });

  it("aplica la clase de cada variante de color", () => {
    render(
      <>
        <Tag variant="money">riesgo bajo</Tag>
        <Tag variant="warn">riesgo medio</Tag>
        <Tag variant="alt">riesgo alto</Tag>
        <Tag variant="danger">riesgo crítico</Tag>
      </>,
    );

    expect(screen.getByText("riesgo bajo").className).toContain("tag--money");
    expect(screen.getByText("riesgo medio").className).toContain("tag--warn");
    expect(screen.getByText("riesgo alto").className).toContain("tag--alt");
    expect(screen.getByText("riesgo crítico").className).toContain("tag--danger");
  });

  it("outline agrega .tag--outline manteniendo la variante de color", () => {
    render(
      <Tag variant="accent" outline>
        activo
      </Tag>,
    );

    const tag = screen.getByText("activo");
    expect(tag.className.split(" ")).toEqual(
      expect.arrayContaining(["tag", "tag--accent", "tag--outline"]),
    );
  });

  it("siempre requiere la palabra visible (nunca solo color)", () => {
    render(<Tag variant="danger">bloqueado</Tag>);

    expect(screen.getByText("bloqueado")).toBeTruthy();
  });
});
