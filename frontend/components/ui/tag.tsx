import type { HTMLAttributes, ReactNode } from "react";

export type TagVariant =
  | "neutral"
  | "accent"
  | "money"
  | "info"
  | "warn"
  | "danger"
  | "alt";

export interface TagProps extends HTMLAttributes<HTMLSpanElement> {
  variant?: TagVariant;
  /** `.tag--outline`: fondo transparente. */
  outline?: boolean;
  /** Texto del tag. Requerido (design/DESIGN-SYSTEM.md §8.6: siempre la palabra, nunca solo color). */
  children: ReactNode;
}

/**
 * `.tag` — envoltorio fino sobre design/mockups/tokens.css §5.3
 * (design/DESIGN-SYSTEM.md §8.6). Estático (no interactivo en v1). Mapa de
 * riesgo HITL: bajo = `money` · medio = `warn` · alto = `alt` · crítico = `danger`.
 */
export function Tag({
  variant = "neutral",
  outline = false,
  className,
  children,
  ...rest
}: TagProps) {
  const variantClass = variant === "neutral" ? "" : `tag--${variant}`;

  return (
    <span
      className={["tag", variantClass, outline ? "tag--outline" : "", className]
        .filter(Boolean)
        .join(" ")}
      {...rest}
    >
      {children}
    </span>
  );
}
