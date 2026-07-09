import userEvent from "@testing-library/user-event";
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Tooltip } from "./tooltip";

describe("Tooltip", () => {
  it("estampa data-tip en su único hijo con el texto de `label`", () => {
    render(
      <Tooltip label="Prefijo servido desde cache: ahorro ~90%">
        <button type="button">Tooltip al hover/focus</button>
      </Tooltip>,
    );

    const trigger = screen.getByRole("button", { name: "Tooltip al hover/focus" });
    expect(trigger.getAttribute("data-tip")).toBe("Prefijo servido desde cache: ahorro ~90%");
  });

  it("el tooltip queda visible por focus-visible sin usar el mouse (navegación por teclado)", async () => {
    const user = userEvent.setup();
    render(
      <div>
        <Tooltip label="Ahorro por cache">
          <button type="button">Con tooltip</button>
        </Tooltip>
      </div>,
    );

    const trigger = screen.getByRole("button", { name: "Con tooltip" });
    expect(document.activeElement).not.toBe(trigger);

    // Tab (sin mouse) es lo que dispara :focus-visible en el CSS portado
    // ([data-tip]:focus-visible::after, styles/components/tooltip.css).
    await user.tab();

    expect(document.activeElement).toBe(trigger);
    expect(trigger.getAttribute("data-tip")).toBe("Ahorro por cache");
  });

  it("preserva el resto de props/handlers del hijo", async () => {
    const user = userEvent.setup();
    let clicked = false;
    render(
      <Tooltip label="Info">
        <button type="button" onClick={() => (clicked = true)}>
          Click
        </button>
      </Tooltip>,
    );

    await user.click(screen.getByRole("button", { name: "Click" }));
    expect(clicked).toBe(true);
  });
});
