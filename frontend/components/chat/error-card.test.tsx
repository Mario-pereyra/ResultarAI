import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ErrorCard, type ErrorCardLabels } from "./error-card";

/**
 * Tarea 6.3 (d13-chat-conversacion): redacción por rol de la tarjeta de
 * error, ejercitada directamente sobre el componente compartido
 * (`GatewayOfflineCard`/`QuotaCard` delegan TODA la redacción acá, ver sus
 * docstrings) -- cubre ambos códigos del subconjunto de la vista 10
 * (`GATEWAY_OFFLINE`/`QUOTA`) con la MISMA aserción, porque la redacción por
 * rol no depende del código, solo de `role`/`labels`.
 */
const GATEWAY_LABELS: ErrorCardLabels = {
  title: "El servicio de IA no está disponible",
  technicalWhy: "El proveedor no responde; reintento automático",
  funcionalWhy: "El asistente no está disponible en este momento",
  supportCodePrefix: "código para soporte:",
};

const QUOTA_LABELS: ErrorCardLabels = {
  title: "Alcanzaste tu cuota mensual",
  technicalWhy: "Tu límite de uso mensual se alcanzó.",
  funcionalWhy: "Alcanzaste tu límite de uso de este mes",
  supportCodePrefix: "código para soporte:",
};

describe.each([
  { code: "GATEWAY_OFFLINE", labels: GATEWAY_LABELS },
  { code: "QUOTA", labels: QUOTA_LABELS },
])("ErrorCard — código $code (tarea 6.3)", ({ code, labels }) => {
  it("Funcional: sin jerga, código en segundo plano como «código para soporte: X», nunca arriba", () => {
    render(<ErrorCard code={code} role="funcional" labels={labels} />);

    expect(screen.getByText(labels.title)).toBeTruthy();
    expect(screen.getByText(labels.funcionalWhy)).toBeTruthy();
    expect(screen.queryByText(labels.technicalWhy)).toBeNull();

    // El código NUNCA aparece "arriba" (mono, `.error-card__code`) -- solo
    // al pie, junto al prefijo de soporte.
    expect(screen.queryByText(code, { selector: ".error-card__code" })).toBeNull();
    expect(screen.getByText(`${labels.supportCodePrefix} ${code}`)).toBeTruthy();
  });

  it("Técnico: código mono visible arriba, redacción técnica, sin el pie de soporte", () => {
    render(<ErrorCard code={code} role="tecnico" labels={labels} />);

    expect(screen.getByText(labels.title)).toBeTruthy();
    expect(screen.getByText(labels.technicalWhy)).toBeTruthy();
    expect(screen.queryByText(labels.funcionalWhy)).toBeNull();

    expect(screen.getByText(code, { selector: ".error-card__code" })).toBeTruthy();
    expect(screen.queryByText(`${labels.supportCodePrefix} ${code}`)).toBeNull();
  });

  it("Admin: igual que Técnico -- código mono arriba y redacción técnica", () => {
    render(<ErrorCard code={code} role="admin" labels={labels} />);

    expect(screen.getByText(code, { selector: ".error-card__code" })).toBeTruthy();
    expect(screen.getByText(labels.technicalWhy)).toBeTruthy();
    expect(screen.queryByText(`${labels.supportCodePrefix} ${code}`)).toBeNull();
  });

  it('expone role="alert" (anatomía obligatoria qué-pasó/por-qué/qué-hacer, DS §8.16/§9.6)', () => {
    render(<ErrorCard code={code} role="funcional" labels={labels} />);
    expect(screen.getByRole("alert")).toBeTruthy();
  });
});
