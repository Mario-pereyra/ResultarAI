"use client";

import { forwardRef, type ReactNode, type SelectHTMLAttributes } from "react";
import { Field } from "./field";

export interface SelectProps
  extends Omit<SelectHTMLAttributes<HTMLSelectElement>, "id"> {
  label: string;
  hint?: string;
  error?: string;
  required?: boolean;
  id?: string;
  /** `<option>`/`<optgroup>` del select, provistas por quien lo usa. */
  children: ReactNode;
}

/**
 * `.field` + `.select` — envoltorio fino sobre design/mockups/tokens.css
 * §5.5. `<select>` nativo (design/DESIGN-SYSTEM.md §8.3: "Nativo en v1"),
 * mismo contrato de accesibilidad que `Input`.
 *
 * El chevron se pinta con un ícono SVG real (`stroke="currentColor"` +
 * `.select-chevron` de styles/components/fields.css, que fija
 * `color: var(--ink-faint)`) en vez del `background-image` con hex
 * embebido de la fuente — ver la nota de cabecera de fields.css para el
 * detalle de por qué (auditoría de colores, tarea 4.9).
 */
export const Select = forwardRef<HTMLSelectElement, SelectProps>(
  function Select(
    {
      label,
      hint,
      error,
      required = false,
      id,
      className,
      children,
      ...rest
    },
    ref,
  ) {
    return (
      <Field
        label={label}
        hint={hint}
        error={error}
        required={required}
        id={id}
      >
        {({ id: controlId, describedBy, invalid }) => (
          <div className="select-wrap">
            <select
              ref={ref}
              id={controlId}
              className={["select", invalid ? "is-invalid" : "", className]
                .filter(Boolean)
                .join(" ")}
              required={required}
              aria-invalid={invalid || undefined}
              aria-describedby={describedBy}
              {...rest}
            >
              {children}
            </select>
            <svg
              className="select-chevron"
              width="14"
              height="14"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2.2"
              strokeLinecap="round"
              strokeLinejoin="round"
              aria-hidden="true"
            >
              <polyline points="6 9 12 15 18 9" />
            </svg>
          </div>
        )}
      </Field>
    );
  },
);
