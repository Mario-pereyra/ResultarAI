import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { EmptyState } from "./empty-state";

describe("EmptyState", () => {
  it("renderiza título y descripción recibidos por props", () => {
    render(
      <EmptyState
        title="Sin aprobaciones pendientes"
        description="Cuando un agente necesite escribir en Protheus, la solicitud va a aparecer acá."
      />,
    );

    expect(screen.getByText("Sin aprobaciones pendientes")).not.toBeNull();
    expect(
      screen.getByText("Cuando un agente necesite escribir en Protheus, la solicitud va a aparecer acá."),
    ).not.toBeNull();
  });

  it("no renderiza ícono ni acción cuando no se pasan", () => {
    const { container } = render(<EmptyState title="Vacío" description="Sin datos todavía." />);

    expect(container.querySelector(".empty-state__icon")).toBeNull();
    expect(screen.queryByRole("button")).toBeNull();
  });

  it("renderiza el ícono (aria-hidden) y la acción cuando se pasan por props", () => {
    render(
      <EmptyState
        title="Empezá una conversación"
        description="Elegí un agente del catálogo o retomá una sesión reciente."
        icon={<svg aria-hidden="true" data-testid="icon" />}
        action={<button type="button">Ver catálogo</button>}
      />,
    );

    const iconWrapper = document.querySelector(".empty-state__icon");
    expect(iconWrapper?.getAttribute("aria-hidden")).toBe("true");
    expect(screen.getByTestId("icon")).not.toBeNull();
    expect(screen.getByRole("button", { name: "Ver catálogo" })).not.toBeNull();
  });
});
