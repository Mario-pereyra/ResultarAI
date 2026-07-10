"use client";

export interface ActivityIndicatorLabels {
  /** Texto genérico mostrado mientras no hay un `detail` más específico
   * ("Consultando…", vista 05: "sin detalle técnico" para el rol Funcional). */
  consulting: string;
}

export interface ActivityIndicatorProps {
  labels: ActivityIndicatorLabels;
  /**
   * Descripción puntual de la actividad en curso (p. ej. "Consultando TDN…").
   * Sin `detail`, se usa `labels.consulting` (tarea 3.3: la línea de
   * actividad plegada previa a la respuesta, todavía sin tool calls reales).
   * La tarea 5.2 (`c09-mcp-tools`, contrato `tool-call-visibility`) puebla
   * este campo con la descripción en lenguaje simple de cada tool call
   * ejecutada -- este componente ya expone el punto de extensión sin que
   * 5.2 tenga que reescribirlo.
   */
  detail?: string;
}

/**
 * Línea de actividad plegada (d13-chat-conversacion, tarea 3.3,
 * `design/VISTAS/02-chat.md` vista 05: "Línea de actividad de tools
 * plegada: «consultando TDN…» (spinner pequeño), sin detalle técnico").
 * Puramente presentacional: `message-column.tsx` decide CUÁNDO mostrarla
 * (turno en streaming sin texto todavía).
 */
export function ActivityIndicator({ labels, detail }: ActivityIndicatorProps) {
  return (
    <div className="chat-activity" role="status">
      <span className="chat-activity__spinner" aria-hidden="true" />
      <span>{detail ?? labels.consulting}</span>
    </div>
  );
}
