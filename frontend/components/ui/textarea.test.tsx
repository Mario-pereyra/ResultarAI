import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Textarea } from "./textarea";

describe("Textarea", () => {
  it("asocia el label con el control mediante htmlFor/id", () => {
    render(<Textarea label="Comentario de aprobación" />);

    const textarea = screen.getByLabelText("Comentario de aprobación");
    const label = screen.getByText("Comentario de aprobación");

    expect(textarea.tagName).toBe("TEXTAREA");
    expect(textarea.id).toBeTruthy();
    expect(label.getAttribute("for")).toBe(textarea.id);
    expect(textarea.className).toContain("textarea");
  });

  it("marca aria-invalid y aria-describedby cuando hay error, sin perder el hint", () => {
    render(
      <Textarea
        label="Comentario"
        hint="Obligatorio en riesgo crítico."
        error="Este campo es obligatorio."
      />,
    );

    const textarea = screen.getByLabelText("Comentario");
    const hint = screen.getByText("Obligatorio en riesgo crítico.");
    const error = screen.getByText("Este campo es obligatorio.");

    expect(textarea.getAttribute("aria-invalid")).toBe("true");
    expect(textarea.getAttribute("aria-describedby")).toBe(`${hint.id} ${error.id}`);
    expect(textarea.className).toContain("is-invalid");
  });
});
