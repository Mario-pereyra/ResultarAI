"use client";

import { Tooltip } from "@/components/ui/tooltip";
import { formatLlmCostBO, formatTokensBO } from "@/lib/format-bo";
import type { Role } from "@/lib/session-context";

export interface SessionTaximeterLabels {
  /** "Sesión" -- `.taximeter__label` (vista 06). */
  label: string;
  /** Prefijo del nombre accesible (`role="status"`): el componente arma
   * `${srLabelPrefix} ${costo}, ${tokens}` -- nunca ICU con placeholders
   * (`{cost}`/`{tokens}`), porque esos valores son dinámicos client-side y
   * `next-intl` exigiría resolverlos en el mismo `t(...)` server-side que
   * los arma (ver `openspec/BACKLOG-DESCUBRIMIENTOS.md`). */
  srLabelPrefix: string;
  /** Tooltip del estado degradado (tarea 4.4), solo Admin -- texto exacto de
   * `design/mockups/06-chat-admin.html` ("costo estimado, telemetría
   * diferida"). */
  degradedTooltip: string;
}

export interface SessionTaximeterProps {
  /** Rol de la sesión de identidad -- decide la visibilidad TOTAL (requirement
   * `chat-experience` "Capa de telemetría por turno para Técnico/Admin":
   * Funcional no la ve "en absoluto"). Se recibe como prop en vez de leer
   * `useSession()` acá adentro para que el componente quede puro/testeable
   * -- mismo criterio que `components/shell/gateway-error.tsx`. */
  role: Role;
  /** Suma acumulada de `telemetry.cost_usd` de los turnos de la rama visible
   * más el turno en curso recién cerrado (tarea 4.2) -- la calcula el
   * caller (`chat-content.tsx`, que ya posee el estado de mensajes; este
   * componente no agrega ningún store nuevo). */
  costUsd: number;
  /** Suma de tokens (hit + miss + write) de esos mismos turnos. */
  totalTokens: number;
  /**
   * Tarea 4.4: `true` si algún turno de la sesión no trae `telemetry.trace_id`
   * -- señal de "traza no disponible" elegida para este change (ver el
   * docstring de `turn-telemetry-row.tsx` para la justificación completa:
   * mismo campo que decide "ver traza" por turno, así que ambas tareas
   * quedan coherentes con una sola fuente de verdad). Sin efecto visual
   * salvo `role === "admin"`: para Técnico el concepto de traza no existe
   * (nunca ve `trace_id`, degradado o no) -- no es un hueco, la vista 06
   * marca "«ver traza»" con ✅ solo en la columna Admin.
   */
  degraded: boolean;
  labels: SessionTaximeterLabels;
}

/**
 * Taxímetro de sesión en el header del chat (tarea 4.2, `design/VISTAS/02-chat.md`
 * vista 06 §2, `.taximeter`). Ausencia total para Funcional (requirement
 * `chat-experience`): a diferencia de `TurnTelemetryRow`, acá no hay ningún
 * dato de turno cuya AUSENCIA determine la visibilidad en una sesión sin
 * turnos todavía (vista 06, estado "Vacío": "sesión nueva = taxímetro en
 * `USD 0,0000`" -- el taxímetro existe ANTES de que haya datos), así que la
 * decisión de render se toma explícitamente por `role`.
 */
export function SessionTaximeter({
  role,
  costUsd,
  totalTokens,
  degraded,
  labels,
}: SessionTaximeterProps) {
  if (role !== "tecnico" && role !== "admin") return null;

  const showDegraded = degraded && role === "admin";
  const costLabel = formatLlmCostBO(costUsd);
  const displayValue = showDegraded ? `~${costLabel}` : costLabel;
  const tokensLabel = formatTokensBO(totalTokens);
  const baseSrLabel = `${labels.srLabelPrefix} ${costLabel}, ${tokensLabel}`;
  // El tooltip solo se anuncia en hover/focus (`[data-tip]`, ver
  // `components/ui/tooltip.tsx`): se repite acá en el nombre accesible para
  // que quien use lector de pantalla no lo pierda.
  const srLabel = showDegraded ? `${labels.degradedTooltip}. ${baseSrLabel}` : baseSrLabel;

  const taximeter = (
    <div className="taximeter" role="status" aria-label={srLabel}>
      <span className="taximeter__label">{labels.label}</span>
      <span className="taximeter__value">{displayValue}</span>
      <span className="taximeter__detail">{tokensLabel}</span>
    </div>
  );

  if (!showDegraded) return taximeter;

  return <Tooltip label={labels.degradedTooltip}>{taximeter}</Tooltip>;
}
