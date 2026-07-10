import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { SessionTaximeter, type SessionTaximeterLabels } from "./session-taximeter";

/**
 * Tareas 4.2/4.4 de d13-chat-conversacion (`design/VISTAS/02-chat.md`
 * vista 06 §2): taxímetro de sesión en el header. Ausencia total para
 * Funcional (requirement `chat-experience`), suma acumulada mostrada para
 * Técnico/Admin, estado degradado (`~` + tooltip "costo estimado") SOLO
 * para Admin (ver docstring de `session-taximeter.tsx`).
 */

const LABELS: SessionTaximeterLabels = {
  label: "Sesión",
  srLabelPrefix: "Costo de sesión:",
  degradedTooltip: "costo estimado, telemetría diferida",
};

describe("SessionTaximeter — ausencia total para Funcional (tarea 4.2)", () => {
  it("no renderiza nada para el rol funcional, ni siquiera en estado degradado", () => {
    const { container } = render(
      <SessionTaximeter
        role="funcional"
        costUsd={0.03}
        totalTokens={1000}
        degraded={true}
        labels={LABELS}
      />,
    );
    expect(container.firstChild).toBeNull();
  });
});

describe("SessionTaximeter — suma acumulada Técnico/Admin (tarea 4.2)", () => {
  it("muestra el costo y los tokens formateados para Técnico", () => {
    render(
      <SessionTaximeter
        role="tecnico"
        costUsd={0.03}
        totalTokens={12400}
        degraded={false}
        labels={LABELS}
      />,
    );
    expect(screen.getByText("Sesión")).toBeTruthy();
    expect(screen.getByText("USD 0,0300")).toBeTruthy();
    expect(screen.getByText("12,4k tok")).toBeTruthy();
  });

  it("muestra USD 0,0000 en una sesión sin turnos todavía", () => {
    render(
      <SessionTaximeter role="admin" costUsd={0} totalTokens={0} degraded={false} labels={LABELS} />,
    );
    expect(screen.getByText("USD 0,0000")).toBeTruthy();
  });
});

describe("SessionTaximeter — estado degradado, solo Admin (tarea 4.4)", () => {
  it("Admin: antepone «~» y anuncia el tooltip de costo estimado", () => {
    render(
      <SessionTaximeter role="admin" costUsd={0.0214} totalTokens={48100} degraded={true} labels={LABELS} />,
    );
    const value = screen.getByText("~USD 0,0214");
    expect(value).toBeTruthy();
    const status = screen.getByRole("status");
    expect(status.getAttribute("data-tip")).toBe(LABELS.degradedTooltip);
    expect(status.getAttribute("aria-label")).toContain(LABELS.degradedTooltip);
  });

  it("Técnico: el mismo `degraded=true` NO muestra «~» ni tooltip -- el concepto de traza no existe para ese rol", () => {
    render(
      <SessionTaximeter role="tecnico" costUsd={0.0214} totalTokens={48100} degraded={true} labels={LABELS} />,
    );
    expect(screen.getByText("USD 0,0214")).toBeTruthy();
    expect(screen.queryByText("~USD 0,0214")).toBeNull();
    const status = screen.getByRole("status");
    expect(status.getAttribute("data-tip")).toBeNull();
  });

  it("Admin sin degradación no muestra «~» ni data-tip", () => {
    render(
      <SessionTaximeter role="admin" costUsd={0.0214} totalTokens={48100} degraded={false} labels={LABELS} />,
    );
    expect(screen.getByText("USD 0,0214")).toBeTruthy();
    const status = screen.getByRole("status");
    expect(status.getAttribute("data-tip")).toBeNull();
  });
});
