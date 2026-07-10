import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import type { TurnTelemetry } from "@/lib/chat/types";
import { AlternateModelTag, type AlternateModelTagLabels } from "./alternate-model-tag";

/**
 * Tarea 5.1 de d13-chat-conversacion (`design/VISTAS/02-chat.md` vista 05
 * §0.2.5 y vista 06 §Datos): etiqueta "modelo alterno" visible para TODOS
 * los roles, con explicación simple para Funcional y nombre del perfil
 * accesible además para Técnico/Admin.
 */

const LABELS: AlternateModelTagLabels = {
  label: "modelo alterno",
  funcionalExplanation:
    "Esta respuesta la generó un modelo alternativo porque el habitual no estaba disponible. La calidad puede variar.",
  profilePrefix: "Perfil:",
  reasonPrefix: "Motivo:",
};

/** Telemetría tal como la arma `layer_turn_metadata` para Técnico/Admin
 * (`resultarai/app/use_cases/chat/telemetry.py`) en un turno de fallback. */
const TECHNICAL_TELEMETRY: TurnTelemetry = {
  cost_usd: 0.0042,
  model_profile_id: "kimi-k2.6",
  primary_model_profile_id: "deepseek-v4-flash",
  fallback_reason: "proveedor caído 14:31",
  latency_ms: 3200,
  cache_hit_tokens: null,
  cache_miss_tokens: null,
  cache_write_tokens: null,
};

describe("AlternateModelTag — turno normal (tarea 5.1)", () => {
  it("no renderiza nada cuando el turno no usó modelo alterno", () => {
    const { container } = render(<AlternateModelTag isAlternateModel={false} labels={LABELS} />);
    expect(container.firstChild).toBeNull();
  });

  it("tampoco renderiza nada con telemetría presente si is_alternate_model es false", () => {
    const { container } = render(
      <AlternateModelTag isAlternateModel={false} telemetry={TECHNICAL_TELEMETRY} labels={LABELS} />,
    );
    expect(container.firstChild).toBeNull();
  });
});

describe("AlternateModelTag — Funcional: datos sin telemetry (tarea 5.1)", () => {
  it("muestra el tag con texto simple, sin el nombre del perfil en ningún atributo del DOM", () => {
    render(<AlternateModelTag isAlternateModel labels={LABELS} />);

    const tag = screen.getByText("modelo alterno");
    expect(tag).toBeTruthy();
    expect(tag.getAttribute("data-tip")).toBe(LABELS.funcionalExplanation);
    expect(tag.getAttribute("aria-label")).toBe(LABELS.funcionalExplanation);
    expect(document.body.innerHTML).not.toContain("kimi-k2.6");
    expect(document.body.innerHTML).not.toContain("deepseek-v4-flash");
  });
});

describe("AlternateModelTag — Técnico/Admin: datos con telemetry (tarea 5.1)", () => {
  it("expone el nombre del perfil y el motivo del fallback en el detalle accesible del tag", () => {
    render(<AlternateModelTag isAlternateModel telemetry={TECHNICAL_TELEMETRY} labels={LABELS} />);

    const tag = screen.getByText("modelo alterno");
    expect(tag.getAttribute("data-tip")).toContain("kimi-k2.6");
    expect(tag.getAttribute("data-tip")).toContain("proveedor caído 14:31");
    expect(tag.getAttribute("aria-label")).toContain("kimi-k2.6");
  });

  it("sin fallback_reason: igual expone el perfil, sin motivo", () => {
    render(
      <AlternateModelTag
        isAlternateModel
        telemetry={{ ...TECHNICAL_TELEMETRY, fallback_reason: null }}
        labels={LABELS}
      />,
    );

    const tag = screen.getByText("modelo alterno");
    expect(tag.getAttribute("data-tip")).toContain("kimi-k2.6");
    expect(tag.getAttribute("data-tip")).not.toContain(LABELS.reasonPrefix);
  });
});
