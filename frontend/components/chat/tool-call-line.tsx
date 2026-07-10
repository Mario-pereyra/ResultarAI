"use client";

import { useState } from "react";
import { formatLatencySecondsBO } from "@/lib/format-bo";
import type { VisibleToolCallView } from "@/lib/chat/types";
import type { Role } from "@/lib/session-context";

export interface ToolCallLineLabels {
  /** Encabezado del bloque de parámetros completos (Técnico/Admin, ej. "Parámetros"). */
  parametersLabel: string;
  /** Prefijo de la línea de latencia (Técnico/Admin, ej. "Latencia:"). */
  latencyLabel: string;
}

export interface ToolCallLineProps {
  /** Espejo de `VisibleToolCallView` (contrato `tool-call-visibility` de
   * c09-mcp-tools) -- ver su docstring en `lib/chat/types.ts` para el
   * detalle de qué campo viaja filtrado por rol y cuál no. */
  call: VisibleToolCallView;
  /**
   * Rol de la sesión de identidad. A diferencia de `TurnTelemetryRow`
   * (decisión 7 de `design.md`: gatea SOLO por presencia del dato, nunca
   * por rol), acá SÍ hace falta un chequeo de rol explícito para la
   * latencia: `call.duration_ms` viaja poblado para TODOS los roles en el
   * contrato de c09 (ver el docstring de `VisibleToolCallView`), así que
   * la capa "latencia solo Técnico/Admin" del requirement `chat-experience`
   * "Tool calls colapsadas y expandibles por capa de rol" no la puede
   * decidir la AUSENCIA del dato -- la aplica este componente. `parameters`
   * en cambio ya viaja `null` para Funcional server-side (`render_for_role`);
   * el chequeo de rol de acá es además-de, no en-lugar-de esa ausencia
   * (defensa en profundidad: aunque `call.parameters` viniera poblado por
   * error, Funcional nunca lo ve).
   */
  role: Role;
  labels: ToolCallLineLabels;
}

/**
 * Tool call colapsada/expandible (tarea 5.2 de d13-chat-conversacion,
 * contrato `tool-call-visibility` de c09-mcp-tools --
 * `resultarai/core/audit/visibility.py`). Colapsada por defecto
 * (`collapsed_by_default` del backend, `design/VISTAS/02-chat.md` vista 05
 * §0.2.7): el disparador muestra el nombre de la Tool y su estado de
 * gobernanza (`status_label`, ya coherente con `escalate_hitl`/`deny` --
 * una escritura escalada nunca se etiqueta "ejecutada", ver el requirement
 * de c09 "Estado de gobernanza reflejado en el registro visible") -- texto
 * corto, en lenguaje simple, igual para los tres roles.
 *
 * Al expandir (`aria-expanded`, `<button>` nativo -- Enter/Espacio ya
 * alternan el estado sin manejo de teclado propio):
 *
 * - **Todos los roles:** `call.simple_description` -- lenguaje simple que
 *   YA incluye el resultado truncado por el backend (`result_truncated`/
 *   `_TRUNCATION_SUFFIX` de `visibility.py`), sin parámetros técnicos (c09,
 *   escenario "Funcional ve la tool call en lenguaje simple").
 * - **Técnico/Admin además:** `call.parameters` completos (JSON legible) y
 *   `call.duration_ms` (latencia) -- ver el gateo por `role` en la prop de
 *   arriba (c09, escenario "Técnico y Admin ven parámetros completos").
 */
export function ToolCallLine({ call, role, labels }: ToolCallLineProps) {
  const [expanded, setExpanded] = useState(false);
  const isTechnicalRole = role === "tecnico" || role === "admin";

  return (
    <div className="tool-call-line">
      <button
        type="button"
        className="tool-call-line__trigger"
        aria-expanded={expanded}
        onClick={() => setExpanded((previous) => !previous)}
      >
        <span className="tool-call-line__icon" aria-hidden="true">
          🔧
        </span>
        <span>
          {call.tool_name} · {call.status_label}
        </span>
        <span className="tool-call-line__chevron" aria-hidden="true">
          ›
        </span>
      </button>
      {expanded ? (
        <div className="tool-call-line__detail">
          <p className="tool-call-line__result">{call.simple_description}</p>
          {isTechnicalRole && call.parameters ? (
            <div>
              <p className="tool-call-line__params-label">{labels.parametersLabel}</p>
              <pre className="tool-call-line__params">{JSON.stringify(call.parameters, null, 2)}</pre>
            </div>
          ) : null}
          {isTechnicalRole && call.duration_ms != null ? (
            <p className="tool-call-line__latency">
              {labels.latencyLabel} {formatLatencySecondsBO(call.duration_ms)}
            </p>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
