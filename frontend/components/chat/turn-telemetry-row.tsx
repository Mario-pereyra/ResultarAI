"use client";

import { Fragment, type ReactNode } from "react";
import { Tag } from "@/components/ui/tag";
import { formatCompactNumberBO, formatLatencySecondsBO, formatLlmCostBO } from "@/lib/format-bo";
import type { TurnTelemetry } from "@/lib/chat/types";

export interface TurnTelemetryLabels {
  cacheHit: string;
  cacheMiss: string;
  cacheWrite: string;
  /** Nombre accesible del chip HIT: `${prefix} {tokens} ${suffix}` (nunca
   * ICU con placeholders -- los tokens son dinámicos por turno, ver
   * `openspec/BACKLOG-DESCUBRIMIENTOS.md`). */
  cacheHitAriaLabelPrefix: string;
  cacheHitAriaLabelSuffix: string;
  cacheMissAriaLabelPrefix: string;
  cacheMissAriaLabelSuffix: string;
  cacheWriteAriaLabelPrefix: string;
  cacheWriteAriaLabelSuffix: string;
  cacheHitTooltip: string;
  cacheMissTooltip: string;
  cacheWriteTooltip: string;
  viewTrace: string;
  viewTraceAriaLabel: string;
}

export interface TurnTelemetryRowProps {
  telemetry: TurnTelemetry;
  labels: TurnTelemetryLabels;
}

/**
 * Fila de telemetría por turno (tareas 4.2/4.3 de d13-chat-conversacion,
 * `design/VISTAS/02-chat.md` vista 06 §2): se inserta DENTRO de `.msg-meta`
 * -- "la fila de telemetría se agrega a la misma fila de metadatos del
 * turno [...], no es un panel aparte" -- nunca en un contenedor propio.
 *
 * Decisión 7 de `design.md`: este componente NO recibe ni consulta el rol.
 * El backend ya filtró `telemetry` completo para Funcional (la clave ni
 * siquiera existe en el JSON, ver `resultarai/app/use_cases/chat/telemetry.py`)
 * y `trace_id` para Técnico (nunca viaja en su `telemetry`) -- acá cada
 * pieza se renderiza según la PRESENCIA del dato correspondiente:
 *
 * - **"ver traza" (tarea 4.3):** solo si `telemetry.trace_id` está presente
 *   -- en la práctica, solo Admin. El `href` es un placeholder documentado
 *   (`#traza-{trace_id}`): la consola de trazas real llega en `d19` (sin
 *   URL definida todavía en la vista 06 ni en el blueprint -- anotado en
 *   `openspec/BACKLOG-DESCUBRIMIENTOS.md`). No se abre en pestaña nueva
 *   (vista 06 pide "nueva pestaña", pero un ancla local sin destino real lo
 *   haría confuso) -- `d19` debe ajustar `target`/`rel` cuando exista la URL
 *   real.
 * - **Chip `WRITE` (`cache_write_tokens`):** omitido por completo mientras
 *   sea `null` -- hoy SIEMPRE lo es (hueco de `b05-gateway-modelos` ya
 *   anotado en `telemetry.py` y en `openspec/BACKLOG-DESCUBRIMIENTOS.md`).
 *   Se decidió omitir en vez de mostrar un chip sin número: un chip "WRITE"
 *   vacío sugeriría un dato roto, no un dato pendiente -- coherente con la
 *   vista 06 ("nunca skeleton de chips: llegan con el turno").
 */
export function TurnTelemetryRow({ telemetry, labels }: TurnTelemetryRowProps) {
  const parts: ReactNode[] = [];

  if (telemetry.latency_ms != null) {
    parts.push(<span>{formatLatencySecondsBO(telemetry.latency_ms)}</span>);
  }

  if (telemetry.model_profile_id != null) {
    parts.push(<Tag outline>{telemetry.model_profile_id}</Tag>);
  }

  if (telemetry.cache_hit_tokens != null) {
    const tokens = formatCompactNumberBO(telemetry.cache_hit_tokens);
    parts.push(
      <span
        className="chip-cache chip-cache--hit"
        data-tip={labels.cacheHitTooltip}
        aria-label={`${labels.cacheHitAriaLabelPrefix} ${tokens} ${labels.cacheHitAriaLabelSuffix}`}
      >
        {labels.cacheHit} · {tokens}
      </span>,
    );
  }

  if (telemetry.cache_miss_tokens != null) {
    const tokens = formatCompactNumberBO(telemetry.cache_miss_tokens);
    parts.push(
      <span
        className="chip-cache chip-cache--miss"
        data-tip={labels.cacheMissTooltip}
        aria-label={`${labels.cacheMissAriaLabelPrefix} ${tokens} ${labels.cacheMissAriaLabelSuffix}`}
      >
        {labels.cacheMiss} · {tokens}
      </span>,
    );
  }

  if (telemetry.cache_write_tokens != null) {
    const tokens = formatCompactNumberBO(telemetry.cache_write_tokens);
    parts.push(
      <span
        className="chip-cache chip-cache--write"
        data-tip={labels.cacheWriteTooltip}
        aria-label={`${labels.cacheWriteAriaLabelPrefix} ${tokens} ${labels.cacheWriteAriaLabelSuffix}`}
      >
        {labels.cacheWrite} · {tokens}
      </span>,
    );
  }

  if (telemetry.cost_usd != null) {
    parts.push(<span className="msg-meta__cost">{formatLlmCostBO(telemetry.cost_usd)}</span>);
  }

  if (telemetry.trace_id) {
    parts.push(
      <a href={`#traza-${telemetry.trace_id}`} aria-label={labels.viewTraceAriaLabel}>
        {labels.viewTrace}
      </a>,
    );
  }

  if (parts.length === 0) return null;

  return (
    <>
      {parts.map((part, index) => (
        <Fragment key={index}>
          <span aria-hidden="true">·</span>
          {part}
        </Fragment>
      ))}
    </>
  );
}
