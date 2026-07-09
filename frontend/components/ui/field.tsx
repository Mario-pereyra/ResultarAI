"use client";

import { useId, type ReactNode } from "react";

/**
 * Datos resueltos por `Field` que el control (input/textarea/select) debe
 * aplicar: id para el `htmlFor` del label, `aria-describedby` combinando
 * hint + error (design/DESIGN-SYSTEM.md §8.2: "el hint no desaparece cuando
 * aparece el error, se apilan") y si el control debe marcarse inválido.
 */
export interface FieldRenderProps {
  id: string;
  describedBy: string | undefined;
  invalid: boolean;
}

export interface FieldProps {
  /** Texto del label. Siempre requerido: ningún control se renderiza sin label asociado. */
  label: string;
  /** Texto de ayuda. Se sigue mostrando aunque también haya error (se apilan). */
  hint?: string;
  /** Mensaje de error. Marca el control como inválido (`aria-invalid`) cuando está presente. */
  error?: string;
  required?: boolean;
  /** Id explícito del control. Si se omite, se genera uno con `useId()`. */
  id?: string;
  className?: string;
  /** Render prop: recibe los atributos ya resueltos para el control real. */
  children: (props: FieldRenderProps) => ReactNode;
}

/**
 * `.field` — envoltorio fino de label + control + hint/error compartido por
 * Input, Textarea y Select (design/mockups/tokens.css §5.5,
 * design/DESIGN-SYSTEM.md §8.2/§8.3). No renderiza el control: cada
 * componente concreto le pasa su propio `<input>`/`<textarea>`/`<select>`
 * vía `children`, ya con el `id`/`aria-describedby`/`aria-invalid`
 * resueltos acá.
 */
export function Field({
  label,
  hint,
  error,
  required = false,
  id,
  className,
  children,
}: FieldProps) {
  const generatedId = useId();
  const controlId = id ?? generatedId;
  const hintId = hint ? `${controlId}-hint` : undefined;
  const errorId = error ? `${controlId}-error` : undefined;
  const describedBy = [hintId, errorId].filter(Boolean).join(" ") || undefined;
  const invalid = Boolean(error);

  return (
    <div className={["field", className].filter(Boolean).join(" ")}>
      <label className="field-label" htmlFor={controlId}>
        {label}
        {required ? (
          <span className="req" aria-hidden="true">
            {" "}
            *
          </span>
        ) : null}
      </label>
      {children({ id: controlId, describedBy, invalid })}
      {hint ? (
        <span className="field-hint" id={hintId}>
          {hint}
        </span>
      ) : null}
      {error ? (
        <span className="field-error" id={errorId}>
          {error}
        </span>
      ) : null}
    </div>
  );
}
