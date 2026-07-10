"use client";

import { forwardRef, useImperativeHandle, useRef } from "react";
import { Dropdown, type DropdownItem } from "@/components/ui/dropdown";

export interface HistoryRowActionsLabels {
  /** `aria-label` del disparador "⋮" -- fallback accesible SIEMPRE presente
   * en móvil (vista 12 §Móvil: "acciones en menú ⋯ (long-press)"). Un tap
   * directo sobre este botón abre el menú sin depender del temporizador de
   * long-press, así que el mecanismo es igual de operable con
   * mouse/teclado/lector de pantalla que con press-and-hold táctil -- ver
   * el docstring completo más abajo. */
  menuLabel: string;
  /** Ítem de menú "Retomar" -- ver la nota de alcance del docstring de
   * `HistoryRowActions` sobre por qué es la ÚNICA acción hoy. */
  resume: string;
}

export interface HistoryRowActionsHandle {
  /**
   * Abre el menú programáticamente. Lo usa el long-press de la fila
   * COMPLETA (`HistoryTableRow`, `app/(shell)/chat/history-row.tsx`, tarea
   * 8.2): en vez de ensanchar la API pública de `Dropdown`
   * (`components/ui/dropdown.tsx`, compartido también por la campana y el
   * menú de usuario del shell) con un modo de apertura controlada que solo
   * esta vista necesita, se simula un click real sobre EL PROPIO
   * disparador (`.dropdown__trigger`) -- el mismo gesto que dispararía un
   * tap directo en el botón "⋮", reusando 100% del estado/teclado/cierre
   * por click-afuera que `Dropdown` ya implementa.
   */
  openMenu: () => void;
}

export interface HistoryRowActionsProps {
  labels: HistoryRowActionsLabels;
  /** Navega a `/chat/{sessionId}` -- mismo destino que tocar el título de
   * la fila (`handleRowActivate` en `history-content.tsx`). */
  onResume: () => void;
}

/**
 * Menú de acciones de una fila del historial en móvil (tarea 8.2 de
 * d13-chat-conversacion, `design/VISTAS/02-chat.md` vista 12 §Móvil:
 * "acciones en menú ⋯ (long-press)"). Envuelve `Dropdown` (WAI-ARIA "menu
 * button": disparador con `aria-haspopup`/`aria-expanded`, panel
 * `role="menu"`, navegación con flechas/Home/End, Esc cierra) -- no
 * reimplementa nada de eso.
 *
 * VISIBILIDAD: el disparador vive SIEMPRE en el DOM; `.history-row__actions`
 * (`styles/components/history.css`) lo oculta en desktop y lo muestra en
 * móvil (mismo patrón "dual-render + CSS decide" que `components/shell/ai-banner.tsx`
 * -- ver su docstring) -- jsdom no evalúa `@media`, así que las pruebas de
 * componente verifican presencia/comportamiento, y el breakpoint se audita
 * en `styles/mobile-adaptations.test.ts`.
 *
 * DECISIÓN DE ALCANCE: la única acción disponible hoy es "Retomar" -- el
 * mockup (`design/mockups/12-historial.html`) también muestra "Archivar"
 * (🗄), pero esa acción no tiene backend todavía (`GET /sessions` de este
 * change no expone el concepto de sesión archivada; llega con
 * `d18-mi-espacio`, ver `openspec/BACKLOG-DESCUBRIMIENTOS.md` -- mismo
 * hueco ya documentado para los botones de acción secundarios de
 * escritorio en la tarea 7.1). El menú queda listo para sumar ese ítem
 * cuando el backend exista, sin tener que rediseñar el mecanismo de
 * apertura.
 */
export const HistoryRowActions = forwardRef<HistoryRowActionsHandle, HistoryRowActionsProps>(
  function HistoryRowActions({ labels, onResume }, ref) {
    const wrapperRef = useRef<HTMLDivElement>(null);

    useImperativeHandle(ref, () => ({
      openMenu: () => {
        wrapperRef.current?.querySelector<HTMLButtonElement>(".dropdown__trigger")?.click();
      },
    }));

    const items: DropdownItem[] = [{ id: "resume", label: labels.resume, onSelect: onResume }];

    return (
      <div className="history-row__actions" ref={wrapperRef}>
        <Dropdown
          triggerLabel={labels.menuLabel}
          triggerIcon={<span aria-hidden="true">⋮</span>}
          triggerClassName="history-row__menu-trigger"
          items={items}
          align="end"
        />
      </div>
    );
  },
);
