"use client";

import { useEffect, useId, useRef, useState, type KeyboardEvent as ReactKeyboardEvent } from "react";
import type { Role } from "@/lib/session-context";
import { SessionTaximeter, type SessionTaximeterLabels } from "./session-taximeter";

export interface ChatHeaderLabels {
  /** Nombre accesible del botón "⋯" que colapsa el taxímetro a un menú de
   * sesión en móvil (`aria-label` del disparador Y del panel que controla
   * vía `aria-controls` -- mismo elemento conceptual, un solo texto). */
  sessionMenuLabel: string;
}

export interface ChatHeaderProps {
  /** `agent.display_name` (vista 05 §Datos que muestra) -- ver el
   * docstring del componente para el hueco de `agent.icon`/
   * `agent.short_description`. */
  agentName: string;
  /** Rol de la sesión de identidad -- decide SOLO la visibilidad del
   * taxímetro y del menú de sesión (mismo criterio que
   * `SessionTaximeter.role`: capa de conveniencia de UI, la seguridad real
   * ya la aplicó el backend en `telemetry.py`). */
  role: Role;
  costUsd: number;
  totalTokens: number;
  degraded: boolean;
  taximeterLabels: SessionTaximeterLabels;
  labels: ChatHeaderLabels;
}

/**
 * Header del chat ("chat-top", `design/VISTAS/02-chat.md` vista 05 §0.1
 * "Anatomía común" / vista 06 §2 y §Móvil). Cierra el hueco documentado en
 * `openspec/BACKLOG-DESCUBRIMIENTOS.md` (2026-07-10, tareas 4.2/4.3/4.4):
 * `chat-content.tsx` nunca construyó el `chat-top` real, solo un slot
 * mínimo (`.chat-taximeter-bar`) para el taxímetro. Este componente lo
 * reemplaza por completo.
 *
 * CAMPOS DEL HEADER -- vista 05 §Datos que muestra ("campos exactos"):
 * "Header: `agent.icon`, `agent.display_name`, `agent.short_description`".
 * De esos tres, hoy solo `agent.display_name` tiene dato real disponible
 * del lado del cliente (`GET /api/agents/{id}`, `chat-content.tsx`):
 * - `agent.icon`: ningún endpoint expone un ícono por agente. Se reutiliza
 *   el mismo glifo 🤖 que ya usa cada mensaje del agente (`.msg-avatar` en
 *   `message-column.tsx`) -- no se inventa un ícono nuevo.
 * - `agent.short_description`: `AgentSummaryResponse`
 *   (`resultarai/app/api/chat.py`) solo expone `id`/`name`/
 *   `starter_prompts`/`escalation_enabled` -- sin `short_description`. Por
 *   regla de este trabajo (SOLO frontend, sin tocar `resultarai/`), no se
 *   fabrica ese texto: se omite. Documentado como hueco de backend.
 *
 * TÍTULO DE SESIÓN: deliberadamente AUSENTE de este header. La vista 05
 * lista los campos EXACTOS de arriba y no incluye ningún título de sesión;
 * `session.auto_title` vive en la vista 12 (historial, editable ahí con
 * lápiz) y el layout de la vista 06 tampoco lo agrega
 * (`[🤖] DocAgent — …  [SESIÓN USD 0,0214 · 48,1k]`, sin título). Se sigue
 * la vista al pie de la letra.
 *
 * TAXÍMETRO EN MÓVIL (vista 06 §Móvil: "el taxímetro sale del header y vive
 * en el menú de sesión (⋯)", DS §8.12): en vez de montar DOS instancias de
 * `SessionTaximeter` (una inline para desktop + una en el panel móvil, lo
 * que duplicaría `role="status"` y rompería los `getByRole("status",
 * {name...})` -- singulares -- ya existentes en `chat-content.test.tsx`),
 * se monta UNA SOLA instancia dentro de `.chat-top__menu-panel`. Ese mismo
 * nodo sirve de contenido INLINE en desktop (`display: flex` por defecto,
 * `styles/components/chat.css`) y de contenido del popover en móvil
 * (`display: none` hasta que el disparador agrega `.is-open`) -- "dual-
 * render + CSS decide" (mismo patrón que `.history-toolbar__search`), sin
 * duplicar el dato ni su nodo accesible.
 *
 * El panel NO es un menú de acciones (el taxímetro no es accionable): es un
 * disclosure simple (botón `aria-expanded`/`aria-controls` + panel hermano
 * sin `role="menu"`), no el componente `Dropdown` genérico
 * (`components/ui/dropdown.tsx`, pensado para listas de `DropdownItem`
 * accionables con navegación por flechas).
 *
 * El botón "⋯" solo se monta para Técnico/Admin -- Funcional no tiene
 * taxímetro que ocultar (DS §9.7: "lo que un rol no tiene, no se
 * renderiza"), así que no hay nada detrás del menú.
 */
export function ChatHeader({
  agentName,
  role,
  costUsd,
  totalTokens,
  degraded,
  taximeterLabels,
  labels,
}: ChatHeaderProps) {
  const showTaximeter = role === "tecnico" || role === "admin";
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);
  const triggerRef = useRef<HTMLButtonElement>(null);
  const panelId = useId();

  // Click afuera del disparador/panel cierra sin devolver el foco -- mismo
  // criterio que `components/ui/dropdown.tsx` (DS §8.21).
  useEffect(() => {
    if (!open) return;
    function handlePointerDown(event: MouseEvent) {
      if (!rootRef.current?.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("mousedown", handlePointerDown);
    return () => document.removeEventListener("mousedown", handlePointerDown);
  }, [open]);

  function handleKeyDown(event: ReactKeyboardEvent<HTMLDivElement>) {
    if (event.key === "Escape") {
      event.preventDefault();
      setOpen(false);
      triggerRef.current?.focus();
    }
  }

  return (
    <div className="chat-top">
      <div className="chat-top__identity">
        <span className="chat-top__avatar" aria-hidden="true">
          🤖
        </span>
        <span className="chat-top__name">{agentName}</span>
      </div>
      {showTaximeter ? (
        <div className="chat-top__menu" ref={rootRef} onKeyDown={handleKeyDown}>
          <button
            type="button"
            ref={triggerRef}
            className="chat-top__menu-trigger"
            aria-haspopup="true"
            aria-expanded={open}
            aria-controls={panelId}
            aria-label={labels.sessionMenuLabel}
            onClick={() => setOpen((value) => !value)}
          >
            <span aria-hidden="true">⋯</span>
          </button>
          <div
            id={panelId}
            className={open ? "chat-top__menu-panel is-open" : "chat-top__menu-panel"}
          >
            <SessionTaximeter
              role={role}
              costUsd={costUsd}
              totalTokens={totalTokens}
              degraded={degraded}
              labels={taximeterLabels}
            />
          </div>
        </div>
      ) : null}
    </div>
  );
}
