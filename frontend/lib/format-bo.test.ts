import { describe, expect, it } from "vitest";
import {
  formatAggregatedAmountBO,
  formatCompactNumberBO,
  formatDateBO,
  formatDateTimeBO,
  formatLatencySecondsBO,
  formatLlmCostBO,
  formatPercentBO,
  formatTokensBO,
} from "./format-bo";

/**
 * Escenario "Formato de fecha en es-BO" (specs/i18n-foundation/spec.md):
 * fecha-hora de ejemplo formateada `dd/mm/aaaa HH:mm` (24 h) vía
 * `Intl.DateTimeFormat` con locale `es-BO`. Se usa la misma fecha de
 * ejemplo que design/DESIGN-SYSTEM.md §9.8 (`11/06/2026 14:32`).
 */
const SAMPLE_DATE = new Date(2026, 5, 11, 14, 32);

describe("format-bo — formatos es-BO de design/DESIGN-SYSTEM.md §9.8 (tarea 6.3)", () => {
  it('escenario "Formato de fecha en es-BO": dd/mm/aaaa', () => {
    expect(formatDateBO(SAMPLE_DATE)).toBe("11/06/2026");
  });

  it('escenario "Formato de fecha en es-BO": dd/mm/aaaa HH:mm (24h)', () => {
    expect(formatDateTimeBO(SAMPLE_DATE)).toBe("11/06/2026 14:32");
  });

  it("costo LLM: USD + 4 decimales, coma decimal", () => {
    expect(formatLlmCostBO(0.0042)).toBe("USD 0,0042");
  });

  it("monto agregado: USD + 2 decimales, separador de miles con punto", () => {
    expect(formatAggregatedAmountBO(1284.5)).toBe("USD 1.284,50");
  });

  it("porcentaje: sin espacio antes de %", () => {
    expect(formatPercentBO(0.82)).toBe("82%");
  });

  it("tokens abreviados: k/M con 1 decimal, sin espacio antes de la unidad", () => {
    expect(formatTokensBO(12400)).toBe("12,4k tok");
    expect(formatTokensBO(820)).toBe("820 tok");
  });

  it("número abreviado (tareas 4.2/4.3, chips de cache): siempre minúscula, incluso en el escalón de millar (1.000-9.999) donde el CLDR de es-BO devuelve mayúscula", () => {
    // Desvío documentado en el docstring de `formatCompactNumberBO`: el
    // CLDR de `Intl` produce "1,8 K" (mayúscula) para este escalón y
    // "41,2 k" (minúscula) para el escalón siguiente -- normalizado acá.
    expect(formatCompactNumberBO(1800)).toBe("1,8k");
    expect(formatCompactNumberBO(41200)).toBe("41,2k");
    expect(formatCompactNumberBO(900)).toBe("900");
  });

  it("latencia de turno: segundos con 1 decimal, coma decimal (vista 06)", () => {
    expect(formatLatencySecondsBO(3200)).toBe("3,2 s");
  });
});
