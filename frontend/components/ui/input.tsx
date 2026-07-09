"use client";

import { forwardRef, type InputHTMLAttributes } from "react";
import { Field } from "./field";

export interface InputProps
  extends Omit<InputHTMLAttributes<HTMLInputElement>, "id"> {
  /** Texto del label, requerido (design/DESIGN-SYSTEM.md §8.2: "<label for> siempre"). */
  label: string;
  hint?: string;
  error?: string;
  required?: boolean;
  id?: string;
  /** `.input--mono`: para IDs/parámetros (design/DESIGN-SYSTEM.md §8.2). */
  mono?: boolean;
}

/**
 * `.field` + `.input` — envoltorio fino sobre design/mockups/tokens.css
 * §5.5. Label asociado vía `htmlFor`/`id` (generado con `useId` si no se
 * provee), `aria-invalid` + `aria-describedby` cuando hay error.
 */
export const Input = forwardRef<HTMLInputElement, InputProps>(function Input(
  {
    label,
    hint,
    error,
    required = false,
    id,
    mono = false,
    className,
    ...rest
  },
  ref,
) {
  return (
    <Field label={label} hint={hint} error={error} required={required} id={id}>
      {({ id: controlId, describedBy, invalid }) => (
        <input
          ref={ref}
          id={controlId}
          className={[
            "input",
            mono ? "input--mono" : "",
            invalid ? "is-invalid" : "",
            className,
          ]
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
});
