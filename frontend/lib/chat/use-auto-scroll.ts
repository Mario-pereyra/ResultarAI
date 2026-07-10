"use client";

import { useCallback, useEffect, useRef, useState, type RefObject } from "react";

/**
 * Auto-scroll condicionado de la columna de mensajes (d13-chat-conversacion,
 * tarea 3.3, `design/VISTAS/02-chat.md` §0.4: "auto-scroll solo si el
 * usuario está abajo; si subió, botón flotante «↓ Nuevos mensajes»").
 *
 * Toda la medición pasa por `element.scrollTop`/`scrollHeight`/`clientHeight`
 * de un `ref` real -- nunca por `window`/`document` -- a propósito: en jsdom
 * (Vitest) esas tres propiedades son mockeables sobre un elemento concreto
 * (`Object.defineProperty(el, "scrollHeight", { value, configurable: true })`),
 * lo que permite simular "el usuario scrolleó hacia arriba" sin un layout de
 * scroll real, que jsdom no implementa.
 */

/** Distancia en px al fondo del contenedor por debajo de la cual se considera
 * "el usuario está al final" (tolera el rebote de scroll inercial de
 * touch/trackpad sin perder el estado "al final" por unos pocos px de más). */
export const AUTO_SCROLL_BOTTOM_THRESHOLD_PX = 48;

export interface UseAutoScrollResult {
  /** Ref a asignar al elemento con `overflow-y: auto` que contiene los mensajes. */
  containerRef: RefObject<HTMLDivElement | null>;
  /** `true` cuando llegó contenido nuevo mientras el usuario no estaba al
   * final: dispara el botón flotante "Nuevos mensajes". */
  showNewMessagesButton: boolean;
  /** Handler de `onScroll` del contenedor: actualiza si el usuario está al final. */
  handleScroll: () => void;
  /** Baja al fondo y reactiva el auto-scroll (click del botón flotante). */
  scrollToBottom: () => void;
}

/**
 * `contentVersion` cambia con cada fragmento/mensaje nuevo (el caller arma
 * una clave derivada de la cantidad de mensajes + longitud del texto en
 * streaming). En cada cambio: si el usuario estaba al final ANTES de que
 * llegara el contenido nuevo, se fuerza el scroll al fondo; si no, se
 * enciende `showNewMessagesButton` sin tocar el scroll del usuario.
 */
export function useAutoScroll(contentVersion: string | number): UseAutoScrollResult {
  const containerRef = useRef<HTMLDivElement | null>(null);
  // Estado mutable consultado sincrónicamente desde el efecto de scroll (no
  // dispara re-render por sí mismo): `showNewMessagesButton` es el único
  // valor derivado que la UI necesita re-renderizar.
  const isAtBottomRef = useRef(true);
  const [showNewMessagesButton, setShowNewMessagesButton] = useState(false);

  const computeIsAtBottom = useCallback(() => {
    const el = containerRef.current;
    if (!el) return true;
    const distanceToBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    return distanceToBottom <= AUTO_SCROLL_BOTTOM_THRESHOLD_PX;
  }, []);

  const handleScroll = useCallback(() => {
    const atBottom = computeIsAtBottom();
    isAtBottomRef.current = atBottom;
    if (atBottom) setShowNewMessagesButton(false);
  }, [computeIsAtBottom]);

  const scrollToBottom = useCallback(() => {
    const el = containerRef.current;
    if (el) el.scrollTop = el.scrollHeight;
    isAtBottomRef.current = true;
    setShowNewMessagesButton(false);
  }, []);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    if (isAtBottomRef.current) {
      el.scrollTop = el.scrollHeight;
    } else {
      setShowNewMessagesButton(true);
    }
    // Se re-ejecuta solo cuando llega contenido nuevo (`contentVersion`): no
    // usa ninguna otra dependencia externa (`isAtBottomRef`/`setShowNewMessagesButton`
    // son estables entre renders), así que no hace falta silenciar el lint.
  }, [contentVersion]);

  return { containerRef, showNewMessagesButton, handleScroll, scrollToBottom };
}
