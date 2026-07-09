"use client";

import { createPortal } from "react-dom";
import { useId, useRef, type MouseEvent as ReactMouseEvent, type ReactNode } from "react";
import { useFocusTrap } from "@/lib/use-focus-trap";

/**
 * Modal (tarea 4.6, d10-design-system-shell).
 * Envoltorio fino sobre `.overlay`/`.modal` (styles/components/modal.css,
 * portado verbatim de design/mockups/tokens.css §5.18). Aporta semántica
 * (`role="dialog"`, `aria-modal`, `aria-labelledby`), trampa de foco,
 * cierre por Esc y retorno de foco al disparador — comportamiento exigido
 * por el escenario "Modal con trampa de foco" de
 * openspec/changes/d10-design-system-shell/specs/design-system/spec.md.
 *
 * La trampa de foco vive en `lib/use-focus-trap.ts` (extraída en la tarea
 * 5.7 para que el drawer móvil del shell reuse el mismo comportamiento).
 */

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

  useFocusTrap(open, modalRef, { onClose, closeOnEscape });

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
