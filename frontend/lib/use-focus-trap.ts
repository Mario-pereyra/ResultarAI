"use client";

import { useEffect, useRef, type RefObject } from "react";

/**
 * Trampa de foco genérica (tarea 5.7, d10-design-system-shell), extraída de
 * `components/ui/modal.tsx` (tarea 4.6) para que el drawer móvil del
 * sidebar (`components/shell/sidebar.tsx`) reuse EXACTAMENTE el mismo
 * comportamiento de accesibilidad que el Modal — Tab cicla dentro del
 * contenedor, Esc cierra y devuelve el foco al disparador — en vez de
 * reimplementarlo. `Modal` se migró a este hook en la misma tarea; ambos
 * comparten esta única implementación.
 */

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

export type UseFocusTrapOptions = {
  onClose: () => void;
  /** design/DESIGN-SYSTEM.md §8.8: "Esc cierra (salvo variante destructiva a mitad de confirmación)". */
  closeOnEscape?: boolean;
  /** Bloquea el scroll del body mientras la trampa está activa. */
  lockBodyScroll?: boolean;
};

export function useFocusTrap<T extends HTMLElement>(
  active: boolean,
  containerRef: RefObject<T | null>,
  { onClose, closeOnEscape = true, lockBodyScroll = true }: UseFocusTrapOptions,
) {
  // onClose/closeOnEscape se leen desde un ref dentro del listener para que
  // el efecto dependa solo de `active`: un re-render del padre con una
  // nueva identidad de `onClose` no reinicia el foco inicial ni el bloqueo
  // de scroll mientras la trampa sigue activa.
  const onCloseRef = useRef(onClose);
  const closeOnEscapeRef = useRef(closeOnEscape);
  useEffect(() => {
    onCloseRef.current = onClose;
    closeOnEscapeRef.current = closeOnEscape;
  }, [onClose, closeOnEscape]);

  useEffect(() => {
    if (!active) return;

    const triggerElement = document.activeElement;
    const previousOverflow = document.body.style.overflow;
    if (lockBodyScroll) document.body.style.overflow = "hidden";

    const focusables = () =>
      Array.from(containerRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR) ?? []);

    focusables()[0]?.focus();

    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        if (closeOnEscapeRef.current) {
          event.preventDefault();
          onCloseRef.current();
        }
        return;
      }

      if (event.key !== "Tab") return;

      const nodes = focusables();
      if (nodes.length === 0) {
        event.preventDefault();
        return;
      }

      const first = nodes[0];
      const last = nodes[nodes.length - 1];
      const activeElement = document.activeElement as HTMLElement | null;
      const activeIndex = activeElement ? nodes.indexOf(activeElement) : -1;

      if (event.shiftKey) {
        if (activeIndex <= 0) {
          event.preventDefault();
          last.focus();
        }
      } else if (activeIndex === -1 || activeIndex === nodes.length - 1) {
        event.preventDefault();
        first.focus();
      }
    }

    document.addEventListener("keydown", handleKeyDown);

    return () => {
      document.removeEventListener("keydown", handleKeyDown);
      if (lockBodyScroll) document.body.style.overflow = previousOverflow;
      if (triggerElement instanceof HTMLElement) {
        triggerElement.focus();
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active, lockBodyScroll]);
}
