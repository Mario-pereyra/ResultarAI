import userEvent from "@testing-library/user-event";
import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { StarterSuggestions } from "./starter-suggestions";

describe("StarterSuggestions (tarea 3.5)", () => {
  it("renderiza cada sugerencia como botón clicable", () => {
    render(
      <StarterSuggestions
        prompts={["Ayudame a redactar un resumen", "Explicame un concepto"]}
        onSelect={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: "Ayudame a redactar un resumen" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Explicame un concepto" })).toBeTruthy();
  });

  it("click llama a onSelect con el texto exacto de la sugerencia", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(<StarterSuggestions prompts={["Dame ideas para organizar la semana"]} onSelect={onSelect} />);

    await user.click(screen.getByRole("button", { name: "Dame ideas para organizar la semana" }));

    expect(onSelect).toHaveBeenCalledTimes(1);
    expect(onSelect).toHaveBeenCalledWith("Dame ideas para organizar la semana");
  });

  it("sin sugerencias no renderiza nada", () => {
    const { container } = render(<StarterSuggestions prompts={[]} onSelect={vi.fn()} />);
    expect(container.firstChild).toBeNull();
  });
});
