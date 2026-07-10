"use client";

import { Tag } from "@/components/ui/tag";
import { Tooltip } from "@/components/ui/tooltip";
import type { TurnTelemetry } from "@/lib/chat/types";

export interface AlternateModelTagLabels {
  /** Texto visible del tag corto ("modelo alterno", `design/VISTAS/02-chat.md`
   * vista 05 §0.2.5, clave i18n `chat.tag.alt_model` de las notas i18n de
   * esa vista). */
  label: string;
  /** Explicación en lenguaje simple para Funcional -- texto EXACTO de la
   * vista 05 ("Tooltip Funcional: «Esta respuesta la generó un modelo
   * alternativo porque el habitual no estaba disponible. La calidad puede
   * variar.»"). Nunca menciona el nombre del perfil. */
  funcionalExplanation: string;
  /** Prefijo para armar `"${profilePrefix} ${model_profile_id}"` en el
   * detalle de Técnico/Admin (tarea 5.1: "al hover/expandir muestra
   * `telemetry.model_profile_id`"). */
  profilePrefix: string;
  /** Prefijo para `"${reasonPrefix} ${fallback_reason}"`, agregado solo si
   * `fallback_reason` viene poblado (vista 06 §Datos: "tooltip «fallback
   * desde deepseek-v4-flash: proveedor caído 14:31»"). */
  reasonPrefix: string;
}

export interface AlternateModelTagProps {
  /** `turn_metadata.is_alternate_model` (tarea 5.1) -- presente y booleano
   * para LOS TRES roles (`layer_turn_metadata`, ver
   * `resultarai/app/use_cases/chat/telemetry.py`: "Siempre presentes, para
   * los tres roles [...] `is_alternate_model`"): el backend nunca omite
   * esta clave, así que acá no hace falta ningún chequeo de rol para
   * decidir SI se muestra el tag -- solo para decidir cuánto detalle trae. */
  isAlternateModel: boolean;
  /** Telemetría del turno -- SOLO presente para Técnico/Admin (decisión 7
   * de `design.md`, misma señal de "ausencia decide" que usa
   * `TurnTelemetryRow`). Para Funcional esta prop llega `undefined`: el
   * nombre del perfil ni siquiera existe en los datos que recibe este
   * componente -- no hace falta filtrarlo a mano ni leer el rol, la
   * ausencia ya lo decide (mismo criterio que pide el enunciado de la
   * tarea 5.1). */
  telemetry?: TurnTelemetry;
  labels: AlternateModelTagLabels;
}

/**
 * Etiqueta "modelo alterno" (tarea 5.1 de d13-chat-conversacion,
 * `design/VISTAS/02-chat.md` vista 05 §0.2.5 y vista 06 §Datos): visible
 * para TODOS los roles cuando el turno respondió con un perfil de fallback
 * distinto al primario de la cascada del agente. Funcional ve el tag con
 * una explicación en lenguaje simple, sin el nombre del perfil; Técnico/
 * Admin ven además `model_profile_id` (y `fallback_reason` si está
 * disponible) en el detalle accesible del tag.
 *
 * El detalle usa el mismo patrón que `SessionTaximeter` (degradado): un
 * `Tooltip` (`data-tip`, visible en hover/focus-visible del hijo) MÁS un
 * `aria-label` explícito sobre el `Tag` -- `Tag` es un `<span>` estático
 * (no enfocable, ver su docstring), así que el `aria-label` es lo que
 * garantiza que el detalle quede accesible sin depender solo del hover
 * (design/DESIGN-SYSTEM.md §8.10: "el tooltip complementa, no sustituye").
 */
export function AlternateModelTag({ isAlternateModel, telemetry, labels }: AlternateModelTagProps) {
  if (!isAlternateModel) return null;

  if (!telemetry) {
    return (
      <Tooltip label={labels.funcionalExplanation}>
        <Tag variant="warn" aria-label={labels.funcionalExplanation}>
          {labels.label}
        </Tag>
      </Tooltip>
    );
  }

  const detailParts = [
    telemetry.model_profile_id ? `${labels.profilePrefix} ${telemetry.model_profile_id}` : null,
    telemetry.fallback_reason ? `${labels.reasonPrefix} ${telemetry.fallback_reason}` : null,
  ].filter((part): part is string => part !== null);

  if (detailParts.length === 0) {
    return <Tag variant="warn">{labels.label}</Tag>;
  }

  const detail = detailParts.join(" — ");
  return (
    <Tooltip label={detail}>
      <Tag variant="warn" aria-label={`${labels.label}. ${detail}`}>
        {labels.label}
      </Tag>
    </Tooltip>
  );
}
