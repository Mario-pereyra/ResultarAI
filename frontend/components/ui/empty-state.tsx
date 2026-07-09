import type { ReactNode } from "react";

/**
 * EmptyState (tarea 4.8, d10-design-system-shell).
 * Envoltorio fino sobre `.empty-state` (styles/components/empty-state.css,
 * portado verbatim de design/mockups/tokens.css §5.12).
 * design/DESIGN-SYSTEM.md §8.22: "ícono 32 + título + hint (≤42ch) + CTA
 * opcional"; "A11y: el CTA es foco lógico siguiente tras cargar la vista
 * vacía" — se resuelve solo con el orden natural del DOM (título → hint →
 * acción), sin robar foco.
 *
 * No es un Client Component: no usa hooks ni eventos, así que puede
 * renderizarse también desde un Server Component.
 */

export type EmptyStateProps = {
  icon?: ReactNode;
  title: string;
  description: string;
  /** CTA opcional (ej. un <button>/<a> ya armado por quien lo usa). */
  action?: ReactNode;
};

export function EmptyState({ icon, title, description, action }: EmptyStateProps) {
  return (
    <div className="empty-state">
      {icon ? (
        <span className="empty-state__icon" aria-hidden="true">
          {icon}
        </span>
      ) : null}
      <p className="empty-state__title">{title}</p>
      <p className="empty-state__hint">{description}</p>
      {action ?? null}
    </div>
  );
}
