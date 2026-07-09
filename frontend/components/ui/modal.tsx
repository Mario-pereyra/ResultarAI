"use client";

import { createPortal } from "react-dom";
import { useEffect, useId, useRef, type MouseEvent as ReactMouseEvent, type ReactNode } from "react";

/**
 * Modal (tarea 4.6, d10-design-system-shell).
 * Envoltorio fino sobre `.overlay`/`.modal` (styles/components/modal.css,
 * portado verbatim de design/mockups/tokens.css §5.18). Aporta semántica
 * (`role="dialog"`, `aria-modal`, `aria-labelledby`), trampa de foco,
 * cierre por Esc y retorno de foco al disparador — comportamiento exigido
 * por el escenario "Modal con trampa de foco" de
 * openspec/changes/d10-design-system-shell/specs/design-system/spec.md.
 */

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

export type ModalProps = {
  open: boolean;
  onClose: () => void;
  /** Título del modal (`.modal__title`), texto requerido — sin fallback hardcodeado. */
  title: string;
  /** aria-label del botón de cierre (ícono-only). */
  closeLabel: string;
  children: ReactNode;
  footer?: ReactNode;
  /**
   * design/DESIGN-SYSTEM.md §8.8: "Esc cierra (salvo variante destructiva a
   * mitad de confirmación)". Poner en `false` para esa variante.
   */
  closeOnEscape?: boolean;
  /** Click en el scrim (fuera de `.modal`) cierra. Mismo criterio que closeOnEscape. */
  closeOnOverlayClick?: boolean;
};

export function Modal({
  open,
  onClose,
  title,
  closeLabel,
  children,
  footer,
  closeOnEscape = true,
  closeOnOverlayClick = true,
}: ModalProps) {
  const titleId = useId();
  const modalRef = useRef<HTMLDivElement | null>(null);
  const triggerRef = useRef<Element | null>(null);

  // onClose/closeOnEscape se leen desde un ref dentro del listener para que
  // el efecto de trampa de foco dependa solo de `open`: así un re-render del
  // padre con una nueva identidad de `onClose` no reinicia el foco inicial
  // ni el bloqueo de scroll mientras el modal sigue abierto.
  const onCloseRef = useRef(onClose);
  const closeOnEscapeRef = useRef(closeOnEscape);
  useEffect(() => {
    onCloseRef.current = onClose;
    closeOnEscapeRef.current = closeOnEscape;
  }, [onClose, closeOnEscape]);

  useEffect(() => {
    if (!open) return;

    triggerRef.current = document.activeElement;
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const focusables = () =>
      Array.from(modalRef.current?.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR) ?? []);

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
      const active = document.activeElement as HTMLElement | null;
      const activeIndex = active ? nodes.indexOf(active) : -1;

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
      document.body.style.overflow = previousOverflow;
      const trigger = triggerRef.current;
      if (trigger instanceof HTMLElement) {
        trigger.focus();
      }
    };
  }, [open]);

  if (!open || typeof window === "undefined") return null;

  function handleOverlayMouseDown(event: ReactMouseEvent<HTMLDivElement>) {
    if (!closeOnOverlayClick) return;
    if (event.target === event.currentTarget) {
      onClose();
    }
  }

  return createPortal(
    <div className="overlay" onMouseDown={handleOverlayMouseDown}>
      <div className="modal" role="dialog" aria-modal="true" aria-labelledby={titleId} ref={modalRef}>
        <div className="modal__head">
          <h2 className="modal__title" id={titleId}>
            {title}
          </h2>
          <button type="button" className="btn btn--ghost btn--sm" aria-label={closeLabel} onClick={onClose}>
            <CloseIcon />
          </button>
        </div>
        <div className="modal__body">{children}</div>
        {footer ? <div className="modal__foot">{footer}</div> : null}
      </div>
    </div>,
    document.body,
  );
}

function CloseIcon() {
  return (
    <svg viewBox="0 0 16 16" width="16" height="16" aria-hidden="true" focusable="false">
      <path d="M3 3l10 10M13 3L3 13" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" fill="none" />
    </svg>
  );
}
