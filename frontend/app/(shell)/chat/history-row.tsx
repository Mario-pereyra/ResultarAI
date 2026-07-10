"use client";

import type { MouseEvent as ReactMouseEvent, ReactNode } from "react";
import { TableRow } from "@/components/ui/table";
import { useLongPress } from "@/lib/use-long-press";

export interface HistoryTableRowProps {
  sessionId: string;
  /** Navega a `/chat/{sessionId}` -- mismo destino que el título de la fila
   * (que ya es un `<button>` propio, ver el guard de `handleClick` de
   * abajo). */
  onActivate: (sessionId: string) => void;
  /** Abre el menú de acciones de ESTA fila (`HistoryRowActions`, tarea
   * 8.2) -- lo invoca el long-press de la fila completa. */
  onLongPressOpenMenu: () => void;
  className?: string;
  children: ReactNode;
}

/**
 * Fila de la tabla del historial con long-press (tarea 8.2 de
 * d13-chat-conversacion, `design/VISTAS/02-chat.md` vista 12 §Móvil:
 * "acciones en menú ⋯ (long-press)"). Envuelve `TableRow` -- el CONTENIDO
 * de las celdas sigue viviendo en `history-content.tsx` (`children`), esta
 * pieza SOLO agrega el gesto de press-and-hold sobre la fila completa y
 * decide si un click posterior navega o no.
 *
 * SUPRESIÓN DEL CLICK TRAS UN LONG-PRESS: ver el docstring de
 * `useLongPress` (`lib/use-long-press.ts`, sección "ORDEN EN EL CALLER")
 * para el mecanismo completo y por qué el ORDEN de los dos guards de abajo
 * importa -- `onLongPressOpenMenu` (`HistoryRowActionsHandle.openMenu`)
 * simula un click sobre el disparador "⋮" para abrir el menú, y ESE click
 * sintético burbujea hasta acá primero. El guard de "vino de un <button>
 * propio" (título de la fila, disparador "⋮") se evalúa PRIMERO y lo
 * absorbe sin tocar `consumeLongPress()` -- así el flag sigue disponible
 * para el click de compatibilidad real que el navegador dispara después,
 * al soltar el dedo fuera de cualquier botón, que es el que
 * `consumeLongPress()` efectivamente necesita suprimir.
 */
export function HistoryTableRow({
  sessionId,
  onActivate,
  onLongPressOpenMenu,
  className,
  children,
}: HistoryTableRowProps) {
  const { handlers, consumeLongPress } = useLongPress({ onLongPress: onLongPressOpenMenu });

  function handleClick(event: ReactMouseEvent<HTMLTableRowElement>) {
    // El título de la fila (`.history-row__title-link`) y el disparador del
    // menú de acciones (`.dropdown__trigger`, dentro de `HistoryRowActions`)
    // ya son `<button>`s con su propio `onClick` -- evita un segundo
    // `onActivate` (o abrir el menú Y navegar) para el mismo click. VA
    // PRIMERO (ver el docstring de arriba): absorbe el click sintético de
    // `onLongPressOpenMenu` sin consumir el flag de `useLongPress`.
    if (event.target instanceof HTMLElement && event.target.closest("button")) return;
    if (consumeLongPress()) return;
    onActivate(sessionId);
  }

  return (
    <TableRow className={className} onClick={handleClick} {...handlers}>
      {children}
    </TableRow>
  );
}
