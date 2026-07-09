"use client";

import { forwardRef, type ButtonHTMLAttributes, type ReactNode } from "react";

export type ButtonVariant = "primary" | "secondary" | "danger" | "ghost";
export type ButtonSize = "sm" | "md" | "lg";

export interface ButtonProps
  extends Omit<ButtonHTMLAttributes<HTMLButtonElement>, "children"> {
  /** Texto/contenido del botón. Requerido: nunca hay un botón sin label visible. */
  children: ReactNode;
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** `.btn--block`: ocupa el 100% del ancho disponible. */
  block?: boolean;
  /**
   * Estado de carga (`.btn--loading`, design/DESIGN-SYSTEM.md §8.1): agrega
   * `aria-busy="true"`, deshabilita la interacción (atributo `disabled`
   * real, no solo la clase) y muestra el spinner de `styles/components/button.css`.
   * El texto NUNCA se quita del DOM (queda transparente vía CSS) para que
   * los lectores de pantalla sigan anunciándolo.
   */
  loading?: boolean;
}

/**
 * `.btn` — envoltorio fino sobre las clases de design/mockups/tokens.css
 * §5.2. Variantes primary/secondary/danger/ghost, tamaños sm/lg/block
 * (design/DESIGN-SYSTEM.md §8.1).
 */
export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  function Button(
    {
      children,
      variant = "primary",
      size = "md",
      block = false,
      loading = false,
      disabled,
      className,
      type = "button",
      ...rest
    },
    ref,
  ) {
    const classes = [
      "btn",
      `btn--${variant}`,
      size !== "md" ? `btn--${size}` : "",
      block ? "btn--block" : "",
      loading ? "btn--loading" : "",
      className,
    ]
      .filter(Boolean)
      .join(" ");

    return (
      <button
        ref={ref}
        type={type}
        className={classes}
        disabled={disabled || loading}
        aria-busy={loading || undefined}
        {...rest}
      >
        {children}
      </button>
    );
  },
);
