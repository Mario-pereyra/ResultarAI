import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { GatewayError, type GatewayErrorLabels } from "./gateway-error";

const labels: GatewayErrorLabels = {
  funcionalTitle: "El asistente no está disponible",
  funcionalWhy: "Intentá de nuevo en unos minutos.",
  technicalTitle: "El servicio de IA no está disponible",
  technicalWhy: "El gateway del modelo no está respondiendo.",
  retry: "Reintentar",
  retrying: "Reintentando…",
};

/**
 * Escenario "Redacción del error se adapta al rol" (tarea 5.6,
 * specs/app-shell/spec.md).
 */
describe("GatewayError", () => {
  it("Funcional: lenguaje simple, sin el código GATEWAY_OFFLINE en ningún lado del DOM", () => {
    render(<GatewayError role="funcional" labels={labels} />);

    expect(screen.getByText(labels.funcionalTitle)).not.toBeNull();
    expect(screen.getByText(labels.funcionalWhy)).not.toBeNull();
    expect(screen.queryByText("GATEWAY_OFFLINE")).toBeNull();
  });

  it("Técnico: ve el código GATEWAY_OFFLINE y la redacción técnica", () => {
    render(<GatewayError role="tecnico" labels={labels} />);

    expect(screen.getByText("GATEWAY_OFFLINE")).not.toBeNull();
    expect(screen.getByText(labels.technicalTitle)).not.toBeNull();
    expect(screen.getByText(labels.technicalWhy)).not.toBeNull();
  });

  it("Admin: igual que Técnico, ve el código y el detalle técnico", () => {
    render(<GatewayError role="admin" labels={labels} />);

    expect(screen.getByText("GATEWAY_OFFLINE")).not.toBeNull();
    expect(screen.getByText(labels.technicalTitle)).not.toBeNull();
  });

  it('siempre expone role="alert" y la acción "Reintentar" (plantilla de errores accionables, DS §9.6)', () => {
    render(<GatewayError role="funcional" labels={labels} />);

    expect(screen.getByRole("alert")).not.toBeNull();
    expect(screen.getByRole("button", { name: "Reintentar" })).not.toBeNull();
  });
});
