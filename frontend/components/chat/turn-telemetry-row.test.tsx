import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import type { TurnTelemetry } from "@/lib/chat/types";
import { TurnTelemetryRow, type TurnTelemetryLabels } from "./turn-telemetry-row";

/**
 * Tareas 4.2/4.3 de d13-chat-conversacion (`design/VISTAS/02-chat.md`
 * vista 06 §2): fila de telemetría por turno -- costo, perfil, latencia,
 * chips de cache, y el enlace "ver traza" (solo cuando `trace_id` está
 * presente, tarea 4.3).
 */

const LABELS: TurnTelemetryLabels = {
  cacheHit: "HIT",
  cacheMiss: "MISS",
  cacheWrite: "WRITE",
  cacheHitAriaLabelPrefix: "cache hit,",
  cacheHitAriaLabelSuffix: "tokens cacheados",
  cacheMissAriaLabelPrefix: "cache miss,",
  cacheMissAriaLabelSuffix: "tokens sin cache",
  cacheWriteAriaLabelPrefix: "prefijo escrito al cache,",
  cacheWriteAriaLabelSuffix: "tokens",
  cacheHitTooltip: "prefijo servido desde cache: ahorro ~90% en esos tokens",
  cacheMissTooltip: "tokens procesados sin cache (primera vez)",
  cacheWriteTooltip: "prefijo escrito al cache para los próximos turnos",
  viewTrace: "ver traza",
  viewTraceAriaLabel: "Ver traza de este turno en Langfuse",
};

/** Simula la telemetría tal como la arma el backend para Técnico: mismo
 * turno, pero sin `trace_id` (`layer_turn_metadata` nunca lo agrega salvo
 * rol admin). */
function withoutTraceId(telemetry: TurnTelemetry): TurnTelemetry {
  const copy = { ...telemetry };
  delete copy.trace_id;
  return copy;
}

const FULL_TELEMETRY: TurnTelemetry = {
  cost_usd: 0.0042,
  model_profile_id: "deepseek-v4-flash",
  primary_model_profile_id: "deepseek-v4-flash",
  fallback_reason: null,
  latency_ms: 3200,
  cache_hit_tokens: 41200,
  cache_miss_tokens: 1800,
  cache_write_tokens: null,
  trace_id: "trace-abc",
};

describe("TurnTelemetryRow — costo, perfil, latencia y chips de cache (tarea 4.2)", () => {
  it("renderiza latencia, perfil, chips HIT/MISS y costo", () => {
    render(<TurnTelemetryRow telemetry={FULL_TELEMETRY} labels={LABELS} />);
    expect(screen.getByText("3,2 s")).toBeTruthy();
    expect(screen.getByText("deepseek-v4-flash")).toBeTruthy();
    expect(screen.getByText("HIT · 41,2k")).toBeTruthy();
    expect(screen.getByText("MISS · 1,8k")).toBeTruthy();
    expect(screen.getByText("USD 0,0042")).toBeTruthy();
  });

  it("omite el chip WRITE cuando `cache_write_tokens` es null (hueco de b05, documentado)", () => {
    render(<TurnTelemetryRow telemetry={FULL_TELEMETRY} labels={LABELS} />);
    expect(screen.queryByText(/^WRITE/)).toBeNull();
  });

  it("muestra el chip WRITE cuando el dato está disponible", () => {
    render(
      <TurnTelemetryRow
        telemetry={{ ...FULL_TELEMETRY, cache_write_tokens: 43500 }}
        labels={LABELS}
      />,
    );
    expect(screen.getByText("WRITE · 43,5k")).toBeTruthy();
  });

  it("no renderiza nada si la telemetría no trae ningún dato poblado", () => {
    const { container } = render(
      <TurnTelemetryRow
        telemetry={{
          cost_usd: null,
          model_profile_id: null,
          primary_model_profile_id: null,
          fallback_reason: null,
          latency_ms: null,
          cache_hit_tokens: null,
          cache_miss_tokens: null,
          cache_write_tokens: null,
        }}
        labels={LABELS}
      />,
    );
    expect(container.firstChild).toBeNull();
  });
});

describe('TurnTelemetryRow — enlace "ver traza" solo con `trace_id` presente (tarea 4.3)', () => {
  it("Admin (trace_id presente): el enlace «ver traza» está presente", () => {
    render(<TurnTelemetryRow telemetry={FULL_TELEMETRY} labels={LABELS} />);
    const link = screen.getByRole("link", { name: LABELS.viewTraceAriaLabel });
    expect(link).toBeTruthy();
    expect(link.getAttribute("href")).toBe("#traza-trace-abc");
    expect(screen.getByText("ver traza")).toBeTruthy();
  });

  it("Técnico (trace_id ausente): el enlace «ver traza» NO se renderiza", () => {
    render(<TurnTelemetryRow telemetry={withoutTraceId(FULL_TELEMETRY)} labels={LABELS} />);
    expect(screen.queryByText("ver traza")).toBeNull();
    expect(screen.queryByRole("link")).toBeNull();
  });
});
