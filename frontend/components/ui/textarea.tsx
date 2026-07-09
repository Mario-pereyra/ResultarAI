"use client";

import { forwardRef, type TextareaHTMLAttributes } from "react";
import { Field } from "./field";

export interface TextareaProps
  extends Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, "id"> {
  label: string;
  hint?: string;
  error?: string;
  required?: boolean;
  id?: string;
}

/**
 * `.field` + `.textarea` — envoltorio fino sobre design/mockups/tokens.css
 * §5.5 (altura mínima 88 px, redimensionable vertical). Mismo contrato de
 * accesibilidad que `Input`.
 */
export const Textarea = forwardRef<HTMLTextAreaElement, TextareaProps>(
  function Textarea(
    { label, hint, error, required = false, id, className, ...rest },
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
          <textarea
            ref={ref}
            id={controlId}
            className={["textarea", invalid ? "is-invalid" : "", className]
              .filter(Boolean)
              .join(" ")}
            required={required}
            aria-invalid={invalid || undefined}
            aria-describedby={describedBy}
            {...rest}
          />
        )}
      </Field>
    );
  },
);
